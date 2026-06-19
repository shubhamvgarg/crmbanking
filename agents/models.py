import uuid

from django.db import models

from rm_auth.models import RMUser

DECISION_METHODS = [
    ("rule_based", "Rule-Based"),
    ("heuristics", "Heuristics"),
    ("ml", "ML Model"),
]

STATUS_CHOICES = [
    ("running", "Running"),
    ("paused", "Paused — awaiting RM review"),
    ("completed", "Completed"),
    ("failed", "Failed"),
]

STAGE_CHOICES = [
    ("sql", "SQL Agent"),
    ("decision", "Decision Agent"),
    ("recommendation", "Recommendation Agent"),
    ("message", "Message Agent"),
    ("done", "Done"),
]


class AgentRun(models.Model):
    run_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    triggered_by = models.ForeignKey(
        RMUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="agent_runs",
    )
    decision_method = models.CharField(max_length=20, choices=DECISION_METHODS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    current_stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="sql")
    batch_offset = models.IntegerField(default=0)
    total_users_processed = models.IntegerField(default=0)

    # Agent outputs stored as JSON
    raw_users = models.JSONField(default=list)
    scored_users = models.JSONField(default=list)
    recommended_users = models.JSONField(default=list)
    generated_messages = models.JSONField(default=list)
    errors = models.JSONField(default=list)

    # LLM reasoning logs per stage (for display)
    sql_agent_log = models.TextField(blank=True)
    decision_agent_log = models.TextField(blank=True)
    recommendation_agent_log = models.TextField(blank=True)
    message_agent_log = models.TextField(blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Agent Run"
        verbose_name_plural = "Agent Runs"
        ordering = ["-started_at"]

    def __str__(self):
        return f"Run {str(self.run_id)[:8]} — {self.get_decision_method_display()} — {self.get_status_display()}"
