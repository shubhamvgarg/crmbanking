import traceback
from datetime import timezone

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as tz
from django.views.decorators.http import require_http_methods, require_POST

from rm_auth.decorators import rm_login_required
from rm_auth.utils import get_authenticated_rm

from .models import AgentRun, DECISION_METHODS
from .graph.pipeline import build_initial_state, get_compiled_pipeline


@rm_login_required
@require_http_methods(["GET"])
def dashboard(request):
    rm_user = get_authenticated_rm(request)
    recent_runs = AgentRun.objects.filter(triggered_by=rm_user).order_by("-started_at")[:10]
    return render(request, "agents/dashboard.html", {
        "rm_user": rm_user,
        "decision_methods": DECISION_METHODS,
        "recent_runs": recent_runs,
    })


@rm_login_required
@require_POST
def trigger_run(request):
    rm_user = get_authenticated_rm(request)
    decision_method = request.POST.get("decision_method", "").strip()

    valid_methods = [m[0] for m in DECISION_METHODS]
    if decision_method not in valid_methods:
        messages.error(request, "Please select a valid decision method.")
        return redirect("agents:dashboard")

    # Create the run record
    run = AgentRun.objects.create(
        triggered_by=rm_user,
        decision_method=decision_method,
        status="running",
        current_stage="sql",
    )

    try:
        pipeline = get_compiled_pipeline()
        initial_state = build_initial_state(
            run_id=str(run.run_id),
            batch_offset=0,
            batch_size=int(getattr(request, "_batch_size", 100)),
            decision_method=decision_method,
        )

        final_state = pipeline.invoke(initial_state)

        # Persist results
        run.raw_users = final_state.get("raw_users", [])
        run.scored_users = final_state.get("scored_users", [])
        run.recommended_users = final_state.get("recommended_users", [])
        run.generated_messages = final_state.get("messages", [])
        run.sql_agent_log = final_state.get("sql_agent_log", "")
        run.decision_agent_log = final_state.get("decision_agent_log", "")
        run.recommendation_agent_log = final_state.get("recommendation_agent_log", "")
        run.message_agent_log = final_state.get("message_agent_log", "")
        run.current_stage = final_state.get("current_stage", "done")
        run.total_users_processed = len(run.raw_users)
        run.status = "completed"
        run.completed_at = tz.now()
        run.save()

        messages.success(
            request,
            f"Pipeline completed — "
            f"{len(run.raw_users)} fetched, "
            f"{len(run.scored_users)} scored, "
            f"{len(run.generated_messages)} messages generated."
        )

    except Exception as exc:
        error_detail = traceback.format_exc()
        run.status = "failed"
        run.errors = [str(exc), error_detail]
        run.completed_at = tz.now()
        run.save()
        messages.error(request, f"Pipeline failed: {exc}")

    return redirect("agents:run_detail", run_id=run.run_id)


@rm_login_required
@require_http_methods(["GET"])
def run_detail(request, run_id):
    run = get_object_or_404(AgentRun, run_id=run_id)
    return render(request, "agents/run_detail.html", {"run": run})


@rm_login_required
@require_http_methods(["GET"])
def run_list(request):
    rm_user = get_authenticated_rm(request)
    runs = AgentRun.objects.filter(triggered_by=rm_user).order_by("-started_at")
    return render(request, "agents/run_list.html", {"runs": runs})
