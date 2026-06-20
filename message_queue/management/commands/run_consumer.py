import json

from django.conf import settings
from django.core.management.base import BaseCommand
from twilio.base.exceptions import TwilioException, TwilioRestException

from message_queue.models import QueuedMessage
from message_queue.rabbitmq import mark_consumed, rabbitmq_channel, record_consume_failure
from whatsapp.services import TwilioConfigurationError, send_whatsapp_message


def should_requeue_consume(exc: Exception, queued: QueuedMessage | None) -> bool:
    """
    Requeue on Twilio API/server failures so RabbitMQ can retry delivery.
    Do not requeue poison messages or configuration errors.
    """
    if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError, TwilioConfigurationError)):
        return False
    if isinstance(exc, (TwilioRestException, TwilioException)):
        if queued and queued.retry_count >= settings.CONSUMER_MAX_RETRIES:
            return False
        return True
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        if queued and queued.retry_count >= settings.CONSUMER_MAX_RETRIES:
            return False
        return True
    return False


class Command(BaseCommand):
    help = "Consume approved WhatsApp message payloads from RabbitMQ."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Consume one message and exit.",
        )

    def handle(self, *args, **options):
        once = options["once"]
        self.stdout.write("Starting RabbitMQ consumer...")

        with rabbitmq_channel() as channel:
            channel.basic_qos(prefetch_count=1)

            def callback(ch, method, properties, body):
                payload = {}
                queued = None
                try:
                    payload = json.loads(body.decode("utf-8"))
                    queued = QueuedMessage.objects.filter(message_id=payload.get("message_id")).first()
                    delivery = send_whatsapp_message(payload, queued_message=queued)
                    queued = mark_consumed(payload)
                    msg_id = queued.message_id if queued else payload.get("message_id", "external")
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Sent WhatsApp message: {msg_id} / SID {delivery.message_sid}"
                        )
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:
                    if not payload:
                        try:
                            payload = json.loads(body.decode("utf-8"))
                        except Exception:
                            payload = {"raw_body": body.decode("utf-8", errors="replace")}
                    if queued is None and payload.get("message_id"):
                        queued = QueuedMessage.objects.filter(message_id=payload["message_id"]).first()

                    requeue = should_requeue_consume(exc, queued)
                    detail = f"Consumer failed: {exc}"
                    record_consume_failure(payload, str(exc), requeued=requeue, queued=queued)

                    if requeue:
                        self.stderr.write(self.style.WARNING(f"{detail} — requeueing"))
                    else:
                        self.stderr.write(self.style.ERROR(f"{detail} — not requeueing"))

                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=requeue)

                if once:
                    ch.stop_consuming()

            channel.basic_consume(
                queue=settings.RABBITMQ_QUEUE,
                on_message_callback=callback,
            )

            self.stdout.write("Waiting for messages. Press Ctrl+C to stop.")
            try:
                channel.start_consuming()
            except KeyboardInterrupt:
                channel.stop_consuming()
                self.stdout.write("Consumer stopped.")
