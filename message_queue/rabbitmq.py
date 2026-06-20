import json
import time
from contextlib import contextmanager
from urllib.parse import quote

import pika
from django.conf import settings
from django.utils import timezone

from .models import DeliveryLog, QueuedMessage


class RabbitMQConfigurationError(RuntimeError):
    pass


def _connection_parameters():
    url = settings.RABBITMQ_URL.strip()
    if url and "your-host" not in url and "user:password" not in url:
        return pika.URLParameters(url)

    host = settings.RABBITMQ_HOST.strip()
    if host.startswith(("amqp://", "amqps://")):
        return pika.URLParameters(host)

    if not host or not settings.RABBITMQ_USER or not settings.RABBITMQ_PASSWORD:
        raise RabbitMQConfigurationError(
            "RabbitMQ is not configured. Set RABBITMQ_URL or RABBITMQ_HOST/RABBITMQ_USER/RABBITMQ_PASSWORD."
        )

    scheme = "amqps" if settings.RABBITMQ_USE_SSL else "amqp"
    user = quote(settings.RABBITMQ_USER, safe="")
    password = quote(settings.RABBITMQ_PASSWORD, safe="")
    vhost = quote(settings.RABBITMQ_VHOST or "/", safe="")
    url = f"{scheme}://{user}:{password}@{host}:{settings.RABBITMQ_PORT}/{vhost}"
    return pika.URLParameters(url)


@contextmanager
def rabbitmq_channel():
    connection = pika.BlockingConnection(_connection_parameters())
    try:
        channel = connection.channel()
        channel.exchange_declare(
            exchange=settings.RABBITMQ_EXCHANGE,
            exchange_type="direct",
            durable=True,
        )
        channel.queue_declare(queue=settings.RABBITMQ_QUEUE, durable=True)
        channel.queue_bind(
            queue=settings.RABBITMQ_QUEUE,
            exchange=settings.RABBITMQ_EXCHANGE,
            routing_key=settings.RABBITMQ_ROUTING_KEY,
        )
        yield channel
    finally:
        if connection and connection.is_open:
            connection.close()


def build_queue_payload(message: dict, run=None, batch_offset: int = 0) -> dict:
    return {
        "run_id": str(run.run_id) if run else message.get("run_id", ""),
        "batch_offset": batch_offset,
        "customer_id": message.get("customer_id", ""),
        "customer_name": message.get("name", message.get("customer_name", "")),
        "whatsapp_number": message.get("whatsapp_number", ""),
        "offer": message.get("offer", message.get("recommended_offer", "")),
        "message": message.get("message", message.get("personalize_message", "")),
    }


def create_queued_message(payload: dict, run=None, batch_offset: int = 0) -> QueuedMessage:
    queued = QueuedMessage.objects.create(
        run=run,
        batch_offset=batch_offset,
        customer_id=payload.get("customer_id", ""),
        customer_name=payload.get("customer_name", ""),
        whatsapp_number=payload.get("whatsapp_number", ""),
        offer=payload.get("offer", ""),
        message=payload.get("message", ""),
        payload=payload,
    )
    DeliveryLog.objects.create(
        queued_message=queued,
        event="publish_attempt",
        detail="Queued locally; publish attempt pending.",
        payload_snapshot=payload,
    )
    return queued


def publish_queued_message(queued: QueuedMessage, max_retries: int = 3) -> QueuedMessage:
    payload = {
        **queued.payload,
        "message_id": str(queued.message_id),
    }
    body = json.dumps(payload).encode("utf-8")
    last_error = ""

    for attempt in range(1, max_retries + 1):
        try:
            with rabbitmq_channel() as channel:
                channel.basic_publish(
                    exchange=settings.RABBITMQ_EXCHANGE,
                    routing_key=settings.RABBITMQ_ROUTING_KEY,
                    body=body,
                    properties=pika.BasicProperties(
                        content_type="application/json",
                        delivery_mode=pika.DeliveryMode.Persistent,
                    ),
                )
            queued.status = "published"
            queued.retry_count = attempt - 1
            queued.last_error = ""
            queued.published_at = timezone.now()
            queued.save(update_fields=[
                "status", "retry_count", "last_error", "published_at", "updated_at",
            ])
            DeliveryLog.objects.create(
                queued_message=queued,
                event="published",
                detail=f"Published to {settings.RABBITMQ_EXCHANGE}/{settings.RABBITMQ_ROUTING_KEY}.",
                payload_snapshot=payload,
            )
            return queued
        except Exception as exc:
            last_error = str(exc)
            queued.retry_count = attempt
            queued.last_error = last_error
            queued.status = "publish_failed"
            queued.save(update_fields=["status", "retry_count", "last_error", "updated_at"])
            DeliveryLog.objects.create(
                queued_message=queued,
                event="publish_failed",
                detail=f"Attempt {attempt}/{max_retries} failed: {last_error}",
                payload_snapshot=payload,
            )
            if attempt < max_retries:
                time.sleep(min(2 ** (attempt - 1), 5))

    return queued


def enqueue_message(message: dict, run=None, batch_offset: int = 0, max_retries: int = 3) -> QueuedMessage:
    payload = build_queue_payload(message, run=run, batch_offset=batch_offset)
    queued = create_queued_message(payload, run=run, batch_offset=batch_offset)
    return publish_queued_message(queued, max_retries=max_retries)


def mark_consumed(payload: dict) -> QueuedMessage | None:
    message_id = payload.get("message_id")
    queued = None
    if message_id:
        queued = QueuedMessage.objects.filter(message_id=message_id).first()

    if queued:
        queued.status = "consumed"
        queued.consumed_at = timezone.now()
        queued.last_error = ""
        queued.save(update_fields=["status", "consumed_at", "last_error", "updated_at"])

    DeliveryLog.objects.create(
        queued_message=queued,
        event="consumed",
        detail="Consumer processed message for WhatsApp delivery.",
        payload_snapshot=payload,
    )
    return queued


def record_consume_failure(
    payload: dict,
    error: str,
    *,
    requeued: bool,
    queued: QueuedMessage | None = None,
) -> QueuedMessage | None:
    """Record a failed consume attempt; keep status published when requeueing."""
    if queued is None and payload.get("message_id"):
        queued = QueuedMessage.objects.filter(message_id=payload["message_id"]).first()

    if queued:
        queued.retry_count += 1
        queued.last_error = error
        if requeued:
            queued.status = "published"
        else:
            queued.status = "failed"
        queued.save(update_fields=["status", "retry_count", "last_error", "updated_at"])

    detail = f"Requeued for retry: {error}" if requeued else f"Failed permanently: {error}"
    DeliveryLog.objects.create(
        queued_message=queued,
        event="consume_failed",
        detail=detail,
        payload_snapshot=payload,
    )
    return queued
