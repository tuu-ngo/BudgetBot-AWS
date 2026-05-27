"""Business logic for Lambda 4 — Budget cap checker + SNS alerter.

Triggered by: Lambda Parser (async invoke) after writing transactions.

Flow:
    1. Get user's budget caps from RDS
    2. Query current-month spending per category from RDS
    3. For each cap: if |spending| >= cap_amount → publish SNS alert
    4. Return summary of alerts sent

Local mode: SNS publish is skipped if SNS_TOPIC_ARN is not set (logs warning).
"""
import logging

from src.config import config

logger = logging.getLogger(__name__)


def check_and_alert(user_id: str, userstore) -> dict:
    """
    Core logic: compare this month's spending against budget caps.
    Returns a dict describing which caps were exceeded and whether alerts were sent.
    """
    caps = userstore.get_budget_caps(user_id)
    if not caps:
        logger.debug("No budget caps set for user_id=%s", user_id)
        return {"user_id": user_id, "alerts_sent": 0, "details": []}

    spending = userstore.spending_this_month(user_id)
    logger.info("user_id=%s monthly spending: %s", user_id, spending)

    alerts_sent = 0
    details = []

    for cap in caps:
        category   = cap["category"]
        cap_amount = cap["cap_amount"]
        spent      = spending.get(category, 0)

        status = "ok"
        if spent >= cap_amount:
            status = "exceeded"
            pct = int(spent / cap_amount * 100)
            sent = _send_sns_alert(
                user_id=user_id,
                category=category,
                spent=spent,
                cap=cap_amount,
                pct=pct,
            )
            if sent:
                alerts_sent += 1

        details.append({
            "category":   category,
            "cap_amount": cap_amount,
            "spent":      spent,
            "status":     status,
        })

    logger.info("user_id=%s budget check done: alerts_sent=%d", user_id, alerts_sent)
    return {"user_id": user_id, "alerts_sent": alerts_sent, "details": details}


def handle_budget_event(event: dict, userstore) -> dict:
    """Entry point called by lambda_budget.py Lambda handler."""
    user_id = event.get("user_id")
    if not user_id:
        logger.error("budget event missing user_id: %s", event)
        return {"error": "missing user_id"}
    return check_and_alert(user_id, userstore)


# =============================================================================
# SNS helper
# =============================================================================

def _send_sns_alert(
    user_id: str,
    category: str,
    spent: int,
    cap: int,
    pct: int,
) -> bool:
    """Publish an SNS notification. Returns True if published, False if skipped/failed."""
    if not config.sns_topic_arn:
        logger.warning(
            "SNS_TOPIC_ARN not set — budget alert suppressed "
            "(user=%s category=%s spent=%d cap=%d)",
            user_id, category, spent, cap,
        )
        return False

    try:
        import boto3
        sns = boto3.client("sns", region_name=config.aws_region)
        subject = f"[BudgetBot] {category} budget exceeded ({pct}%)"
        message = (
            f"BudgetBot Alert\n"
            f"User:     {user_id}\n"
            f"Category: {category}\n"
            f"Spent:    {spent:,}\n"
            f"Cap:      {cap:,}\n"
            f"Usage:    {pct}%\n\n"
            "Log in to BudgetBot to review your transactions."
        )
        sns.publish(
            TopicArn=config.sns_topic_arn,
            Subject=subject,
            Message=message,
        )
        logger.info("SNS alert sent: category=%s pct=%d%%", category, pct)
        return True
    except Exception as exc:
        logger.error("SNS publish failed: %s", exc)
        return False
