"""Lambda 2 — SQS-triggered CSV parser.

Trigger:  SQS queue (standard queue, batch size 1 recommended for isolation).
Handler:  src/lambdas/lambda_parser.handler

Event shape (one SQS record body):
    {
        "user_id":  "uuid",
        "file_id":  "uuid",
        "s3_key":   "uploads/{user_id}/{filename}",
        "filename": "statement.csv"
    }

On success: writes transactions to RDS, updates file status → 'done',
            async-invokes Budget Lambda.
On failure: updates file status → 'error', logs exception.
"""
import logging

from src.adapters import factory
from src.handlers.parser_handler import process_sqs_event

logger = logging.getLogger()
logger.setLevel("INFO")

# Initialise adapters once (warm Lambda reuse)
_storage   = factory.make_storage()
_ai_client = factory.make_ai()
_userstore = factory.make_userstore()


def handler(event: dict, context) -> dict:
    logger.info("Parser Lambda invoked: %d SQS records", len(event.get("Records", [])))
    return process_sqs_event(
        event=event,
        context=context,
        storage=_storage,
        ai_client=_ai_client,
        userstore=_userstore,
    )
