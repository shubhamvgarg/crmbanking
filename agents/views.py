import json
import traceback

from django.contrib import messages
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as tz
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from rm_auth.decorators import rm_login_required
from rm_auth.utils import get_authenticated_rm

from .graph.pipeline import build_initial_state, get_compiled_pipeline
from .models import DECISION_METHODS, AgentRun

# ── Helpers ──────────────────────────────────────────────────────────────────

_STAGE_ORDER = ["sql_agent", "decision_agent", "recommendation_agent", "message_agent"]

_STAGE_LABELS = {
    "sql_agent": "SQL Agent",
    "decision_agent": "Decision Agent",
    "recommendation_agent": "Recommendation Agent",
    "message_agent": "Message Agent",
}

_STAGE_ICONS = {
    "sql_agent": "🗄",
    "decision_agent": "🔍",
    "recommendation_agent": "💡",
    "message_agent": "✉",
}


def _sse(payload: dict) -> str:
    """Format a dict as a single SSE data line."""
    return f"data: {json.dumps(payload)}\n\n"


def _count_label(node: str, state_update: dict) -> str:
    if node == "sql_agent":
        n = len(state_update.get("raw_users", []))
        return f"{n} customers fetched"
    if node == "decision_agent":
        n = len(state_update.get("scored_users", []))
        return f"{n} candidates scored"
    if node == "recommendation_agent":
        n = len(state_update.get("recommended_users", []))
        return f"{n} offers assigned"
    if node == "message_agent":
        n = len(state_update.get("messages", []))
        return f"{n} messages generated"
    return ""


def _log_key(node: str) -> str:
    return f"{node.replace('_agent', '')}_agent_log"


# ── Views ─────────────────────────────────────────────────────────────────────

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
    """Create an AgentRun record then redirect to the live-watch page."""
    rm_user = get_authenticated_rm(request)
    decision_method = request.POST.get("decision_method", "").strip()

    valid_methods = [m[0] for m in DECISION_METHODS]
    if decision_method not in valid_methods:
        messages.error(request, "Please select a valid decision method.")
        return redirect("agents:dashboard")

    run = AgentRun.objects.create(
        triggered_by=rm_user,
        decision_method=decision_method,
        status="running",
        current_stage="sql",
    )
    return redirect("agents:watch_run", run_id=run.run_id)


@rm_login_required
@require_http_methods(["GET"])
def watch_run(request, run_id):
    """Render the live-progress page. Redirects to detail if run is already done."""
    run = get_object_or_404(AgentRun, run_id=run_id)
    if run.status in ("completed", "failed"):
        return redirect("agents:run_detail", run_id=run_id)
    return render(request, "agents/watch.html", {
        "run": run,
        "stage_order": _STAGE_ORDER,
        "stage_labels": _STAGE_LABELS,
        "stage_icons": _STAGE_ICONS,
    })


@rm_login_required
@require_http_methods(["GET"])
def stream_run(request, run_id):
    """
    SSE endpoint. Runs the LangGraph pipeline using pipeline.stream() with
    stream_mode=["updates", "messages"] so the browser sees:
      • "token" events  — individual LLM output tokens (real-time)
      • "stage_done"    — after each agent node completes
      • "done"          — when the whole pipeline finishes
      • "error"         — on failure
    """
    run = get_object_or_404(AgentRun, run_id=run_id)

    def event_stream():
        # Tell the browser which stages to expect
        yield _sse({
            "type": "init",
            "stages": _STAGE_ORDER,
            "labels": _STAGE_LABELS,
            "icons": _STAGE_ICONS,
        })

        try:
            pipeline = get_compiled_pipeline()
            initial_state = build_initial_state(
                run_id=str(run.run_id),
                batch_offset=0,
                batch_size=100,
                decision_method=run.decision_method,
            )

            # Announce the first stage is starting
            yield _sse({"type": "stage_start", "node": "sql_agent"})

            # Accumulate final state ourselves so we can save to DB
            accumulated = dict(initial_state)

            for event in pipeline.stream(initial_state, stream_mode=["updates", "messages"]):
                mode, data = event

                if mode == "messages":
                    # data = (AIMessageChunk, metadata)
                    chunk, metadata = data
                    token = getattr(chunk, "content", "")
                    node = metadata.get("langgraph_node", "")
                    if token and node in _STAGE_ORDER:
                        yield _sse({
                            "type": "token",
                            "node": node,
                            "content": token,
                        })

                elif mode == "updates":
                    # data = {node_name: state_update_dict}
                    for node, state_update in data.items():
                        if node not in _STAGE_ORDER:
                            continue

                        # Merge into accumulated state
                        accumulated.update(state_update)

                        # Announce next stage starting (if any)
                        idx = _STAGE_ORDER.index(node)
                        if idx + 1 < len(_STAGE_ORDER):
                            yield _sse({
                                "type": "stage_start",
                                "node": _STAGE_ORDER[idx + 1],
                            })

                        log = state_update.get(_log_key(node), "")

                        yield _sse({
                            "type": "stage_done",
                            "node": node,
                            "label": _STAGE_LABELS.get(node, node),
                            "count_label": _count_label(node, state_update),
                            "log": log,
                        })

            # Save final state to DB
            run.raw_users = accumulated.get("raw_users", [])
            run.scored_users = accumulated.get("scored_users", [])
            run.recommended_users = accumulated.get("recommended_users", [])
            run.generated_messages = accumulated.get("messages", [])
            run.sql_agent_log = accumulated.get("sql_agent_log", "")
            run.decision_agent_log = accumulated.get("decision_agent_log", "")
            run.recommendation_agent_log = accumulated.get("recommendation_agent_log", "")
            run.message_agent_log = accumulated.get("message_agent_log", "")
            run.current_stage = "done"
            run.total_users_processed = len(run.raw_users)
            run.status = "completed"
            run.completed_at = tz.now()
            run.save()

            yield _sse({
                "type": "done",
                "run_id": str(run.run_id),
                "total_fetched": len(run.raw_users),
                "total_scored": len(run.scored_users),
                "total_messages": len(run.generated_messages),
            })

        except Exception as exc:
            error_detail = traceback.format_exc()
            try:
                run.status = "failed"
                run.errors = [str(exc), error_detail]
                run.completed_at = tz.now()
                run.save()
            except Exception:
                pass
            yield _sse({
                "type": "error",
                "message": str(exc),
                "detail": error_detail,
            })

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


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
