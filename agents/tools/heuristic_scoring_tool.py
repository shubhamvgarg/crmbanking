"""
Heuristic Scoring Tool
Scores users using smart banking heuristics:
  1. Credit card usage > 80% of limit → loan need likely
  2. No missed EMIs (repayment == 'good') → eligible
A user must satisfy at least 1 heuristic to be a candidate.
"""

import json

from langchain_core.tools import tool


def _apply_heuristics(user: dict) -> tuple[int, list[str]]:
    passed = []

    if user.get("cc_usage_above_80pct"):
        passed.append("high_credit_card_utilisation")

    if user.get("repayment_behavior") == "good":
        passed.append("clean_emi_history")

    # Bonus heuristic: salary > 50k suggests higher loan repayment capacity
    if float(user.get("salary", 0)) > 50_000:
        passed.append("high_income")

    return len(passed), passed


@tool
def heuristic_scoring_tool(users_json: str) -> str:
    """
    Apply heuristic scoring to a list of customers.
    Heuristics: high credit card utilisation (>80%), clean EMI history,
    and high income (>50k/month).
    A customer must satisfy at least 1 heuristic to be flagged as a loan candidate.
    Input: JSON string with a 'users' list or a plain JSON array.
    Returns: JSON with scored and filtered candidates.
    """
    try:
        data = json.loads(users_json)
        users = data if isinstance(data, list) else data.get("users", [])
    except (json.JSONDecodeError, KeyError):
        return json.dumps({"status": "error", "message": "Invalid JSON input", "candidates": []})

    candidates = []
    for user in users:
        score, heuristics_passed = _apply_heuristics(user)
        if score >= 1:
            candidates.append({
                **user,
                "decision_method": "heuristics",
                "conversion_score": round(min(score / 3, 1.0), 2),
                "heuristics_passed": heuristics_passed,
                "scoring_reason": f"Passed {score}/3 heuristics: {', '.join(heuristics_passed)}",
            })

    return json.dumps({
        "status": "success",
        "method": "heuristics",
        "total_input": len(users),
        "total_candidates": len(candidates),
        "candidates": candidates,
    })
