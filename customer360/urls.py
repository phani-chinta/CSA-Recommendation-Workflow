from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from segments import views
urlpatterns = [path("health/live",views.health_live,name="health_live"),path("health/ready",views.health_ready,name="health_ready"),path("accounts/login/",auth_views.LoginView.as_view(template_name="registration/login.html"),name="login"),path("accounts/logout/",auth_views.LogoutView.as_view(),name="logout"),path("admin/", admin.site.urls), path("", views.dashboard, name="dashboard"), path("customers/", views.customers, name="customers"), path("customers/<str:customer_id>/", views.customer_detail, name="customer_detail"),path("customers/<str:customer_id>/cases/new/",views.support_case_create,name="support_case_create"), path("actions/", views.actions, name="actions"), path("evaluation/", views.evaluation, name="evaluation"), path("outcomes/<str:outcome_id>/transition/",views.outcome_transition,name="outcome_transition"),path("cases/<str:case_id>/transition/",views.support_case_transition,name="support_case_transition"),path("exports/<str:kind>/", views.export_data, name="export_data")]

