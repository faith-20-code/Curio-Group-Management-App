from django.urls import path

from .views import *

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("group/create/", GroupCreateView.as_view(), name="group_create"),
    path("work/create/", WorkCreateView.as_view(), name="work_create"),
    path("subtask/create/", SubTaskCreateView.as_view(), name="subtask_create"),
]


urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login, name='login'),

]