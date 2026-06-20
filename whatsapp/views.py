from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from rm_auth.decorators import rm_login_required

from .models import WhatsAppDelivery
from .services import sync_pending_delivery_statuses, update_delivery_from_webhook


@csrf_exempt
@require_POST
def status_webhook(request):
    """
    Twilio delivery-status callback.
    Twilio posts application/x-www-form-urlencoded fields like MessageSid and MessageStatus.
    """
    update_delivery_from_webhook(request.POST.dict())
    return HttpResponse("OK")


@rm_login_required
@require_GET
def delivery_log(request):
    try:
        sync_pending_delivery_statuses(limit=100)
    except Exception:
        pass

    deliveries = (
        WhatsAppDelivery.objects
        .select_related("queued_message", "queued_message__run")
        .order_by("-created_at")[:200]
    )
    return render(request, "whatsapp/delivery_log.html", {"deliveries": deliveries})
