"""
Rule-Based Scoring Tool
Scores users by evaluating 4 deterministic banking rules.
A user needs to satisfy at least 2 of the 4 rules to be a good candidate.
"""

import json

from langchain_core.tools import tool

_RULES = [
    "has_recent_large_transaction",
    "salary_credited_regularly",
    "relationship_tenure_months_gt_12",
    "no_major_defaults",
]


def _apply_rules(user: dict) -> tuple[int, list[str]]:
    """Return (score 0-4, list of passed rule names)."""
    passed = []

    if user.get("has_recent_large_transaction"):
        passed.append("recent_large_transaction")

    if user.get("salary_credited_regularly"):
        passed.append("regular_salary_credits")

    if user.get("relationship_tenure_months", 0) > 12:
        passed.append("tenure_over_12_months")

    repayment = user.get("repayment_behavior", "no_history")
    if repayment not in ("bad", "poor"):
        passed.append("no_major_defaults")

    return len(passed), passed


@tool
def rule_scoring_tool(users_json: str) -> str:
    """
    Apply rule-based scoring to a list of customers.
    Rules: recent large transaction, regular salary credits,
    tenure > 12 months, no major repayment defaults.
    A customer needs to satisfy at least 2 rules to be flagged as a good loan candidate.
    Input: JSON string containing a 'users' list.
    Returns: JSON with scored and filtered candidates.
    """
    try:
        data = json.loads(users_json)
        users = data if isinstance(data, list) else data.get("users", [])
    except (json.JSONDecodeError, KeyError):
        return json.dumps({"status": "error", "message": "Invalid JSON input", "candidates": []})

    candidates = []
    for user in users:
        score, rules_passed = _apply_rules(user)
        if score >= 2:
            candidates.append({
                **user,
                "decision_method": "rule_based",
                "conversion_score": round(score / 4, 2),
                "rules_passed": rules_passed,
                "scoring_reason": f"Passed {score}/4 rules: {', '.join(rules_passed)}",
            })

    return json.dumps({
        "status": "success",
        "method": "rule_based",
        "total_input": len(users),
        "total_candidates": len(candidates),
        "candidates": candidates,
    })
