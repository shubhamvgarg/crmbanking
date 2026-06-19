from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from agents.models import AgentRun, HumanReview
from customers.models import CustomerProfile
from message_queue.models import QueuedMessage
from rm_auth.models import RMUser
from whatsapp.models import WhatsAppDelivery


class Command(BaseCommand):
    help = "Validate the CRM demo readiness across RM auth, customers, agents, queue, and WhatsApp."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Require at least one completed run, queued message, and WhatsApp delivery.",
        )

    def handle(self, *args, **options):
        strict = options["strict"]
        failures = []
        warnings = []

        checks = {
            "Active RMs": RMUser.objects.filter(is_active=True).count(),
            "Customers": CustomerProfile.objects.count(),
            "Agent runs": AgentRun.objects.count(),
            "Human reviews": HumanReview.objects.count(),
            "Queued messages": QueuedMessage.objects.count(),
            "WhatsApp deliveries": WhatsAppDelivery.objects.count(),
        }

        env_checks = {
            "GROQ_API_KEY": bool(settings.GROQ_API_KEY),
            "RABBITMQ_QUEUE": bool(settings.RABBITMQ_QUEUE),
            "RABBITMQ_EXCHANGE": bool(settings.RABBITMQ_EXCHANGE),
            "TWILIO_ACCOUNT_SID": bool(settings.TWILIO_ACCOUNT_SID),
            "TWILIO_AUTH_TOKEN": bool(settings.TWILIO_AUTH_TOKEN),
            "TWILIO_WHATSAPP_FROM": bool(settings.TWILIO_WHATSAPP_FROM),
        }

        if checks["Active RMs"] == 0:
            failures.append("Create at least one active RM user.")
        if checks["Customers"] == 0:
            failures.append("Seed or import customer data.")
        for name, configured in env_checks.items():
            if not configured:
                failures.append(f"Missing required setting: {name}.")

        if checks["Agent runs"] == 0:
            warnings.append("No agent run exists yet.")
        if checks["Human reviews"] == 0:
            warnings.append("No HumanReview records yet; run through HITL review once.")
        if checks["Queued messages"] == 0:
            warnings.append("No queued messages yet; approve final messages in a pipeline run.")
        if checks["WhatsApp deliveries"] == 0:
            warnings.append("No WhatsApp deliveries yet; run the queue consumer after approval.")

        if strict:
            if AgentRun.objects.filter(status="completed").count() == 0:
                failures.append("Strict mode: no completed AgentRun found.")
            if checks["Queued messages"] == 0:
                failures.append("Strict mode: no QueuedMessage records found.")
            if checks["WhatsApp deliveries"] == 0:
                failures.append("Strict mode: no WhatsAppDelivery records found.")

        self.stdout.write(self.style.MIGRATE_HEADING("CRM Bank E2E Readiness"))
        for name, value in checks.items():
            self.stdout.write(f"{name}: {value}")
        self.stdout.write("")
        for name, configured in env_checks.items():
            status = "configured" if configured else "missing"
            style = self.style.SUCCESS if configured else self.style.ERROR
            self.stdout.write(style(f"{name}: {status}"))

        if warnings:
            self.stdout.write("")
            for warning in warnings:
                self.stdout.write(self.style.WARNING(f"Warning: {warning}"))

        if failures:
            raise CommandError("E2E validation failed:\n- " + "\n- ".join(failures))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("E2E readiness validation passed."))
