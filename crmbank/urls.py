from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("rm_auth.urls")),
    path("customers/", include("customers.urls")),
    path("agents/", include("agents.urls")),
    path("whatsapp/", include("whatsapp.urls")),
    path("", lambda request: redirect("rm_auth:dashboard")),
]
