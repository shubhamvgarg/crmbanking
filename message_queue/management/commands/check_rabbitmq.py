from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from message_queue.rabbitmq import rabbitmq_channel


class Command(BaseCommand):
    help = "Verify connection to the configured online RabbitMQ broker."

    def handle(self, *args, **options):
        self.stdout.write("Checking RabbitMQ connection...")
        self.stdout.write(f"Queue: {settings.RABBITMQ_QUEUE}")
        self.stdout.write(f"Exchange: {settings.RABBITMQ_EXCHANGE}")
        self.stdout.write(f"Routing key: {settings.RABBITMQ_ROUTING_KEY}")

        try:
            with rabbitmq_channel():
                self.stdout.write(self.style.SUCCESS("Connected to RabbitMQ broker."))
                self.stdout.write(self.style.SUCCESS("Queue/exchange declaration succeeded."))
        except Exception as exc:
            raise CommandError(f"RabbitMQ check failed: {exc}") from exc
