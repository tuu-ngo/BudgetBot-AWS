"""Lambda 4 — Budget cap checker + SNS alerter.

Trigger: async invoke from Lambda Parser (InvocationType='Event').
Handler: src/lambdas/lambda_budget.handler

Event shape:
    {"user_id": "uuid", "file_id": "uuid"}

Flow:
    1. Load user's budget caps from RDS
    2. Load current-month spending totals from RDS
    3. For each category where |spent| >= cap → publish SNS email alert
"""
import logging

from src.adapters import factory
from src.handlers.budget_handler import handle_budget_event

logger = logging.getLogger()
logger.setLevel("INFO")

# Initialise adapter once (warm Lambda reuse)
_userstore = factory.make_userstore()


def handler(event: dict, context) -> dict:
    logger.info("Budget Lambda invoked: %s", event)
    result = handle_budget_event(event=event, userstore=_userstore)
    logger.info("Budget check result: %s", result)
    return result
