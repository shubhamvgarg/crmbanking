from django.contrib import admin

from .models import (
    CreditCardHistory,
    CreditCardTransaction,
    CustomerProfile,
    LoanHistory,
    TransactionData,
)


class TransactionDataInline(admin.TabularInline):
    model = TransactionData
    extra = 0
    readonly_fields = ("month", "total_monthly_credits", "total_monthly_debits",
                       "salary_credits", "average_balance")


class CreditCardTransactionInline(admin.TabularInline):
    model = CreditCardTransaction
    extra = 0
    readonly_fields = ("month", "total_monthly_credit")


class LoanHistoryInline(admin.StackedInline):
    model = LoanHistory
    extra = 0
    readonly_fields = ("repayment_behavior", "credit_score")


class CreditCardHistoryInline(admin.TabularInline):
    model = CreditCardHistory
    extra = 0
    readonly_fields = ("cd_id", "cd_limit", "cd_usage_above_80pct", "cd_score")


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "customer_id", "name", "age", "occupation",
        "salary", "account_type", "relationship_tenure_months",
    )
    list_filter = ("account_type",)
    search_fields = ("customer_id", "name", "email", "occupation")
    readonly_fields = ("customer_id",)
    inlines = [
        TransactionDataInline,
        CreditCardTransactionInline,
        LoanHistoryInline,
        CreditCardHistoryInline,
    ]


@admin.register(TransactionData)
class TransactionDataAdmin(admin.ModelAdmin):
    list_display = ("customer", "month", "total_monthly_credits",
                    "total_monthly_debits", "salary_credits", "average_balance")
    list_filter = ("month",)
    search_fields = ("customer__customer_id", "customer__name")
    date_hierarchy = "month"


@admin.register(CreditCardTransaction)
class CreditCardTransactionAdmin(admin.ModelAdmin):
    list_display = ("customer", "month", "total_monthly_credit")
    list_filter = ("month",)
    search_fields = ("customer__customer_id", "customer__name")
    date_hierarchy = "month"


@admin.register(LoanHistory)
class LoanHistoryAdmin(admin.ModelAdmin):
    list_display = ("customer", "repayment_behavior", "credit_score")
    list_filter = ("repayment_behavior",)
    search_fields = ("customer__customer_id", "customer__name")


@admin.register(CreditCardHistory)
class CreditCardHistoryAdmin(admin.ModelAdmin):
    list_display = ("cd_id", "customer", "cd_limit", "cd_usage_above_80pct", "cd_score")
    list_filter = ("cd_usage_above_80pct",)
    search_fields = ("cd_id", "customer__customer_id", "customer__name")
