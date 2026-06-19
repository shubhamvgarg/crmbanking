from django.db import models

from message_queue.models import QueuedMessage


class WhatsAppDelivery(models.Model):
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("read", "Read"),
        ("failed", "Failed"),
        ("undelivered", "Undelivered"),
    ]

    queued_message = models.OneToOneField(
        QueuedMessage,
        on_delete=models.CASCADE,
        related_name="whatsapp_delivery",
        null=True,
        blank=True,
    )
    message_sid = models.CharField(max_length=80, unique=True)
    to_number = models.CharField(max_length=30)
    from_number = models.CharField(max_length=30)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    error_code = models.CharField(max_length=30, blank=True)
    error_message = models.TextField(blank=True)
    raw_callback = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "WhatsApp Delivery"
        verbose_name_plural = "WhatsApp Deliveries"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.message_sid} — {self.status}"
