from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from twilio.rest import Client

from message_queue.models import DeliveryLog, QueuedMessage

from .models import WhatsAppDelivery


class TwilioConfigurationError(RuntimeError):
    pass


def _require_twilio_settings():
    missing = [
        name
        for name in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM")
        if not getattr(settings, name, "")
    ]
    if missing:
        raise TwilioConfigurationError(f"Missing Twilio settings: {', '.join(missing)}")


def _status_callback_url() -> str:
    configured = getattr(settings, "TWILIO_STATUS_CALLBACK_URL", "")
    if configured:
        return configured
    base_url = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
    if not base_url:
        return ""
    return f"{base_url}{reverse('whatsapp:status_webhook')}"


def _normalize_whatsapp_number(number: str) -> str:
    if not number:
        return ""
    return number if number.startswith("whatsapp:") else f"whatsapp:{number}"


def send_whatsapp_message(payload: dict, queued_message: QueuedMessage | None = None) -> WhatsAppDelivery:
    """
    Send a WhatsApp message through Twilio and persist delivery metadata.
    """
    _require_twilio_settings()

    to_number = _normalize_whatsapp_number(payload.get("whatsapp_number", ""))
    body = payload.get("message", "")
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    kwargs = {
        "from_": settings.TWILIO_WHATSAPP_FROM,
        "to": "whatsapp:+919548946440",
        "body": body,
    }
    callback_url = _status_callback_url()
    if callback_url:
        kwargs["status_callback"] = callback_url

    actual_to = kwargs["to"]
    message = client.messages.create(**kwargs)

    delivery = WhatsAppDelivery.objects.create(
        queued_message=queued_message,
        message_sid=message.sid,
        to_number=actual_to,
        from_number=settings.TWILIO_WHATSAPP_FROM,
        body=body,
        status=message.status or "queued",
        sent_at=timezone.now(),
    )
    DeliveryLog.objects.create(
        queued_message=queued_message,
        event="consumed",
        detail=f"Twilio accepted message SID {message.sid} with status {delivery.status}.",
        payload_snapshot={**payload, "message_sid": message.sid, "twilio_status": delivery.status},
    )
    return delivery


def update_delivery_from_webhook(data: dict) -> WhatsAppDelivery | None:
    sid = data.get("MessageSid") or data.get("SmsSid") or data.get("MessageSid".lower())
    if not sid:
        return None

    delivery = WhatsAppDelivery.objects.filter(message_sid=sid).first()
    if not delivery:
        return None

    status = data.get("MessageStatus") or data.get("SmsStatus") or delivery.status
    delivery.status = status
    delivery.raw_callback = data
    delivery.error_code = data.get("ErrorCode", "") or ""
    delivery.error_message = data.get("ErrorMessage", "") or ""

    now = timezone.now()
    if status == "delivered":
        delivery.delivered_at = now
    elif status in ("failed", "undelivered"):
        delivery.failed_at = now
    elif status == "sent" and not delivery.sent_at:
        delivery.sent_at = now

    delivery.save(update_fields=[
        "status", "raw_callback", "error_code", "error_message",
        "sent_at", "delivered_at", "failed_at", "updated_at",
    ])
    return delivery
