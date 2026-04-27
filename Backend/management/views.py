from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from .models import Work, SubTask, Group, Document, Profile
from .forms import (
    SignupForm, GroupForm, AddMembersForm, WorkForm,
    SubTaskForm, SubTaskProgressForm, LeaderDocumentForm, MemberDocumentForm
)



# Change this line at the top of views.py


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

    print("OR STATUS:", response.status_code)
    print("OR RAW:", response.text[:300])

    try:
        data = response.json()
    except Exception:
        raise Exception(f"Non-JSON response: {response.text[:200]}")

    if "choices" in data:
        content = data["choices"][0]["message"]["content"].strip()
        print("OR CONTENT:", content[:300])
        return content

    if "error" in data:
        raise Exception(str(data["error"]))

    raise Exception(f"Unexpected response: {str(data)[:200]}")

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
        SubTask.objects.filter(work__group=group)
        if is_leader and group
        else SubTask.objects.filter(assigned_to=request.user)
    )

    total = subtasks.count()
    completed = subtasks.filter(status="completed").count()
    task_completion_percentage = round(completed / total * 100) if total > 0 else 0

    return render(request, "dashboard.html", {
        "group": group,
        "leader_groups": leader_groups,
        "works": works,
        "subtasks": subtasks,
        "documents": documents,
        "is_leader": is_leader,
        "task_completion_percentage": task_completion_percentage,
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

# ── SubTask ───────────────────────────────────────────────────────────────────

@login_required(login_url="login")
def subtask_create(request):
    form = SubTaskForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("dashboard")
    return render(request, "subtask_form.html", {"form": form, "title": "Assign Task"})


@login_required(login_url="login")
def subtask_update(request, pk):
    subtask = get_object_or_404(SubTask, pk=pk, assigned_to=request.user)
    form = SubTaskProgressForm(request.POST or None, instance=subtask)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("dashboard")
    return render(request, "subtask_progress.html", {"form": form, "subtask": subtask})

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


@login_required(login_url="login")
def document_delete(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if request.user == doc.uploaded_by or Group.objects.filter(leader=request.user, pk=doc.group.pk).exists():
        doc.delete()
    return redirect("dashboard")

# ── Member Profile ────────────────────────────────────────────────────────────

@login_required(login_url="login")
def member_profile(request, user_id):
    member = get_object_or_404(User, pk=user_id)
    profile, _ = Profile.objects.get_or_create(user=member)
    group = Group.objects.filter(members=member).first()
    subtasks = SubTask.objects.filter(assigned_to=member, work__group=group) if group else SubTask.objects.none()
    documents = Document.objects.filter(uploaded_by=member, group=group) if group else Document.objects.none()
    return render(request, "member_profile.html", {
        "member": member,
        "profile": profile,
        "subtasks": subtasks,
        "documents": documents,
        "group": group,
    })

# ── Document text extractor ───────────────────────────────────────────────────

def _extract_document_text(doc):
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

# ── AI: auto-assign tasks ─────────────────────────────────────────────────────

@require_POST
@login_required(login_url="login")
def ai_assign_tasks(request):
    try:
        body = json.loads(request.body)
        work_id = body.get("work_id")
        doc_id = body.get("doc_id")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request."}, status=400)

    group = Group.objects.filter(leader=request.user).first()
    if not group:
        return JsonResponse({"error": "No group found."}, status=403)

    work = get_object_or_404(Work, id=work_id, group=group)

    if doc_id:
        doc = get_object_or_404(Document, id=doc_id, group=group)
    else:
        # Priority 1: doc tied to this specific work
        doc = Document.objects.filter(
            group=group, work=work, uploaded_by=request.user
        ).order_by("-uploaded_at").first()
        # Priority 2: any leader doc in the group
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
        member_list.append({
            "username": m.username,
            "user_id": m.id,
            "skills": p.skills or "general",
        })

    members_text = "\n".join(
        f"- {m['username']} (skills: {m['skills']})" for m in member_list
    )

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
  {{"title": "Subtask name", "assigned_to": "username"}},
  {{"title": "Another subtask", "assigned_to": "username"}}
]"""

    raw = ""
    try:
        raw = _call_ai(prompt)
        if not raw:
            return JsonResponse({"error": "AI returned an empty response."}, status=500)

        # Strip markdown fences if model adds them anyway
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        # Find the JSON array even if model adds text before/after
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return JsonResponse(
                {"error": f"No JSON array found in AI response: {raw[:200]}"},
                status=500,
            )
        raw = raw[start:end]

        subtask_suggestions = json.loads(raw)

    except json.JSONDecodeError as e:
        return JsonResponse(
            {"error": f"AI returned invalid JSON: {str(e)}. Raw: {raw[:200]}"},
            status=500,
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    member_lookup = {m["username"]: m["user_id"] for m in member_list}
    created = []

    for item in subtask_suggestions:
        title = item.get("title", "").strip()
        username = item.get("assigned_to", "").strip()
        user_id = member_lookup.get(username)

        if not title or not user_id:
            continue

        assigned_user = User.objects.filter(id=user_id).first()
        if not assigned_user:
            continue

        subtask = SubTask.objects.create(
            work=work,
            title=title,
            assigned_to=assigned_user,
            status="pending",
            completion_percentage=0,
        )
        created.append({
            "id": subtask.id,
            "title": subtask.title,
            "assigned_to": assigned_user.username,
            "status": subtask.get_status_display(),
        })

    if not created:
        return JsonResponse(
            {"error": "AI could not match tasks to members. Make sure member skills are filled in."},
            status=400,
        )

    return JsonResponse({"subtasks": created, "count": len(created)})