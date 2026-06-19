from django.urls import path

from . import views

app_name = "agents"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("run/", views.trigger_run, name="trigger_run"),
    path("run/<uuid:run_id>/continue/", views.continue_run, name="continue_run"),
    path("run/<uuid:run_id>/watch/", views.watch_run, name="watch_run"),
    path("run/<uuid:run_id>/stream/", views.stream_run, name="stream_run"),
    path("run/<uuid:run_id>/review/<str:stage>/", views.review_stage, name="review_stage"),
    path("run/<uuid:run_id>/review/<str:stage>/submit/", views.submit_review, name="submit_review"),
    path("run/<uuid:run_id>/", views.run_detail, name="run_detail"),
    path("runs/", views.run_list, name="run_list"),
]
