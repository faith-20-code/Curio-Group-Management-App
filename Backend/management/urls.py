from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),

    path("group/create/", views.group_create, name="group_create"),
    path("group/<int:group_id>/add-members/", views.group_add_members, name="group_add_members"),

    path("work/create/", views.work_create, name="work_create"),
    path("work/<int:pk>/", views.work_detail, name="work_detail"),

    # Manual assignment
    path("subtask/create/", views.subtask_create, name="subtask_create"),

    # Step-level actions (replaces old subtask/<pk>/update/ percentage slider)
    path("subtask/<int:subtask_id>/steps/generate/", views.ai_generate_steps, name="ai_generate_steps"),
    path("subtask/<int:subtask_id>/steps/add/", views.subtask_step_add, name="subtask_step_add"),
    path("step/<int:step_id>/toggle/", views.subtask_step_toggle, name="subtask_step_toggle"),

    path("document/upload/", views.upload_document, name="upload_document"),
    path("document/<int:pk>/delete/", views.document_delete, name="document_delete"),
    path("member/<int:user_id>/", views.member_profile, name="member_profile"),
    path("member/<int:user_id>/tasks/", views.member_tasks, name="member_tasks"),

    # Tabbed task previews ("...more" destination)
    path("tasks/<str:status>/", views.task_list_view, name="task_list_view"),

    # AI
    path("ai/chat/", views.ai_chat, name="ai_chat"),
    path("ai/assign-tasks/", views.ai_assign_tasks, name="ai_assign_tasks"),
]