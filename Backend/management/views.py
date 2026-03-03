from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from .models import Work, SubTask, Group
from django.views.generic import CreateView
from django.urls import reverse_lazy



class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        group = Group.objects.filter(
            members=self.request.user
        ).first()

        context["group"] = group

        if group:
            context["works"] = Work.objects.filter(group=group)

        context["subtasks"] = SubTask.objects.filter(
            assigned_to=self.request.user
        )

        return context
    


class GroupCreateView(LoginRequiredMixin, CreateView):
    model = Group
    fields = ["name", "members"]

    template_name = "group_create.html"
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        form.instance.leader = self.request.user
        return super().form_valid(form)
    


class WorkCreateView(LoginRequiredMixin, CreateView):
    model = Work
    fields = ["title", "description"]

    template_name = "work_create.html"
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        group = Group.objects.filter(
            leader=self.request.user
        ).first()

        form.instance.group = group
        form.instance.created_by = self.request.user

        return super().form_valid(form)
    


class SubTaskCreateView(LoginRequiredMixin, CreateView):
    model = SubTask
    fields = ["work", "title", "assigned_to"]

    template_name = "subtask_create.html"
    success_url = reverse_lazy("dashboard")

    def get_form(self):
        form = super().get_form()

        # Only allow group members
        user_group = Group.objects.filter(
            members=self.request.user
        ).first()

        if user_group:
            form.fields["assigned_to"].queryset = user_group.members.all()

            form.fields["work"].queryset = Work.objects.filter(
                group=user_group
            )

        return form