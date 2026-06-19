"""
Notification Tool (Phase 5)
Publishes approved WhatsApp outreach payloads to RabbitMQ.
"""

import json

from langchain_core.tools import tool

from message_queue.rabbitmq import enqueue_message


@tool
def notification_tool(
    user: str,
    whatsapp_number: str,
    offer: str,
    personalize_message: str,
) -> str:
    """
    Queue a personalized WhatsApp message for delivery.
    Publishes the message payload to RabbitMQ through the message_queue app.
    """
    payload = {
        "customer_name": user,
        "name": user,
        "whatsapp_number": whatsapp_number,
        "offer": offer,
        "message": personalize_message,
    }
    queued = enqueue_message(payload)
    payload["status"] = queued.status
    payload["message_id"] = str(queued.message_id)
    payload["queued"] = queued.status == "published"
    payload["error"] = queued.last_error
    return json.dumps(payload)
