"""
SQL Tool — fetches a paginated batch of customers from the DB and
returns a compact JSON representation suitable for agent processing.
"""

import json

from langchain_core.tools import tool


@tool
def sql_query_tool(batch_offset: int, batch_size: int) -> str:
    """
    Fetch customer profiles, transactions, loan history, and credit card data
    from the database. Returns a JSON array of customer records.
    Use this tool to retrieve the next batch of customers for processing.
    """
    # Import here to avoid circular imports and ensure Django is ready
    from customers.models import CustomerProfile

    profiles = (
        CustomerProfile.objects
        .prefetch_related("transactions", "cc_transactions", "credit_cards", "loan_history")
        .order_by("customer_id")[batch_offset: batch_offset + batch_size]
    )

    users = []
    for p in profiles:
        # Latest transaction month
        latest_txn = p.transactions.order_by("-month").first()
        prev_txn = p.transactions.order_by("-month")[1:2].first()

        # Credit card summary
        cc_cards = list(p.credit_cards.all())
        cc_high_usage = any(c.cd_usage_above_80pct for c in cc_cards)

        # Loan history
        try:
            lh = p.loan_history
            repayment = lh.repayment_behavior
            credit_score = lh.credit_score
        except Exception:
            repayment = "no_history"
            credit_score = None

        # Salary credited regularly = salary credit in both months
        salary_regular = False
        if latest_txn and prev_txn:
            salary_regular = (
                float(latest_txn.salary_credits) > 0 and
                float(prev_txn.salary_credits) > 0
            )

        # Recent large transaction
        has_large_txn = False
        if latest_txn and latest_txn.recent_large_transactions:
            has_large_txn = len(latest_txn.recent_large_transactions) > 0

        avg_balance = float(latest_txn.average_balance) if latest_txn else 0.0

        users.append({
            "customer_id": p.customer_id,
            "name": p.name,
            "age": p.age,
            "occupation": p.occupation,
            "salary": float(p.salary),
            "account_type": p.account_type,
            "relationship_tenure_months": p.relationship_tenure_months,
            "existing_products": p.existing_products,
            "whatsapp_number": p.whatsapp_number,
            "email": p.email,
            "avg_balance": avg_balance,
            "salary_credited_regularly": salary_regular,
            "has_recent_large_transaction": has_large_txn,
            "cc_usage_above_80pct": cc_high_usage,
            "repayment_behavior": repayment,
            "credit_score": credit_score,
        })

    return json.dumps({
        "status": "success",
        "batch_offset": batch_offset,
        "batch_size": batch_size,
        "count": len(users),
        "users": users,
    })
