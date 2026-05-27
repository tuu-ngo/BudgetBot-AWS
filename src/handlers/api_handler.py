"""Business logic for Lambda 1 — API Gateway handler.

Handles: /upload, /summary, /transactions, /files, /users CRUD, /budget-caps.

FLOW_MODE=local  → upload processes CSV inline (sync, no SQS needed)
FLOW_MODE=aws    → upload creates file record + presigned PUT URL + queues SQS message
"""
import csv
import io
import json
import logging
from typing import Optional

from src.config import config

logger = logging.getLogger(__name__)


# =============================================================================
# CSV parsing (shared between local-flow inline and parser lambda)
# =============================================================================

def parse_csv(data: bytes) -> list[dict]:
    """Parse a bank-statement CSV into a list of {date, description, amount} dicts."""
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    header = [c.lower().strip() for c in rows[0]]
    if "date" in header and "amount" in header:
        idx = {col: i for i, col in enumerate(header)}
        data_rows = rows[1:]
    else:
        idx = {"date": 0, "description": 1, "amount": 2}
        data_rows = rows

    parsed = []
    for r in data_rows:
        if len(r) < 3 or not r[idx.get("date", 0)].strip():
            continue
        try:
            parsed.append({
                "date":        r[idx.get("date", 0)].strip(),
                "description": r[idx.get("description", 1)].strip(),
                "amount":      int(float(r[idx.get("amount", 2)].strip().replace(",", ""))),
            })
        except (ValueError, IndexError):
            continue
    return parsed


# =============================================================================
# Upload — two modes
# =============================================================================

def handle_upload(
    user_id: str,
    filename: str,
    data: bytes,
    storage,
    userstore,
    ai_client=None,
) -> dict:
    """
    FLOW_MODE=local:
        Store file → create file record → parse CSV → categorize inline → insert txns → return result.

    FLOW_MODE=aws:
        Create file record (status='pending') → generate presigned S3 PUT URL →
        send SQS message → return {presigned_url, file_id, s3_key}.
        Parsing happens in Lambda Parser triggered by SQS.
    """
    if config.flow_mode == "aws":
        return _upload_aws(user_id, filename, data, storage, userstore)
    return _upload_local(user_id, filename, data, storage, userstore, ai_client)


def _upload_local(user_id, filename, data, storage, userstore, ai_client):
    """Synchronous inline processing — local dev."""
    from src.handlers.parser_handler import process_rows

    s3_key = f"{user_id}/{filename}"
    location = storage.put(s3_key, data)

    file_record = userstore.create_file(user_id=user_id, file_name=filename, status="done")
    file_id = file_record["file_id"]

    rows = parse_csv(data)
    results = process_rows(
        rows=rows,
        file_id=file_id,
        user_id=user_id,
        ai_client=ai_client,
        userstore=userstore,
    )

    return {
        "flow_mode":         "local",
        "filename":          filename,
        "file_id":           file_id,
        "stored_at":         location,
        "rows_parsed":       len(rows),
        "rows_inserted":     results["inserted"],
        "rows_review":       results["review_count"],
        "sample_categorized": results["samples"],
    }


def _upload_aws(user_id, filename, data, storage, userstore):
    """AWS flow — returns presigned URL for direct S3 PUT."""
    import boto3

    s3_key = f"uploads/{user_id}/{filename}"
    file_record = userstore.create_file(user_id=user_id, file_name=filename, status="pending")
    file_id = file_record["file_id"]

    # Generate presigned PUT URL (client uploads directly to S3)
    s3_client = boto3.client("s3", region_name=config.aws_region)
    presigned_url = s3_client.generate_presigned_url(
        "put_object",
        Params={"Bucket": config.storage_bucket, "Key": s3_key},
        ExpiresIn=300,
    )

    # Send SQS message so Parser Lambda can process after S3 upload
    sqs = boto3.client("sqs", region_name=config.aws_region)
    sqs.send_message(
        QueueUrl=config.sqs_queue_url,
        MessageBody=json.dumps({
            "user_id":  user_id,
            "file_id":  file_id,
            "s3_key":   s3_key,
            "filename": filename,
        }),
    )

    logger.info("Upload queued: file_id=%s s3_key=%s", file_id, s3_key)
    return {
        "flow_mode":    "aws",
        "file_id":      file_id,
        "s3_key":       s3_key,
        "presigned_url": presigned_url,
        "status":       "pending",
        "message":      "PUT the file to presigned_url, then poll /upload/{file_id}/status",
    }


# =============================================================================
# File status polling (aws mode)
# =============================================================================

def handle_file_status(file_id: str, userstore) -> dict:
    file_rec = userstore.get_file(file_id)
    if not file_rec:
        return None
    return file_rec


# =============================================================================
# Summary & transactions
# =============================================================================

def handle_summary(user_id: str, month: Optional[str], userstore) -> dict:
    raw = userstore.summary(user_id, month=month)
    total = sum(v["total"] for v in raw.values())
    sorted_cats = sorted(raw.items(), key=lambda kv: -abs(kv[1]["total"]))
    return {
        "user_id":     user_id,
        "month":       month,
        "total_spend": total,
        "by_category": dict(sorted_cats),
        "top_3_drivers": [
            {"category": cat, "total": v["total"], "count": v["count"]}
            for cat, v in sorted_cats[:3]
        ],
    }


def handle_list_transactions(
    user_id: str,
    month: Optional[str],
    userstore,
    review_status: Optional[str] = None,
) -> dict:
    txns = userstore.list_transactions(user_id, month=month, review_status=review_status)
    return {"user_id": user_id, "month": month, "transactions": txns}


def handle_review_queue(user_id: str, userstore) -> dict:
    txns = userstore.list_review_queue(user_id)
    return {"user_id": user_id, "count": len(txns), "transactions": txns}


def handle_update_category(transaction_id: str, category: str, userstore) -> dict:
    txn = userstore.update_transaction_category(transaction_id, category)
    if not txn:
        return None
    return {"status": "updated", "transaction": txn}


# =============================================================================
# Budget caps
# =============================================================================

def handle_get_caps(user_id: str, userstore) -> dict:
    caps = userstore.get_budget_caps(user_id)
    return {"user_id": user_id, "budget_caps": caps}


def handle_set_cap(user_id: str, category: str, cap_amount: int, userstore) -> dict:
    cap = userstore.set_budget_cap(user_id, category, cap_amount)
    return {"status": "ok", "cap": cap}


def handle_delete_cap(user_id: str, category: str, userstore) -> dict:
    deleted = userstore.delete_budget_cap(user_id, category)
    return {"status": "deleted" if deleted else "not_found"}
