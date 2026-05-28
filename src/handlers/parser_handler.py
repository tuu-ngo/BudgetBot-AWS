"""Business logic for Lambda 2 — SQS-triggered CSV parser.

Entry points:
    process_sqs_event(event, context)  — called by lambda_parser.py (AWS SQS trigger)
    process_rows(rows, ...)            — called directly by api_handler in local mode

Flow per SQS message:
    1. Download CSV from S3
    2. parse_csv → rows
    3. For each row: Bedrock few-shot categorize (confidence 0.0–1.0)
    4. Insert into RDS:
       - confidence >= threshold  → review_status='ok'
       - confidence <  threshold  → review_status='review'
    5. Update file status → 'done'
    6. Async invoke Budget Lambda (fire-and-forget)
"""
import json
import logging

from src.config import config

logger = logging.getLogger(__name__)


# =============================================================================
# Core row-processing logic (shared by SQS handler and local inline flow)
# =============================================================================

def process_rows(
    rows: list[dict],
    file_id: str,
    user_id: str,
    ai_client,
    userstore,
) -> dict:
    """Categorize and persist each CSV row. Returns summary dict."""
    inserted = 0
    review_count = 0
    samples: list[dict] = []

    for row in rows:
        result = ai_client.categorize(
            description=row["description"],
            amount=row["amount"],
            date=row["date"],
        )
        txn_data = {
            "time":        row["date"],
            "description": row["description"],
            "amount":      row["amount"],
            "category":    result["category"],
            "confident":   result["confidence"],
        }
        saved = userstore.add_transaction(
            file_id=file_id,
            txn=txn_data,
            review_threshold=config.review_threshold,
        )
        inserted += 1
        if saved["review_status"] == "review":
            review_count += 1
        if len(samples) < 5:
            samples.append(saved)

    return {"inserted": inserted, "review_count": review_count, "samples": samples}


# =============================================================================
# SQS event handler (AWS Lambda trigger)
# =============================================================================

def process_sqs_event(event: dict, context, storage, ai_client, userstore) -> dict:
    """Process all SQS messages in one Lambda invocation batch."""
    from src.handlers.api_handler import parse_csv

    results = []
    for record in event.get("Records", []):
        body = json.loads(record["body"])
        file_id = body["file_id"]
        s3_key = body.get("s3_key") or body.get("file_name")
        if not s3_key:
            raise ValueError("Missing s3_key/file_name in SQS message")
        filename = body.get("filename", s3_key.split("/")[-1])
        user_id = body.get("user_id")
        if not user_id:
            file_rec = userstore.get_file(file_id)
            if not file_rec:
                raise ValueError("Missing user_id and file record not found")
            user_id = file_rec["user_id"]

        logger.info("Processing SQS record: file_id=%s s3_key=%s", file_id, s3_key)

        try:
            userstore.update_file_status(file_id, "processing")

            # Download from S3
            data = storage.get(s3_key)
            rows = parse_csv(data)

            result = process_rows(
                rows=rows,
                file_id=file_id,
                user_id=user_id,
                ai_client=ai_client,
                userstore=userstore,
            )

            userstore.update_file_status(file_id, "done")
            logger.info(
                "file_id=%s done: inserted=%d review=%d",
                file_id, result["inserted"], result["review_count"],
            )

            # Async invoke Budget Lambda (fire-and-forget, non-blocking)
            _invoke_budget_lambda(user_id=user_id, file_id=file_id)

            results.append({"file_id": file_id, "status": "done", **result})

        except Exception as exc:
            logger.exception("Failed to process file_id=%s: %s", file_id, exc)
            userstore.update_file_status(file_id, "error")
            results.append({"file_id": file_id, "status": "error", "error": str(exc)})

    return {"processed": len(results), "results": results}


def _invoke_budget_lambda(user_id: str, file_id: str) -> None:
    """Async invoke Budget Handler Lambda. Non-blocking — errors are logged, not raised."""
    if not config.budget_lambda_name:
        logger.debug("BUDGET_LAMBDA_NAME not set — skipping budget check")
        return
    try:
        import boto3
        lambda_client = boto3.client("lambda", region_name=config.aws_region)
        lambda_client.invoke(
            FunctionName=config.budget_lambda_name,
            InvocationType="Event",  # async, fire-and-forget
            Payload=json.dumps({"user_id": user_id, "file_id": file_id}),
        )
        logger.info("Budget Lambda invoked async for user_id=%s", user_id)
    except Exception as exc:
        logger.warning("Could not invoke Budget Lambda: %s", exc)
