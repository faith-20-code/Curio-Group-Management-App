from django.urls import path

from .views import *

urlpatterns = [
    path('', home, name='home'),
    path('login/', login, name='login'),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("group/create/", GroupCreateView.as_view(), name="group_create"),
    path("work/create/", WorkCreateView.as_view(), name="work_create"),
    path("subtask/create/", SubTaskCreateView.as_view(), name="subtask_create"),
]