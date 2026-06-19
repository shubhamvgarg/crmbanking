"""
ML Scoring Tool
Trains a Logistic Regression model on all available customer data
(using synthetic conversion labels derived from rule-based logic),
then predicts conversion probability for the input batch.
"""

import json

import numpy as np
from langchain_core.tools import tool
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


REPAYMENT_SCORE = {"good": 3, "no_history": 2, "poor": 1, "bad": 0}


def _extract_features(user: dict) -> list[float]:
    return [
        float(user.get("salary", 0)) / 200_000,
        float(user.get("relationship_tenure_months", 0)) / 120,
        float(user.get("credit_score") or 600) / 900,
        REPAYMENT_SCORE.get(user.get("repayment_behavior", "no_history"), 1) / 3,
        float(user.get("avg_balance", 0)) / 500_000,
        1.0 if user.get("cc_usage_above_80pct") else 0.0,
        1.0 if user.get("salary_credited_regularly") else 0.0,
        1.0 if user.get("has_recent_large_transaction") else 0.0,
    ]


def _synthetic_label(user: dict) -> int:
    """Generate a training label using rule logic as ground truth."""
    score = 0
    if float(user.get("salary", 0)) > 40_000:
        score += 1
    if user.get("relationship_tenure_months", 0) > 12:
        score += 1
    if user.get("repayment_behavior") == "good":
        score += 2
    if (user.get("credit_score") or 0) > 650:
        score += 2
    if user.get("cc_usage_above_80pct"):
        score += 1
    if float(user.get("avg_balance", 0)) > 50_000:
        score += 1
    return 1 if score >= 3 else 0


def _load_all_training_data() -> tuple[list[list[float]], list[int]]:
    from customers.models import CustomerProfile

    profiles = CustomerProfile.objects.prefetch_related(
        "transactions", "credit_cards", "loan_history"
    ).order_by("customer_id")

    X, y = [], []
    for p in profiles:
        latest_txn = p.transactions.order_by("-month").first()
        prev_txn = p.transactions.order_by("-month")[1:2].first()
        cc_cards = list(p.credit_cards.all())
        try:
            lh = p.loan_history
            repayment = lh.repayment_behavior
            credit_score = lh.credit_score
        except Exception:
            repayment = "no_history"
            credit_score = None

        user = {
            "salary": float(p.salary),
            "relationship_tenure_months": p.relationship_tenure_months,
            "credit_score": credit_score,
            "repayment_behavior": repayment,
            "avg_balance": float(latest_txn.average_balance) if latest_txn else 0.0,
            "cc_usage_above_80pct": any(c.cd_usage_above_80pct for c in cc_cards),
            "salary_credited_regularly": bool(
                latest_txn and prev_txn and
                float(latest_txn.salary_credits) > 0 and
                float(prev_txn.salary_credits) > 0
            ),
            "has_recent_large_transaction": bool(
                latest_txn and latest_txn.recent_large_transactions
            ),
        }
        X.append(_extract_features(user))
        y.append(_synthetic_label(user))

    return X, y


def _train_model():
    X, y = _load_all_training_data()
    if len(set(y)) < 2:
        return None, None
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = LogisticRegression(max_iter=500, random_state=42)
    model.fit(X_scaled, y)
    return model, scaler


@tool
def ml_predict_tool(users_json: str) -> str:
    """
    Use a Logistic Regression model to predict loan conversion probability
    for a list of customers. The model is trained on all existing customer
    data using synthetic conversion labels.
    Input: JSON string with a 'users' list or a plain JSON array.
    Returns: JSON with customers scored by ML probability (threshold ≥ 0.5).
    """
    try:
        data = json.loads(users_json)
        users = data if isinstance(data, list) else data.get("users", [])
    except (json.JSONDecodeError, KeyError):
        return json.dumps({"status": "error", "message": "Invalid JSON input", "candidates": []})

    model, scaler = _train_model()
    if model is None:
        return json.dumps({"status": "error", "message": "Not enough training data", "candidates": []})

    candidates = []
    for user in users:
        features = np.array([_extract_features(user)])
        features_scaled = scaler.transform(features)
        probability = float(model.predict_proba(features_scaled)[0][1])

        if probability >= 0.5:
            candidates.append({
                **user,
                "decision_method": "ml",
                "conversion_score": round(probability, 3),
                "scoring_reason": f"ML model predicted {probability:.1%} conversion probability",
            })

    return json.dumps({
        "status": "success",
        "method": "ml",
        "total_input": len(users),
        "total_candidates": len(candidates),
        "candidates": candidates,
    })
