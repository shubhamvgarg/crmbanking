from django.contrib import admin

from .models import DeliveryLog, QueuedMessage


class DeliveryLogInline(admin.TabularInline):
    model = DeliveryLog
    extra = 0
    readonly_fields = ("event", "detail", "payload_snapshot", "created_at")
    can_delete = False


@admin.register(QueuedMessage)
class QueuedMessageAdmin(admin.ModelAdmin):
    list_display = (
        "short_id", "run", "customer_id", "customer_name",
        "status", "retry_count", "published_at", "consumed_at", "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("customer_id", "customer_name", "whatsapp_number", "offer")
    readonly_fields = (
        "message_id", "payload", "retry_count", "last_error",
        "published_at", "consumed_at", "created_at", "updated_at",
    )
    inlines = [DeliveryLogInline]

    def short_id(self, obj):
        return str(obj.message_id)[:8]
    short_id.short_description = "Message ID"


@admin.register(DeliveryLog)
class DeliveryLogAdmin(admin.ModelAdmin):
    list_display = ("event", "queued_message", "created_at")
    list_filter = ("event", "created_at")
    readonly_fields = ("queued_message", "event", "detail", "payload_snapshot", "created_at")
