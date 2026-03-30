from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView
from django.contrib.auth.models import User
from .models import Work, SubTask, Group, Document, Profile
from .forms import (
    SignupForm, GroupForm, AddMembersForm, WorkForm,
    SubTaskForm, SubTaskProgressForm, LeaderDocumentForm, MemberDocumentForm
)


# ── Home ──────────────────────────────────────────────────────────────────────

def home(request):
    return render(request, "index.html")


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
            return redirect("dashboard")   # one dashboard, handles both roles
        error = "Invalid username or password."
    return render(request, "login.html", {"error": error})


def signup_view(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.create_user(
            username=form.cleaned_data["username"],
            email=form.cleaned_data["email"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
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


# ── Shared dashboard (leader + member) ───────────────────────────────────────

@login_required(login_url="login")
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    is_leader = profile.is_leader

    leader_groups = Group.objects.filter(leader=request.user)
    member_group = Group.objects.filter(members=request.user).first()

    if is_leader:
        group_id = request.GET.get("group")
        selected_group = None
        if group_id:
            selected_group = leader_groups.filter(id=group_id).first()
        selected_group = selected_group or leader_groups.first()
        group = selected_group
    else:
        group = member_group

    works = Work.objects.filter(group=group) if group else Work.objects.none()
    documents = Document.objects.filter(group=group) if group else Document.objects.none()

    if is_leader:
        subtasks = SubTask.objects.filter(work__group=group) if group else SubTask.objects.none()
    else:
        subtasks = SubTask.objects.filter(assigned_to=request.user)

    if subtasks.exists():
        completed_count = subtasks.filter(status='completed').count()
        total_count = subtasks.count()
        task_completion_percentage = (completed_count / total_count * 100) if total_count > 0 else 0
    else:
        task_completion_percentage = 0

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
        # Promote user to leader
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
    return render(request, "subtask_form.html", {
        "form": form,
        "title": "Assign Task",
    })


@login_required(login_url="login")
def subtask_update(request, pk):
    """Member updates their task completion percentage."""
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
    form = FormClass(request.POST or None, request.FILES or None)

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
    # Allow delete if user is the uploader or the leader of the group
    if request.user == doc.uploaded_by or Group.objects.filter(leader=request.user, pk=doc.group.pk).exists():
        doc.delete()
    return redirect("dashboard")


# ── Member Profile View ───────────────────────────────────────────────────────

@login_required(login_url="login")
def member_profile(request, user_id):
    """Leader views a member's profile."""
    member = get_object_or_404(User, pk=user_id)
    profile, _ = Profile.objects.get_or_create(user=member)
    # Get the group where the member belongs (assuming one group per member for simplicity)
    group = Group.objects.filter(members=member).first()
    if not group:
        # If no group, perhaps redirect or show empty
        subtasks = SubTask.objects.none()
        documents = Document.objects.none()
    else:
        subtasks = SubTask.objects.filter(assigned_to=member, work__group=group)
        documents = Document.objects.filter(uploaded_by=member, group=group)
    return render(request, "member_profile.html", {
        "member": member,
        "profile": profile,
        "subtasks": subtasks,
        "documents": documents,
        "group": group,
    })