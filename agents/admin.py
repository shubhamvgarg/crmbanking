from django.contrib import admin

from .models import AgentRun, HumanReview


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


@admin.register(HumanReview)
class HumanReviewAdmin(admin.ModelAdmin):
    list_display = ("run", "stage", "batch_offset", "reviewed_by", "reviewed_at",
                    "original_count", "approved_count", "removed_count")
    list_filter = ("stage",)
    readonly_fields = ("run", "reviewed_by", "reviewed_at", "original_data",
                       "approved_data", "removed_ids")

    def original_count(self, obj):
        return len(obj.original_data)
    original_count.short_description = "Original"

    def approved_count(self, obj):
        return len(obj.approved_data)
    approved_count.short_description = "Approved"

    def removed_count(self, obj):
        return len(obj.removed_ids)
    removed_count.short_description = "Removed"
