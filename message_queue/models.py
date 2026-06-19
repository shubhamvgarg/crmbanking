import uuid

from django.db import models

from agents.models import AgentRun


class QueuedMessage(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("published", "Published"),
        ("publish_failed", "Publish Failed"),
        ("consumed", "Consumed"),
        ("failed", "Failed"),
    ]

    message_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        AgentRun,
        on_delete=models.CASCADE,
        related_name="queued_messages",
        null=True,
        blank=True,
    )
    batch_offset = models.IntegerField(default=0)
    customer_id = models.CharField(max_length=30)
    customer_name = models.CharField(max_length=120, blank=True)
    whatsapp_number = models.CharField(max_length=30)
    offer = models.CharField(max_length=120, blank=True)
    message = models.TextField()
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    retry_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Queued Message"
        verbose_name_plural = "Queued Messages"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["run", "batch_offset"]),
        ]

    def __str__(self):
        return f"{str(self.message_id)[:8]} — {self.customer_id} — {self.status}"


class DeliveryLog(models.Model):
    EVENT_CHOICES = [
        ("publish_attempt", "Publish Attempt"),
        ("published", "Published"),
        ("publish_failed", "Publish Failed"),
        ("consumed", "Consumed"),
        ("consume_failed", "Consume Failed"),
    ]

    queued_message = models.ForeignKey(
        QueuedMessage,
        on_delete=models.CASCADE,
        related_name="delivery_logs",
        null=True,
        blank=True,
    )
    event = models.CharField(max_length=30, choices=EVENT_CHOICES)
    detail = models.TextField(blank=True)
    payload_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Delivery Log"
        verbose_name_plural = "Delivery Logs"
        ordering = ["-created_at"]

    def __str__(self):
        msg = self.queued_message_id or "external"
        return f"{self.event} — {msg}"
