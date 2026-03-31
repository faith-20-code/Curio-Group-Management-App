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
    path("subtask/create/", views.subtask_create, name="subtask_create"),
    path("subtask/<int:pk>/update/", views.subtask_update, name="subtask_update"),
    path("document/upload/", views.upload_document, name="upload_document"),
    path("document/<int:pk>/delete/", views.document_delete, name="document_delete"),
    path("member/<int:user_id>/", views.member_profile, name="member_profile"),
    #Ai Logic for URLS
    path("ai/chat/", views.ai_chat, name="ai_chat"),
    path("ai/assign-tasks/", views.ai_assign_tasks, name="ai_assign_tasks"),
]