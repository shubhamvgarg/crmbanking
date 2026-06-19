from django.contrib import admin

from .models import WhatsAppDelivery


@admin.register(WhatsAppDelivery)
class WhatsAppDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "message_sid", "queued_message", "to_number",
        "status", "sent_at", "delivered_at", "failed_at", "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("message_sid", "to_number", "queued_message__customer_id")
    readonly_fields = (
        "queued_message", "message_sid", "to_number", "from_number", "body",
        "raw_callback", "created_at", "updated_at",
    )
