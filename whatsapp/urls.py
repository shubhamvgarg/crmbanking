from django.urls import path

from . import views

app_name = "whatsapp"

urlpatterns = [
    path("webhook/", views.status_webhook, name="status_webhook"),
    path("delivery-log/", views.delivery_log, name="delivery_log"),
]
