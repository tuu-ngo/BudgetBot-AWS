"""Budget cap checker.

Called after upload or via /budget/check to compare current-month spending
against the user's configured budget caps.

Flow:
    1. Get user's budget caps from RDS
    2. Query current-month spending per category from RDS
    3. Return warning details for any category where spending is over cap
"""
import logging

logger = logging.getLogger(__name__)


def check_budget_caps(user_id: str, userstore) -> dict:
    """
    Core logic: compare this month's spending against budget caps.
    Returns a dict the frontend can render directly as budget warnings.
    """
    caps = userstore.get_budget_caps(user_id)
    if not caps:
        logger.debug("No budget caps set for user_id=%s", user_id)
        return {"user_id": user_id, "warnings_count": 0, "warnings": [], "details": []}

    spending = userstore.spending_this_month(user_id)
    logger.info("user_id=%s monthly spending: %s", user_id, spending)

    warnings = []
    details = []

    for cap in caps:
        category   = cap["category"]
        cap_amount = cap["cap_amount"]
        spent      = spending.get(category, 0)

        status = "ok"
        if spent > cap_amount:
            status = "exceeded"
            pct = int(spent / cap_amount * 100)
            warnings.append({
                "category": category,
                "spent": spent,
                "cap_amount": cap_amount,
                "over_by": spent - cap_amount,
                "percent": pct,
                "message": (
                    f"{category} spending is over budget: "
                    f"{spent:,} / {cap_amount:,} ({pct}%)."
                ),
            })
        elif spent == cap_amount and cap_amount > 0:
            status = "reached"

        details.append({
            "category":   category,
            "cap_amount": cap_amount,
            "spent":      spent,
            "status":     status,
            "percent":    int(spent / cap_amount * 100) if cap_amount > 0 else 0,
        })

    logger.info("user_id=%s budget check done: warnings=%d", user_id, len(warnings))
    return {
        "user_id": user_id,
        "warnings_count": len(warnings),
        "warnings": warnings,
        "details": details,
    }


def handle_budget_event(event: dict, userstore) -> dict:
    """Entry point called by lambda_budget.py Lambda handler."""
    user_id = event.get("user_id")
    if not user_id:
        logger.error("budget event missing user_id: %s", event)
        return {"error": "missing user_id"}
    return check_budget_caps(user_id, userstore)
