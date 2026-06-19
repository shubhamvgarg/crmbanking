from django.contrib import admin
from django.utils.html import format_html

from .models import AgentRun


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = (
        "short_id", "triggered_by", "decision_method",
        "status", "current_stage", "batch_offset",
        "total_users_processed", "started_at",
    )
    list_filter = ("status", "decision_method", "current_stage")
    readonly_fields = (
        "run_id", "triggered_by", "started_at", "completed_at",
        "raw_users", "scored_users", "recommended_users",
        "generated_messages", "errors",
        "sql_agent_log", "decision_agent_log",
        "recommendation_agent_log", "message_agent_log",
    )

    def short_id(self, obj):
        return str(obj.run_id)[:8]
    short_id.short_description = "Run ID"
