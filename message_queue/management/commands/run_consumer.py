import json

from django.conf import settings
from django.core.management.base import BaseCommand

from message_queue.models import DeliveryLog, QueuedMessage
from message_queue.rabbitmq import mark_consumed, rabbitmq_channel
from whatsapp.services import send_whatsapp_message


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
                try:
                    payload = json.loads(body.decode("utf-8"))
                    queued = QueuedMessage.objects.filter(message_id=payload.get("message_id")).first()
                    delivery = send_whatsapp_message(payload, queued_message=queued)
                    queued = mark_consumed(payload)
                    msg_id = queued.message_id if queued else payload.get("message_id", "external")
                    self.stdout.write(self.style.SUCCESS(f"Sent WhatsApp message: {msg_id} / SID {delivery.message_sid}"))
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:
                    detail = f"Consumer failed: {exc}"
                    queued = None
                    try:
                        payload = json.loads(body.decode("utf-8"))
                        queued = QueuedMessage.objects.filter(message_id=payload.get("message_id")).first()
                        if queued:
                            queued.status = "failed"
                            queued.last_error = str(exc)
                            queued.save(update_fields=["status", "last_error", "updated_at"])
                    except Exception:
                        payload = {}
                    DeliveryLog.objects.create(
                        queued_message=queued,
                        event="consume_failed",
                        detail=detail,
                        payload_snapshot=payload or {"raw_body": body.decode("utf-8", errors="replace")},
                    )
                    self.stderr.write(self.style.ERROR(detail))
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

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
