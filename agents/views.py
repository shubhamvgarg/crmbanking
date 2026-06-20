import json
import traceback

from django.contrib import messages
from django.conf import settings
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone as tz
from django.views.decorators.http import require_http_methods, require_POST

from rm_auth.decorators import rm_login_required
from rm_auth.utils import get_authenticated_rm

from .graph.pipeline import (
    build_initial_state,
    get_compiled_pipeline,
    get_thread_config,
)
from .models import DECISION_METHODS, AgentRun, HumanReview

# ── Stage metadata ────────────────────────────────────────────────────────────

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

# Maps "interrupted-before X" → "which stage just finished"
_STAGE_BEFORE = {
    "decision_agent": "sql_agent",
    "recommendation_agent": "decision_agent",
    "message_agent": "recommendation_agent",
}

# Maps stage → the AgentRun JSONField that holds its output
_RUN_FIELD = {
    "sql_agent": "raw_users",
    "decision_agent": "scored_users",
    "recommendation_agent": "recommended_users",
    "message_agent": "generated_messages",
}

# Maps stage → the AgentPipelineState key for its output
_STATE_KEY = {
    "sql_agent": "raw_users",
    "decision_agent": "scored_users",
    "recommendation_agent": "recommended_users",
    "message_agent": "messages",
}

_CURRENT_STAGE_TO_REVIEW_STAGE = {
    "sql": "sql_agent",
    "decision": "decision_agent",
    "recommendation": "recommendation_agent",
    "message": "message_agent",
}

# ── Helpers ───────────────────────────────────────────────────────────────────


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _count_label(node: str, state_values: dict) -> str:
    mapping = {
        "sql_agent": ("raw_users", "customers fetched"),
        "decision_agent": ("scored_users", "candidates scored"),
        "recommendation_agent": ("recommended_users", "offers assigned"),
        "message_agent": ("messages", "messages generated"),
    }
    if node in mapping:
        key, label = mapping[node]
        return f"{len(state_values.get(key, []))} {label}"
    return ""


def _log_key(node: str) -> str:
    return f"{node.replace('_agent', '')}_agent_log"


def _save_partial_state(run: AgentRun, completed_stage: str, state_vals: dict) -> None:
    """Persist whatever the pipeline has produced so far to the AgentRun row."""
    run.raw_users = state_vals.get("raw_users", run.raw_users)
    run.scored_users = state_vals.get("scored_users", run.scored_users)
    run.recommended_users = state_vals.get("recommended_users", run.recommended_users)
    run.generated_messages = state_vals.get("messages", run.generated_messages)
    run.sql_agent_log = state_vals.get("sql_agent_log", run.sql_agent_log or "")
    run.decision_agent_log = state_vals.get("decision_agent_log", run.decision_agent_log or "")
    run.recommendation_agent_log = state_vals.get("recommendation_agent_log", run.recommendation_agent_log or "")
    run.message_agent_log = state_vals.get("message_agent_log", run.message_agent_log or "")
    stage_short = completed_stage.replace("_agent", "")
    run.current_stage = stage_short
    run.status = "paused"
    run.save()


def _save_final_state(run: AgentRun, state_vals: dict) -> None:
    """Save completed pipeline state before issuing the message-review event."""
    run.raw_users = state_vals.get("raw_users", run.raw_users)
    run.scored_users = state_vals.get("scored_users", run.scored_users)
    run.recommended_users = state_vals.get("recommended_users", run.recommended_users)
    run.generated_messages = state_vals.get("messages", [])
    run.sql_agent_log = state_vals.get("sql_agent_log", "")
    run.decision_agent_log = state_vals.get("decision_agent_log", "")
    run.recommendation_agent_log = state_vals.get("recommendation_agent_log", "")
    run.message_agent_log = state_vals.get("message_agent_log", "")
    run.current_stage = "message"
    run.status = "paused"
    run.save()


def _get_pending_review_stage(run: AgentRun) -> str:
    """Return the review stage matching a paused AgentRun's current_stage."""
    return _CURRENT_STAGE_TO_REVIEW_STAGE.get(run.current_stage, "sql_agent")


def _publish_approved_messages(run: AgentRun, approved_data: list[dict]) -> list[dict]:
    """Publish RM-approved final messages to RabbitMQ and annotate queue status."""
    from message_queue.rabbitmq import enqueue_message

    published = []
    for item in approved_data:
        queued = enqueue_message(item, run=run, batch_offset=run.batch_offset)
        published.append({
            **item,
            "queued": queued.status == "published",
            "queue_status": queued.status,
            "queued_message_id": str(queued.message_id),
            "queue_error": queued.last_error,
        })
    return published


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
    run = get_object_or_404(AgentRun, run_id=run_id)
    if run.status == "completed":
        return redirect("agents:run_detail", run_id=run_id)
    return render(request, "agents/watch.html", {
        "run": run,
        "stage_order": _STAGE_ORDER,
        "stage_labels": _STAGE_LABELS,
        "stage_icons": _STAGE_ICONS,
    })


@rm_login_required
@require_http_methods(["GET"])
def continue_run(request, run_id):
    """
    Continue a run from its current persisted state.

    - paused: send the RM to the pending review screen
    - running: send the RM back to the live watch screen
    - completed/failed: show the run detail
    """
    run = get_object_or_404(AgentRun, run_id=run_id)

    if run.status == "paused":
        stage = _get_pending_review_stage(run)
        messages.info(request, f"Continue by reviewing {_STAGE_LABELS.get(stage, stage)} output.")
        return redirect("agents:review_stage", run_id=run_id, stage=stage)

    if run.status == "running":
        return redirect("agents:watch_run", run_id=run_id)

    return redirect("agents:run_detail", run_id=run_id)


@rm_login_required
@require_http_methods(["GET"])
def stream_run(request, run_id):
    """
    SSE endpoint — runs (or resumes) the LangGraph pipeline for a given run.

    Events emitted:
      init          — first-ever batch; lists stage order/labels/icons
      resume        — picking up after an RM review; which stages are already done
      stage_start   — a node is about to execute
      token         — individual LLM output token
      stage_done    — a node finished; carries count_label and reasoning log
      review_needed — pipeline interrupted; RM must review before continuing
                      OR all 4 stages done; RM must review generated messages
      done          — entire run complete (all batches exhausted)
      error         — unhandled exception
    """
    run = get_object_or_404(AgentRun, run_id=run_id)
    config = get_thread_config(str(run.run_id), run.batch_offset)

    def event_stream():
        # Send a keepalive comment immediately so the browser knows
        # the SSE connection is live before the pipeline starts.
        yield ": keep-alive\n\n"
        try:
            pipeline = get_compiled_pipeline()
            existing = pipeline.get_state(config)

            if existing.values and existing.next:
                # Resuming after an RM review — tell JS which stages are done
                idx = _STAGE_ORDER.index(existing.next[0]) if existing.next[0] in _STAGE_ORDER else len(_STAGE_ORDER)
                completed_stages = _STAGE_ORDER[:idx]
                completed_info = [
                    {
                        "node": n,
                        "count_label": _count_label(n, existing.values),
                        "log": existing.values.get(_log_key(n), ""),
                    }
                    for n in completed_stages
                ]
                yield _sse({"type": "resume", "completed": completed_info})
                yield _sse({"type": "stage_start", "node": existing.next[0]})
                input_state = None
            else:
                # Fresh batch start
                input_state = build_initial_state(
                    run_id=str(run.run_id),
                    batch_offset=run.batch_offset,
                    batch_size=settings.AGENT_BATCH_SIZE,
                    decision_method=run.decision_method,
                )
                yield _sse({
                    "type": "init",
                    "stages": _STAGE_ORDER,
                    "labels": _STAGE_LABELS,
                    "icons": _STAGE_ICONS,
                    "batch_offset": run.batch_offset,
                })
                yield _sse({"type": "stage_start", "node": "sql_agent"})

            accumulated = {}

            for event in pipeline.stream(input_state, config, stream_mode=["updates", "messages"]):
                mode, data = event

                if mode == "messages":
                    chunk, metadata = data
                    token = getattr(chunk, "content", "")
                    node = metadata.get("langgraph_node", "")
                    if token and node in _STAGE_ORDER:
                        yield _sse({"type": "token", "node": node, "content": token})

                elif mode == "updates":
                    for node, state_update in data.items():
                        if node not in _STAGE_ORDER:
                            continue
                        accumulated.update(state_update)

                        # Announce the next stage starting (if there is one)
                        idx = _STAGE_ORDER.index(node)
                        if idx + 1 < len(_STAGE_ORDER):
                            yield _sse({"type": "stage_start", "node": _STAGE_ORDER[idx + 1]})

                        yield _sse({
                            "type": "stage_done",
                            "node": node,
                            "label": _STAGE_LABELS.get(node, node),
                            "count_label": _count_label(node, state_update),
                            "log": state_update.get(_log_key(node), ""),
                        })

            # ── Post-stream analysis ──────────────────────────────────────
            final = pipeline.get_state(config)
            state_vals = {**existing.values, **accumulated} if existing.values else accumulated

            if final.next:
                # Interrupted before a node — RM must review the preceding stage
                next_node = final.next[0]
                completed_stage = _STAGE_BEFORE.get(next_node, "sql_agent")
                _save_partial_state(run, completed_stage, state_vals)
                yield _sse({
                    "type": "review_needed",
                    "stage": completed_stage,
                    "next_stage": next_node,
                    "stage_label": _STAGE_LABELS.get(completed_stage, completed_stage),
                    "count": len(state_vals.get(_STATE_KEY[completed_stage], [])),
                    "review_url": reverse("agents:review_stage", args=[run_id, completed_stage]),
                })
            else:
                # All 4 nodes ran — save final state, ask RM to review messages
                _save_final_state(run, state_vals)
                from customers.models import CustomerProfile
                total = CustomerProfile.objects.count()
                next_offset = run.batch_offset + settings.AGENT_BATCH_SIZE
                yield _sse({
                    "type": "review_needed",
                    "stage": "message_agent",
                    "next_stage": None,
                    "stage_label": "Message Agent",
                    "count": len(state_vals.get("messages", [])),
                    "review_url": reverse("agents:review_stage", args=[run_id, "message_agent"]),
                    "has_next_batch": next_offset < total,
                    "next_batch_offset": next_offset if next_offset < total else None,
                    "total_customers": total,
                })

        except Exception as exc:
            detail = traceback.format_exc()
            try:
                run.status = "failed"
                run.errors = [str(exc), detail]
                run.completed_at = tz.now()
                run.save()
            except Exception:
                pass
            yield _sse({"type": "error", "message": str(exc), "detail": detail})

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# ── Human-in-the-Loop review ──────────────────────────────────────────────────

_LOAN_OFFERS = [
    "Premium Personal Loan",
    "Pre-Approved Loan",
    "Small Starter Loan",
    "Debt Consolidation Loan",
    "Loyalty Rate Loan",
    "Salary Advance Loan",
]


@rm_login_required
@require_http_methods(["GET"])
def review_stage(request, run_id, stage):
    run = get_object_or_404(AgentRun, run_id=run_id)
    if stage not in _RUN_FIELD:
        messages.error(request, f"Unknown review stage: {stage}")
        return redirect("agents:run_detail", run_id=run_id)

    data = getattr(run, _RUN_FIELD[stage], [])
    return render(request, "agents/review_stage.html", {
        "run": run,
        "stage": stage,
        "stage_label": _STAGE_LABELS.get(stage, stage),
        "stage_icon": _STAGE_ICONS.get(stage, ""),
        "data": data,
        "loan_offers": _LOAN_OFFERS,
    })


@rm_login_required
@require_POST
def submit_review(request, run_id, stage):
    """
    Process the RM's review decision for a given stage.

    For mid-pipeline stages (sql / decision / recommendation):
      • Filter data to RM-approved entries
      • Optionally apply RM edits to offers (recommendation_agent)
      • Update LangGraph state so the next node uses reviewed data
      • Redirect to watch_run to resume pipeline

    For the final stage (message_agent):
      • Filter messages to RM-approved entries
      • Optionally apply RM edits to message text
      • Check if more customer batches remain
        – Yes → increment batch_offset, redirect to watch_run for next batch
        – No  → mark run completed, redirect to run_detail
    """
    run = get_object_or_404(AgentRun, run_id=run_id)
    rm_user = get_authenticated_rm(request)

    if stage not in _RUN_FIELD:
        messages.error(request, "Invalid stage.")
        return redirect("agents:run_detail", run_id=run_id)

    original_data = getattr(run, _RUN_FIELD[stage], [])

    # ── Collect approved IDs from checkboxes ─────────────────────────────────
    approved_ids_raw = set(request.POST.getlist("approved_ids"))

    # Determine the ID key used in this stage's output dicts
    def _get_id(entry: dict) -> str:
        return str(
            entry.get("customer_id")
            or entry.get("id")
            or entry.get("cid", "")
        )

    approved_data = [e for e in original_data if _get_id(e) in approved_ids_raw]
    removed_ids = [_get_id(e) for e in original_data if _get_id(e) not in approved_ids_raw]

    # ── Apply RM edits for editable stages ───────────────────────────────────
    if stage == "recommendation_agent":
        for entry in approved_data:
            cid = _get_id(entry)
            new_offer = request.POST.get(f"offer_{cid}", "").strip()
            if new_offer:
                entry["recommended_offer"] = new_offer
            # Persist edit back to AgentRun.recommended_users too
        run.recommended_users = approved_data

    elif stage == "message_agent":
        for entry in approved_data:
            cid = _get_id(entry)
            new_msg = request.POST.get(f"message_{cid}", "").strip()
            if new_msg:
                entry["message"] = new_msg
        approved_data = _publish_approved_messages(run, approved_data)
        run.generated_messages = approved_data

    # ── Save HumanReview record ───────────────────────────────────────────────
    HumanReview.objects.update_or_create(
        run=run,
        stage=stage,
        batch_offset=run.batch_offset,
        defaults={
            "original_data": original_data,
            "approved_data": approved_data,
            "removed_ids": removed_ids,
            "reviewed_by": rm_user,
        },
    )

    # ── Route by stage type ───────────────────────────────────────────────────
    if stage != "message_agent":
        # Mid-pipeline: update LangGraph state then resume
        config = get_thread_config(str(run.run_id), run.batch_offset)
        pipeline = get_compiled_pipeline()
        pipeline.update_state(config, {_STATE_KEY[stage]: approved_data})

        # Advance current_stage label
        stage_short_next = {
            "sql_agent": "decision",
            "decision_agent": "recommendation",
            "recommendation_agent": "message",
        }
        run.current_stage = stage_short_next.get(stage, "done")
        run.status = "running"
        run.save()
        return redirect("agents:watch_run", run_id=run_id)

    else:
        # Final stage: decide whether to start next batch or complete the run
        from customers.models import CustomerProfile
        total = CustomerProfile.objects.count()
        next_offset = run.batch_offset + settings.AGENT_BATCH_SIZE

        if next_offset < total:
            run.batch_offset = next_offset
            run.status = "running"
            run.current_stage = "sql"
            # Accumulate totals across batches
            run.total_users_processed = next_offset
            run.save()
            messages.info(
                request,
                f"Batch approved. Starting next batch (offset {next_offset} / {total}).",
            )
            return redirect("agents:watch_run", run_id=run_id)
        else:
            run.total_users_processed = total
            run.status = "completed"
            run.completed_at = tz.now()
            run.save()
            messages.success(request, "All batches processed. Pipeline complete!")
            return redirect("agents:run_detail", run_id=run_id)


# ── Run history ───────────────────────────────────────────────────────────────

@rm_login_required
@require_http_methods(["GET"])
def run_detail(request, run_id):
    run = get_object_or_404(AgentRun, run_id=run_id)
    reviews = run.reviews.order_by("batch_offset", "stage")
    queued_messages = run.queued_messages.select_related("whatsapp_delivery").order_by("-created_at")
    return render(request, "agents/run_detail.html", {
        "run": run,
        "reviews": reviews,
        "queued_messages": queued_messages,
    })


@rm_login_required
@require_http_methods(["GET"])
def run_list(request):
    rm_user = get_authenticated_rm(request)
    runs = AgentRun.objects.filter(triggered_by=rm_user).order_by("-started_at")
    return render(request, "agents/run_list.html", {"runs": runs})
