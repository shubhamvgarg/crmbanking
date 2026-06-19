from django.db import models


class CustomerProfile(models.Model):
    ACCOUNT_TYPES = [
        ("savings", "Savings"),
        ("current", "Current"),
        ("premium", "Premium"),
        ("salary", "Salary"),
    ]

    customer_id = models.CharField(max_length=20, unique=True, primary_key=True)
    name = models.CharField(max_length=120)
    age = models.PositiveIntegerField()
    occupation = models.CharField(max_length=100)
    salary = models.DecimalField(max_digits=12, decimal_places=2)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default="savings")
    relationship_tenure_months = models.PositiveIntegerField(
        help_text="Number of months the customer has been with the bank"
    )
    existing_products = models.JSONField(
        default=list,
        help_text="e.g. ['Savings Account', 'Credit Card']",
    )
    whatsapp_number = models.CharField(max_length=20)
    email = models.EmailField()

    class Meta:
        verbose_name = "Customer Profile"
        verbose_name_plural = "Customer Profiles"
        ordering = ["customer_id"]

    def __str__(self):
        return f"{self.customer_id} — {self.name}"


class TransactionData(models.Model):
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    month = models.DateField(help_text="First day of the reference month")
    total_monthly_credits = models.DecimalField(max_digits=14, decimal_places=2)
    total_monthly_debits = models.DecimalField(max_digits=14, decimal_places=2)
    salary_credits = models.DecimalField(max_digits=14, decimal_places=2)
    average_balance = models.DecimalField(max_digits=14, decimal_places=2)
    recent_large_transactions = models.JSONField(
        default=list,
        help_text="List of transactions above ₹50,000",
    )

    class Meta:
        verbose_name = "Transaction Data"
        verbose_name_plural = "Transaction Data"
        ordering = ["-month"]
        unique_together = [("customer", "month")]

    def __str__(self):
        return f"{self.customer_id} — {self.month:%b %Y}"


class CreditCardTransaction(models.Model):
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="cc_transactions",
    )
    month = models.DateField(help_text="First day of the reference month")
    total_monthly_credit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Total spend on all credit cards this month",
    )
    recent_large_transactions = models.JSONField(
        default=list,
        help_text="Large CC transactions this month",
    )

    class Meta:
        verbose_name = "Credit Card Transaction"
        verbose_name_plural = "Credit Card Transactions"
        ordering = ["-month"]
        unique_together = [("customer", "month")]

    def __str__(self):
        return f"{self.customer_id} CC — {self.month:%b %Y}"


class LoanHistory(models.Model):
    REPAYMENT_CHOICES = [
        ("good", "Good"),
        ("bad", "Bad"),
        ("poor", "Poor"),
        ("no_history", "No History"),
    ]

    customer = models.OneToOneField(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="loan_history",
    )
    existing_loans = models.JSONField(
        default=list,
        help_text="Active loans with type, principal, and EMI",
    )
    previous_applications = models.JSONField(
        default=list,
        help_text="Past loan applications with status",
    )
    repayment_behavior = models.CharField(
        max_length=20,
        choices=REPAYMENT_CHOICES,
        default="no_history",
    )
    credit_score = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Credit score (300–900), null if unavailable",
    )

    class Meta:
        verbose_name = "Loan History"
        verbose_name_plural = "Loan Histories"

    def __str__(self):
        return f"{self.customer_id} — {self.get_repayment_behavior_display()}"


class CreditCardHistory(models.Model):
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="credit_cards",
    )
    cd_id = models.CharField(max_length=30, unique=True, help_text="Credit card identifier")
    cd_limit = models.DecimalField(max_digits=12, decimal_places=2)
    cd_usage_above_80pct = models.BooleanField(
        default=False,
        help_text="True when current utilisation exceeds 80% of the limit",
    )
    cd_score = models.PositiveIntegerField(help_text="Card-specific credit score")

    class Meta:
        verbose_name = "Credit Card History"
        verbose_name_plural = "Credit Card Histories"
        ordering = ["customer", "cd_id"]

    def __str__(self):
        return f"{self.cd_id} ({self.customer_id})"
