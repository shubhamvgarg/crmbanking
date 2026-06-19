"""
Recommendation Tool
Maps each scored candidate's profile signals to the most appropriate
loan product from the bank's catalog.
"""

import json

from langchain_core.tools import tool

LOAN_CATALOG = {
    "Premium Personal Loan": {
        "amount_range": "₹5L – ₹15L",
        "interest_rate": "10.5%",
        "tenure_months": 60,
        "criteria": "High salary (>₹80k/mo) or Premium account",
    },
    "Pre-Approved Loan": {
        "amount_range": "₹2L – ₹10L",
        "interest_rate": "11.0%",
        "tenure_months": 48,
        "criteria": "Existing customer with good repayment history",
    },
    "Small Starter Loan": {
        "amount_range": "₹50k – ₹2L",
        "interest_rate": "14.0%",
        "tenure_months": 24,
        "criteria": "Low or no credit history",
    },
    "Debt Consolidation Loan": {
        "amount_range": "₹1L – ₹5L",
        "interest_rate": "12.0%",
        "tenure_months": 36,
        "criteria": "High credit card utilisation (>80%)",
    },
    "Loyalty Rate Loan": {
        "amount_range": "₹3L – ₹12L",
        "interest_rate": "9.9%",
        "tenure_months": 60,
        "criteria": "Tenure > 3 years with stable income",
    },
    "Salary Advance Loan": {
        "amount_range": "₹50k – ₹3L",
        "interest_rate": "12.5%",
        "tenure_months": 12,
        "criteria": "Salary account with regular credits",
    },
}


def _pick_offer(user: dict) -> tuple[str, dict]:
    salary = float(user.get("salary", 0))
    tenure = user.get("relationship_tenure_months", 0)
    repayment = user.get("repayment_behavior", "no_history")
    credit_score = user.get("credit_score") or 0
    account_type = user.get("account_type", "savings")
    cc_high = user.get("cc_usage_above_80pct", False)

    # Priority order
    if salary >= 80_000 or account_type == "premium":
        offer = "Premium Personal Loan"
    elif tenure >= 36 and repayment == "good" and salary >= 30_000:
        offer = "Loyalty Rate Loan"
    elif cc_high:
        offer = "Debt Consolidation Loan"
    elif repayment == "good" and credit_score >= 650:
        offer = "Pre-Approved Loan"
    elif account_type == "salary" and user.get("salary_credited_regularly"):
        offer = "Salary Advance Loan"
    else:
        offer = "Small Starter Loan"

    return offer, LOAN_CATALOG[offer]


@tool
def recommendation_tool(candidates_json: str) -> str:
    """
    For each scored loan candidate, recommend the most suitable loan product
    based on their salary, tenure, repayment history, credit score, and
    account type. Returns candidates with added offer details.
    Input: JSON string with a 'candidates' list or a plain JSON array.
    Returns: JSON array of candidates with recommended_offer and offer_details.
    """
    try:
        data = json.loads(candidates_json)
        candidates = data if isinstance(data, list) else data.get("candidates", [])
    except (json.JSONDecodeError, KeyError):
        return json.dumps({"status": "error", "message": "Invalid JSON input", "recommended": []})

    recommended = []
    for user in candidates:
        offer_name, offer_details = _pick_offer(user)
        recommended.append({
            **user,
            "recommended_offer": offer_name,
            "offer_details": offer_details,
        })

    return json.dumps({
        "status": "success",
        "total": len(recommended),
        "recommended": recommended,
    })
