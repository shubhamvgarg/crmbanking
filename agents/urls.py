from django.urls import path

from . import views

app_name = "agents"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("run/", views.trigger_run, name="trigger_run"),
    path("run/<uuid:run_id>/watch/", views.watch_run, name="watch_run"),
    path("run/<uuid:run_id>/stream/", views.stream_run, name="stream_run"),
    path("run/<uuid:run_id>/", views.run_detail, name="run_detail"),
    path("runs/", views.run_list, name="run_list"),
]
