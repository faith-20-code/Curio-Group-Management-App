from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import IntegrityError, transaction
import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from .models import Work, SubTask, SubTaskStep, Group, Document, Profile
from .forms import (
    SignupForm, GroupForm, AddMembersForm, WorkForm,
    SubTaskForm, LeaderDocumentForm, MemberDocumentForm
)


# ── Home ──────────────────────────────────────────────────────────────────────
def home(request):
    return render(request, "index.html")


# ── AI Helper ─────────────────────────────────────────────────────────────────
def _call_ai(prompt):
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "nvidia/nemotron-3-super-120b-a12b:free",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
        },
        timeout=30,
    )
    try:
        data = response.json()
    except Exception:
        raise Exception(f"Non-JSON response: {response.text[:200]}")

    if "choices" in data:
        return data["choices"][0]["message"]["content"].strip()
    if "error" in data:
        raise Exception(str(data["error"]))
    raise Exception(f"Unexpected response: {str(data)[:200]}")


def _extract_json_array(raw):
    """Shared by ai_assign_tasks and ai_generate_steps — was duplicated logic."""
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    start, end = raw.find("["), raw.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON array found in AI response: {raw[:200]}")
    return json.loads(raw[start:end])


# ── Auth ──────────────────────────────────────────────────────────────────────

def login_view(request):
    error = None
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST["username"],
            password=request.POST["password"]
        )
        if user:
            auth_login(request, user)
            Profile.objects.get_or_create(user=user)
            if user.is_superuser:
                return redirect("/admin/")
            return redirect("dashboard")
        error = "Invalid username or password."
    return render(request, "login.html", {"error": error})


def signup_view(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.create_user(
            username=form.cleaned_data["username"],
            email=form.cleaned_data.get("email", ""),
            first_name=form.cleaned_data.get("first_name", ""),
            last_name=form.cleaned_data.get("last_name", ""),
            password=form.cleaned_data["password"],
        )
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.skills = form.cleaned_data.get("skills", "")
        profile.save()
        auth_login(request, user)
        return redirect("dashboard")
    return render(request, "signup.html", {"form": form})


def logout_view(request):
    auth_logout(request)
    return redirect("login")


# ── Dashboard ─────────────────────────────────────────────────────────────────

@login_required(login_url="login")
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    is_leader = profile.is_leader

    leader_groups = Group.objects.filter(leader=request.user)
    member_group = Group.objects.filter(members=request.user).first()

    if is_leader:
        group_id = request.GET.get("group")
        selected_group = leader_groups.filter(id=group_id).first() if group_id else None
        group = selected_group or leader_groups.first()
    else:
        group = member_group

    works = Work.objects.filter(group=group) if group else Work.objects.none()
    documents = Document.objects.filter(group=group) if group else Document.objects.none()
    subtasks = (
        SubTask.objects.filter(work__group=group).select_related("work", "assigned_to")
        if is_leader and group
        else SubTask.objects.filter(assigned_to=request.user).select_related("work", "assigned_to")
    )

    total = subtasks.count()
    completed = subtasks.filter(status="completed").count()
    task_completion_percentage = round(completed / total * 100) if total > 0 else 0

    # Tab data: at most 2 cards shown per status on the dashboard itself.
    # "...more" links to task_list_view for the full set of that status.
    # Without this cap, a group with 10+ tasks made the dashboard page
    # grow indefinitely with no internal scroll boundary — capping the
    # count here (not just in CSS) is what actually fixes that, since
    # the template only ever receives 2 items per bucket to render.
    TAB_PREVIEW_LIMIT = 2
    todo_qs = subtasks.filter(status="pending").order_by("-created_at")
    in_progress_qs = subtasks.filter(status="in_progress").order_by("-created_at")
    completed_qs = subtasks.filter(status="completed").order_by("-created_at")

    return render(request, "dashboard.html", {
        "group": group,
        "leader_groups": leader_groups,
        "works": works,
        "subtasks": subtasks,
        "documents": documents,
        "is_leader": is_leader,
        "task_completion_percentage": task_completion_percentage,
        "todo_tasks": todo_qs[:TAB_PREVIEW_LIMIT],
        "todo_total": todo_qs.count(),
        "in_progress_tasks": in_progress_qs[:TAB_PREVIEW_LIMIT],
        "in_progress_total": in_progress_qs.count(),
        "completed_tasks": completed_qs[:TAB_PREVIEW_LIMIT],
        "completed_total": completed_qs.count(),
    })


@login_required(login_url="login")
def task_list_view(request, status):
    """
    The '...more' destination: a dedicated page listing ALL tasks of one
    status. Two modes:
    - Normal: leader sees the whole group, member sees only their own.
    - ?member=<id>: leader-only, scopes the list to one specific group
      member instead of the whole group (used by member_tasks.html's
      "...more" links, since a single member can also have more than
      2 tasks in a bucket).
    """
    valid_statuses = {"pending", "in_progress", "completed"}
    if status not in valid_statuses:
        return JsonResponse({"error": "Invalid status."}, status=400)

    profile, _ = Profile.objects.get_or_create(user=request.user)
    is_leader = profile.is_leader
    group = (
        Group.objects.filter(leader=request.user).first()
        if is_leader
        else Group.objects.filter(members=request.user).first()
    )

    member_id = request.GET.get("member")
    viewing_member = None

    if member_id and is_leader and group:
        viewing_member = get_object_or_404(User, pk=member_id)
        if not group.members.filter(id=viewing_member.id).exists():
            return JsonResponse({"error": "That user is not a member of your group."}, status=403)
        subtasks = SubTask.objects.filter(assigned_to=viewing_member, work__group=group, status=status)
    elif is_leader and group:
        subtasks = SubTask.objects.filter(work__group=group, status=status)
    else:
        subtasks = SubTask.objects.filter(assigned_to=request.user, status=status)

    subtasks = subtasks.select_related("work", "assigned_to").prefetch_related("steps").order_by("-created_at")

    return render(request, "task_list.html", {
        "subtasks": subtasks,
        "status": status,
        "status_label": dict(SubTask.STATUS).get(status, status),
        "is_leader": is_leader,
        "viewing_member": viewing_member,
    })


# ── Group ─────────────────────────────────────────────────────────────────────

@login_required(login_url="login")
def group_create(request):
    form = GroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        group = form.save(commit=False)
        group.leader = request.user
        group.save()
        form.save_m2m()
        profile, _ = Profile.objects.get_or_create(user=request.user)
        profile.is_leader = True
        profile.save()
        return redirect("dashboard")
    return render(request, "group_form.html", {"form": form, "title": "Create Group"})


@login_required(login_url="login")
def group_add_members(request, group_id):
    group = get_object_or_404(Group, id=group_id, leader=request.user)
    form = AddMembersForm(group, request.POST or None)
    if request.method == "POST" and form.is_valid():
        for member in form.cleaned_data["members"]:
            group.members.add(member)
        return redirect("dashboard")
    return render(request, "group_form.html", {"form": form, "title": "Add Members"})


# ── Work ──────────────────────────────────────────────────────────────────────

@login_required(login_url="login")
def work_create(request):
    leader_groups = Group.objects.filter(leader=request.user)
    if not leader_groups.exists():
        return redirect("group_create")
    form = WorkForm(request.user, request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        work = form.save(commit=False)
        work.created_by = request.user
        work.save()
        return redirect("dashboard")
    return render(request, "work_form.html", {
        "form": form,
        "title": "Create Work",
        "leader_groups": leader_groups,
    })


@login_required(login_url="login")
def work_detail(request, pk):
    """
    Shows a Work's breakdown status, subtasks, and step checklists.
    Accessible to the leader of the work's group AND any member of that
    group — members need this page to check off their own steps, not
    just the leader.
    """
    work = get_object_or_404(Work, pk=pk)
    is_leader_of_group = work.group.leader_id == request.user.id
    is_member_of_group = work.group.members.filter(id=request.user.id).exists()
    if not (is_leader_of_group or is_member_of_group):
        return JsonResponse({"error": "Not authorized to view this work."}, status=403)

    subtasks = work.subtasks.select_related("assigned_to").prefetch_related("steps")
    return render(request, "work_detail.html", {
        "work": work,
        "subtasks": subtasks,
        "is_broken_down": work.is_broken_down,
        "is_leader": is_leader_of_group,
    })


# ── SubTask: manual creation ──────────────────────────────────────────────────

@login_required(login_url="login")
def subtask_create(request):
    """
    Manual assignment path. If a subtask with the same (work, title)
    already exists, we don't silently create a duplicate AND we don't
    hard-crash — we surface a confirm step so the leader decides
    (per their answer: "let the leader decide").

    Also respects ?work=<id> from the dashboard's "Manual" link so the
    work dropdown is pre-selected instead of defaulting to nothing.
    """
    initial = {}
    preselected_work_id = request.GET.get("work")
    if preselected_work_id:
        initial["work"] = preselected_work_id

    form = SubTaskForm(request.user, request.POST or None, initial=initial)
    force = request.POST.get("force") == "1"

    if request.method == "POST" and form.is_valid():
        work = form.cleaned_data["work"]
        title = form.cleaned_data["title"]

        existing = SubTask.objects.filter(work=work, title__iexact=title).first()
        if existing and not force:
            return render(request, "subtask_form.html", {
                "form": form,
                "title": "Assign Task",
                "duplicate_warning": existing,
            })

        try:
            with transaction.atomic():
                subtask = form.save(commit=False)
                subtask.source = "manual"
                if existing and force:
                    existing.delete()
                subtask.save()
                work.recalculate_status()
        except IntegrityError:
            form.add_error(None, "That subtask title already exists for this work.")
            return render(request, "subtask_form.html", {"form": form, "title": "Assign Task"})

        return redirect("work_detail", pk=work.pk)

    return render(request, "subtask_form.html", {"form": form, "title": "Assign Task"})


# ── SubTask: AI auto-assign ───────────────────────────────────────────────────

@require_POST
@login_required(login_url="login")
def ai_assign_tasks(request):
    """
    AI auto-assign path. Per your answer: if the Work already has
    subtasks, the leader explicitly chooses mode=replace or mode=add_only
    via the request body — no silent re-running.
    """
    try:
        body = json.loads(request.body)
        work_id = body.get("work_id")
        doc_id = body.get("doc_id")
        mode = body.get("mode", "add_only")  # "replace" | "add_only"
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request."}, status=400)

    if mode not in ("replace", "add_only"):
        return JsonResponse({"error": "mode must be 'replace' or 'add_only'."}, status=400)

    group = Group.objects.filter(leader=request.user).first()
    if not group:
        return JsonResponse({"error": "No group found."}, status=403)

    work = get_object_or_404(Work, id=work_id, group=group)

    existing_subtasks = list(work.subtasks.all())
    if existing_subtasks and mode == "add_only":
        existing_titles = {s.title.lower() for s in existing_subtasks}
    else:
        existing_titles = set()

    if doc_id:
        doc = get_object_or_404(Document, id=doc_id, group=group)
    else:
        doc = Document.objects.filter(
            group=group, work=work, uploaded_by=request.user
        ).order_by("-uploaded_at").first()
        if not doc:
            doc = Document.objects.filter(
                group=group, uploaded_by=request.user
            ).order_by("-uploaded_at").first()

    if not doc:
        return JsonResponse(
            {"error": f"No document found for '{work.title}'. Upload a document and link it to this work first."},
            status=400,
        )

    doc_text = _extract_document_text(doc)
    if not doc_text.strip():
        return JsonResponse(
            {"error": "Could not read the document. Make sure it is a valid PDF, Word, or text document."},
            status=400,
        )

    members = group.members.all()
    if not members.exists():
        return JsonResponse({"error": "No members in group yet."}, status=400)

    member_list = []
    for m in members:
        p, _ = Profile.objects.get_or_create(user=m)
        member_list.append({"username": m.username, "user_id": m.id, "skills": p.skills or "general"})

    members_text = "\n".join(f"- {m['username']} (skills: {m['skills']})" for m in member_list)

    prompt = f"""You are an AI project manager. Analyse the following project document and:
1. Break it down into specific, actionable subtasks (between 3 and {len(member_list) * 2} subtasks).
2. Assign each subtask to the most suitable group member based on their skills.
3. Return ONLY a valid JSON array. No explanation, no markdown, no code fences.

Project document:
\"\"\"
{doc_text[:3000]}
\"\"\"

Group members and their skills:
{members_text}

Required output format (JSON array only):
[
  {{"title": "Subtask name", "assigned_to": "username"}}
]"""

    try:
        raw = _call_ai(prompt)
        if not raw:
            return JsonResponse({"error": "AI returned an empty response."}, status=500)
        subtask_suggestions = _extract_json_array(raw)
    except (ValueError, json.JSONDecodeError) as e:
        return JsonResponse({"error": f"AI returned invalid JSON: {str(e)}"}, status=500)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    member_lookup = {m["username"]: m["user_id"] for m in member_list}
    created = []

    with transaction.atomic():
        if mode == "replace":
            work.subtasks.all().delete()

        for item in subtask_suggestions:
            title = item.get("title", "").strip()
            username = item.get("assigned_to", "").strip()
            user_id = member_lookup.get(username)

            if not title or not user_id:
                continue
            if title.lower() in existing_titles:
                continue  # add_only mode: skip titles that already exist

            assigned_user = User.objects.filter(id=user_id).first()
            if not assigned_user:
                continue

            subtask, was_created = SubTask.objects.get_or_create(
                work=work, title=title,
                defaults={"assigned_to": assigned_user, "status": "pending",
                          "completion_percentage": 0, "source": "ai"},
            )
            if was_created:
                created.append({
                    "id": subtask.id, "title": subtask.title,
                    "assigned_to": assigned_user.username,
                    "status": subtask.get_status_display(),
                })

        work.recalculate_status()

    if not created:
        return JsonResponse(
            {"error": "No new subtasks created — they may already exist, or AI could not match skills."},
            status=400,
        )

    return JsonResponse({"subtasks": created, "count": len(created)})


# ── SubTaskStep: AI-generated, works for manual OR AI-sourced subtasks ───────

@require_POST
@login_required(login_url="login")
def ai_generate_steps(request, subtask_id):
    """
    Member-facing: "Generate steps with AI" button on their own subtask,
    regardless of whether the subtask itself was created manually by the
    leader or by ai_assign_tasks. Uses the Work's original document as
    context, same as the parent breakdown did.
    """
    subtask = get_object_or_404(SubTask, pk=subtask_id, assigned_to=request.user)

    if subtask.has_steps:
        return JsonResponse({"error": "Steps already exist for this subtask."}, status=400)

    work = subtask.work
    doc = Document.objects.filter(group=work.group, work=work).order_by("-uploaded_at").first()
    doc_context = _extract_document_text(doc)[:2000] if doc else ""

    prompt = f"""You are an AI assistant helping break a subtask into small actionable steps.

Overall project work: "{work.title}" — {work.description}
{"Reference document: " + doc_context if doc_context else ""}

Subtask to break down: "{subtask.title}"

Return ONLY a valid JSON array of 3 to 8 short, concrete step titles. No explanation, no markdown.
Example format: ["Step one", "Step two", "Step three"]"""

    try:
        raw = _call_ai(prompt)
        if not raw:
            return JsonResponse({"error": "AI returned an empty response."}, status=500)
        step_titles = _extract_json_array(raw)
    except (ValueError, json.JSONDecodeError) as e:
        return JsonResponse({"error": f"AI returned invalid JSON: {str(e)}"}, status=500)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    created_steps = []
    with transaction.atomic():
        for i, title in enumerate(step_titles):
            if not isinstance(title, str) or not title.strip():
                continue
            step = SubTaskStep.objects.create(
                subtask=subtask, title=title.strip(), order=i, generated_by_ai=True
            )
            created_steps.append({"id": step.id, "title": step.title, "is_done": False})
        subtask.recalculate_completion()

    return JsonResponse({"steps": created_steps, "count": len(created_steps)})


@login_required(login_url="login")
def subtask_step_add(request, subtask_id):
    """Member manually adds a single step instead of using AI."""
    subtask = get_object_or_404(SubTask, pk=subtask_id, assigned_to=request.user)
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        if title:
            next_order = subtask.steps.count()
            SubTaskStep.objects.create(subtask=subtask, title=title, order=next_order)
            subtask.recalculate_completion()
        return redirect("work_detail", pk=subtask.work.pk)
    return render(request, "step_add.html", {"subtask": subtask})


@require_POST
@login_required(login_url="login")
def subtask_step_toggle(request, step_id):
    """
    Replaces the old SubTaskProgressForm slider. Checking/unchecking a
    step recalculates the subtask % automatically, which then recalculates
    the Work % — this is the rollup you described (member sees their
    subtask progress, leader sees Work-wide progress made of subtasks).
    """
    step = get_object_or_404(SubTaskStep, pk=step_id, subtask__assigned_to=request.user)
    step.is_done = not step.is_done
    step.save(update_fields=["is_done"])
    step.subtask.recalculate_completion()
    return JsonResponse({
        "step_id": step.id,
        "is_done": step.is_done,
        "subtask_completion": step.subtask.completion_percentage,
        "subtask_status": step.subtask.status,
        "work_completion": step.subtask.work.completion_percentage,
        "work_status": step.subtask.work.status,
    })


# ── Documents ─────────────────────────────────────────────────────────────────

@login_required(login_url="login")
def upload_document(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    is_leader = profile.is_leader
    group = (
        Group.objects.filter(leader=request.user).first()
        if is_leader
        else Group.objects.filter(members=request.user).first()
    )
    if not group:
        return redirect("group_create")

    FormClass = LeaderDocumentForm if is_leader else MemberDocumentForm
    form = FormClass(group, request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        doc = form.save(commit=False)
        doc.uploaded_by = request.user
        doc.group = group
        if not is_leader:
            doc.doc_type = "file"
        doc.save()
        return redirect("dashboard")

    return render(request, "upload_document.html", {"form": form, "is_leader": is_leader})


@require_POST
@login_required(login_url="login")
def document_delete(request, pk):
    """
    Bug fix #1: original version silently redirected with no permission
    error if the check failed — the doc just... didn't delete, no
    feedback. Now returns 403 explicitly when neither condition is met.

    Bug fix #2: was reachable via GET (the template used a plain <a> tag),
    meaning a prefetch, crawler, or middle-click could trigger deletion.
    @require_POST + the template's switch to a <form method="post">
    closes that off.
    """
    doc = get_object_or_404(Document, pk=pk)
    is_owner = request.user == doc.uploaded_by
    is_group_leader = Group.objects.filter(leader=request.user, pk=doc.group.pk).exists()

    if not (is_owner or is_group_leader):
        return JsonResponse({"error": "You don't have permission to delete this document."}, status=403)

    doc.delete()
    return redirect("dashboard")


# ── Member Profile ────────────────────────────────────────────────────────────

@login_required(login_url="login")
def member_profile(request, user_id):
    """
    Per your request: this page now shows ONLY name + qualifications
    (skills). Tasks/progress used to render here but that's been moved
    to member_tasks (leader-only) below — a leader who wants to see a
    member's tasks clicks through to that separate page instead.
    """
    member = get_object_or_404(User, pk=user_id)
    profile, _ = Profile.objects.get_or_create(user=member)
    group = Group.objects.filter(members=member).first()
    is_leader_viewing = group and group.leader_id == request.user.id
    return render(request, "member_profile.html", {
        "member": member,
        "profile": profile,
        "group": group,
        "is_leader_viewing": is_leader_viewing,
    })


@login_required(login_url="login")
def member_tasks(request, user_id):
    """
    Leader-only: the tasks view that used to live inside member_profile.
    Shows one member's subtasks broken into the same To-Do / In Progress
    / Completed tabs as the main dashboard, with full steps visible.
    """
    member = get_object_or_404(User, pk=user_id)
    group = Group.objects.filter(members=member, leader=request.user).first()
    if not group:
        return JsonResponse({"error": "You can only view tasks for members of your own group."}, status=403)

    subtasks = SubTask.objects.filter(assigned_to=member, work__group=group) \
        .select_related("work").prefetch_related("steps")

    TAB_PREVIEW_LIMIT = 2
    todo_qs = subtasks.filter(status="pending").order_by("-created_at")
    in_progress_qs = subtasks.filter(status="in_progress").order_by("-created_at")
    completed_qs = subtasks.filter(status="completed").order_by("-created_at")

    return render(request, "member_tasks.html", {
        "member": member,
        "group": group,
        "todo_tasks": todo_qs[:TAB_PREVIEW_LIMIT],
        "todo_total": todo_qs.count(),
        "in_progress_tasks": in_progress_qs[:TAB_PREVIEW_LIMIT],
        "in_progress_total": in_progress_qs.count(),
        "completed_tasks": completed_qs[:TAB_PREVIEW_LIMIT],
        "completed_total": completed_qs.count(),
    })# ── Document text extractor ───────────────────────────────────────────────────

def _extract_document_text(doc):
    if not doc:
        return ""
    if doc.doc_type == "text" and doc.text_content:
        return doc.text_content
    if not doc.file:
        return ""
    file_name = doc.file.name.lower()
    if file_name.endswith(".pdf"):
        try:
            import pdfplumber
            with pdfplumber.open(doc.file.path) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception:
            return ""
    if file_name.endswith(".docx"):
        try:
            from docx import Document as DocxDocument
            d = DocxDocument(doc.file.path)
            return "\n".join(p.text for p in d.paragraphs)
        except Exception:
            return ""
    if file_name.endswith(".doc"):
        try:
            import subprocess
            result = subprocess.run(["antiword", doc.file.path], capture_output=True, text=True)
            return result.stdout
        except Exception:
            return ""
    return ""


# ── AI: chat ──────────────────────────────────────────────────────────────────

@require_POST
@login_required(login_url="login")
def ai_chat(request):
    try:
        body = json.loads(request.body)
        user_message = body.get("message", "").strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request."}, status=400)

    if not user_message:
        return JsonResponse({"error": "Empty message."}, status=400)

    profile, _ = Profile.objects.get_or_create(user=request.user)
    is_leader = profile.is_leader
    group = (
        Group.objects.filter(leader=request.user).first()
        if is_leader
        else Group.objects.filter(members=request.user).first()
    )

    context_parts = [
        "You are Curio AI, a helpful assistant for a university group project management system.",
        f"You are talking to: {request.user.username} ({'Group Leader' if is_leader else 'Member'}).",
    ]

    if group:
        context_parts.append(f"Group name: {group.name}")
        context_parts.append(f"Group leader: {group.leader.username}")

        members_info = []
        for m in group.members.all():
            p, _ = Profile.objects.get_or_create(user=m)
            members_info.append(f"  - {m.username} (skills: {p.skills or 'not specified'})")
        if members_info:
            context_parts.append("Group members:\n" + "\n".join(members_info))

        docs = Document.objects.filter(group=group).order_by("-uploaded_at")[:3]
        for doc in docs:
            text = _extract_document_text(doc)
            if text:
                context_parts.append(f"Document '{doc.title or 'Untitled'}' content:\n{text[:800]}")

        subtasks = (
            SubTask.objects.filter(work__group=group)
            if is_leader
            else SubTask.objects.filter(assigned_to=request.user)
        )
        if subtasks.exists():
            task_lines = [
                f"  - {s.title} → {s.assigned_to.username} ({s.get_status_display()}, {s.completion_percentage}%)"
                for s in subtasks
            ]
            context_parts.append("Current tasks:\n" + "\n".join(task_lines))

    full_prompt = "\n\n".join(context_parts) + f"\n\nUser question: {user_message}\nAnswer:"

    try:
        reply = _call_ai(full_prompt)
        if not reply:
            return JsonResponse({"error": "AI returned an empty response. Try again."}, status=500)
        return JsonResponse({"reply": reply})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)