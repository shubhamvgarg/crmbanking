"""
Notification Tool (Phase 3 stub)
In Phase 5 this will publish payloads to RabbitMQ.
For now it returns the payload as a confirmation dict.
"""

import json

from langchain_core.tools import tool


@tool
def notification_tool(
    user: str,
    whatsapp_number: str,
    offer: str,
    personalize_message: str,
) -> str:
    """
    Queue a personalized WhatsApp message for delivery.
    Publishes the message payload to the message queue.
    In Phase 3 this is a stub — it logs and returns the payload.
    In Phase 5 it will publish to RabbitMQ.
    """
    payload = {
        "user": user,
        "whatsapp_number": whatsapp_number,
        "offer": offer,
        "personalize_message": personalize_message,
        "status": "queued_stub",
    }
    return json.dumps(payload)
