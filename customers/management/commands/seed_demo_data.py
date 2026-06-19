"""
Management command: seed_demo_data
Populates the database with 120 realistic demo customers and their
related transaction, credit-card, loan, and credit-card-history records.

Usage:
    python manage.py seed_demo_data           # insert 120 customers
    python manage.py seed_demo_data --clear   # wipe existing data first
"""

import datetime
import random

from django.core.management.base import BaseCommand

from customers.models import (
    CreditCardHistory,
    CreditCardTransaction,
    CustomerProfile,
    LoanHistory,
    TransactionData,
)

FIRST_NAMES = [
    "Aarav", "Aditi", "Amit", "Anika", "Arjun", "Bhavna", "Deepak", "Divya",
    "Farhan", "Geeta", "Harish", "Isha", "Jatin", "Kavita", "Kiran", "Lakshmi",
    "Mahesh", "Manish", "Meera", "Mohan", "Neeraj", "Neha", "Nikhil", "Poonam",
    "Priya", "Rahul", "Rajesh", "Ramesh", "Ravi", "Rekha", "Rohit", "Sandeep",
    "Sanjay", "Sarita", "Shilpa", "Shreya", "Suresh", "Swati", "Varun", "Vijay",
]

LAST_NAMES = [
    "Agarwal", "Bansal", "Bhatt", "Chaudhary", "Chopra", "Das", "Desai", "Dubey",
    "Gupta", "Iyer", "Jain", "Joshi", "Kapoor", "Khanna", "Kumar", "Malhotra",
    "Mehta", "Mishra", "Nair", "Pandey", "Patel", "Pillai", "Rao", "Reddy",
    "Sharma", "Singh", "Sinha", "Trivedi", "Varma", "Yadav",
]

OCCUPATIONS = [
    "Software Engineer", "Bank Manager", "Doctor", "Teacher", "Accountant",
    "Sales Executive", "Marketing Manager", "Nurse", "Civil Engineer", "Architect",
    "Lawyer", "Government Employee", "Business Owner", "Professor", "Data Analyst",
    "HR Manager", "Financial Analyst", "Pharmacist", "Consultant", "Retired",
]

ACCOUNT_TYPES = ["savings", "current", "premium", "salary"]

PRODUCTS = [
    "Savings Account", "Current Account", "Fixed Deposit",
    "Recurring Deposit", "Credit Card", "Debit Card",
    "Home Loan", "Personal Loan", "Car Loan", "Insurance",
]

LOAN_TYPES = ["Personal Loan", "Home Loan", "Car Loan", "Education Loan", "Business Loan"]
REPAYMENT_OPTIONS = ["good", "bad", "poor", "no_history"]


def _random_name(rng: random.Random) -> tuple[str, str]:
    return rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)


def _phone(rng: random.Random) -> str:
    return f"+91{rng.randint(7000000000, 9999999999)}"


def _email(first: str, last: str, idx: int) -> str:
    return f"{first.lower()}.{last.lower()}{idx}@demobank.in"


def _existing_products(rng: random.Random) -> list[str]:
    return rng.sample(PRODUCTS, k=rng.randint(1, 4))


def _recent_large_txns(rng: random.Random, count: int = 3) -> list[dict]:
    txns = []
    for _ in range(rng.randint(0, count)):
        txns.append({
            "amount": round(rng.uniform(50_000, 500_000), 2),
            "description": rng.choice(["Electronics", "Jewellery", "Travel", "Medical", "Property Advance"]),
            "date": (datetime.date.today() - datetime.timedelta(days=rng.randint(1, 28))).isoformat(),
        })
    return txns


def _existing_loans(rng: random.Random) -> list[dict]:
    loans = []
    for _ in range(rng.randint(0, 2)):
        loans.append({
            "type": rng.choice(LOAN_TYPES),
            "principal": round(rng.uniform(1_00_000, 50_00_000), 2),
            "emi": round(rng.uniform(2_000, 50_000), 2),
            "remaining_months": rng.randint(1, 60),
        })
    return loans


def _previous_applications(rng: random.Random) -> list[dict]:
    apps = []
    for _ in range(rng.randint(0, 3)):
        apps.append({
            "type": rng.choice(LOAN_TYPES),
            "year": rng.randint(2018, 2025),
            "status": rng.choice(["approved", "rejected", "closed"]),
        })
    return apps


class Command(BaseCommand):
    help = "Seed the database with 120 demo customers and related records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing customer data before seeding.",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=120,
            help="Number of demo customers to create (default: 120).",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("  Clearing existing customer data...")
            CreditCardHistory.objects.all().delete()
            LoanHistory.objects.all().delete()
            CreditCardTransaction.objects.all().delete()
            TransactionData.objects.all().delete()
            CustomerProfile.objects.all().delete()
            self.stdout.write(self.style.WARNING("  Existing data cleared."))

        count = options["count"]
        rng = random.Random(42)  # fixed seed → reproducible demo data

        today = datetime.date.today()
        current_month = today.replace(day=1)
        last_month = (current_month - datetime.timedelta(days=1)).replace(day=1)

        created = 0
        skipped = 0

        self.stdout.write(f"  Seeding {count} demo customers...")

        for i in range(1, count + 1):
            customer_id = f"CUST{i:04d}"

            if CustomerProfile.objects.filter(customer_id=customer_id).exists():
                skipped += 1
                continue

            first, last = _random_name(rng)
            full_name = f"{first} {last}"

            salary = round(rng.choice([
                rng.uniform(15_000, 30_000),   # low income
                rng.uniform(30_001, 70_000),   # mid income
                rng.uniform(70_001, 2_00_000), # high income
            ]), 2)

            tenure = rng.randint(1, 120)
            account_type = rng.choice(ACCOUNT_TYPES)

            profile = CustomerProfile.objects.create(
                customer_id=customer_id,
                name=full_name,
                age=rng.randint(22, 60),
                occupation=rng.choice(OCCUPATIONS),
                salary=salary,
                account_type=account_type,
                relationship_tenure_months=tenure,
                existing_products=_existing_products(rng),
                whatsapp_number=_phone(rng),
                email=_email(first, last, i),
            )

            # --- Transaction data (current + last month) ---
            for month in [current_month, last_month]:
                credits = round(salary * rng.uniform(1.0, 1.8), 2)
                debits = round(salary * rng.uniform(0.5, 1.3), 2)
                TransactionData.objects.create(
                    customer=profile,
                    month=month,
                    total_monthly_credits=credits,
                    total_monthly_debits=debits,
                    salary_credits=salary,
                    average_balance=round(rng.uniform(5_000, 5_00_000), 2),
                    recent_large_transactions=_recent_large_txns(rng),
                )

            # --- Credit card transaction (70% of customers have CC) ---
            has_cc = rng.random() < 0.70
            if has_cc:
                for month in [current_month, last_month]:
                    CreditCardTransaction.objects.create(
                        customer=profile,
                        month=month,
                        total_monthly_credit=round(rng.uniform(2_000, 80_000), 2),
                        recent_large_transactions=_recent_large_txns(rng, count=2),
                    )

            # --- Loan history ---
            repayment = rng.choice(REPAYMENT_OPTIONS)
            credit_score = (
                rng.randint(300, 900)
                if repayment != "no_history"
                else (rng.randint(300, 900) if rng.random() < 0.4 else None)
            )
            LoanHistory.objects.create(
                customer=profile,
                existing_loans=_existing_loans(rng),
                previous_applications=_previous_applications(rng),
                repayment_behavior=repayment,
                credit_score=credit_score,
            )

            # --- Credit card history (0–2 cards per customer) ---
            num_cards = rng.randint(0, 2) if has_cc else 0
            for c in range(1, num_cards + 1):
                cd_limit = round(rng.choice([50_000, 1_00_000, 1_50_000, 2_00_000, 5_00_000]), 2)
                usage = round(rng.uniform(0.05, 1.0) * cd_limit, 2)
                CreditCardHistory.objects.create(
                    customer=profile,
                    cd_id=f"{customer_id}-CC{c:02d}",
                    cd_limit=cd_limit,
                    cd_usage_above_80pct=(usage / cd_limit) > 0.80,
                    cd_score=rng.randint(300, 900),
                )

            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n  Done — {created} customers created, {skipped} already existed."
            )
        )
        self.stdout.write(f"  Total customers in DB: {CustomerProfile.objects.count()}")
        self.stdout.write(f"  Total transactions:    {TransactionData.objects.count()}")
        self.stdout.write(f"  Total CC transactions: {CreditCardTransaction.objects.count()}")
        self.stdout.write(f"  Total loan records:    {LoanHistory.objects.count()}")
        self.stdout.write(f"  Total CC histories:    {CreditCardHistory.objects.count()}")
