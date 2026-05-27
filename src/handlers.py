"""Endpoint business logic for BudgetBot."""
import csv
import io
from typing import Optional


def _parse_csv(data: bytes) -> list:
    """Expect CSV columns: date, description, amount. Header row optional."""
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    # Detect header
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
                "date": r[idx.get("date", 0)].strip(),
                "description": r[idx.get("description", 1)].strip(),
                "amount": int(float(r[idx.get("amount", 2)].strip().replace(",", ""))),
            })
        except (ValueError, IndexError):
            continue
    return parsed


def handle_upload(
    user_id: str,
    filename: str,
    data: bytes,
    ai_client,
    storage,
    userstore,
) -> dict:
    """Parse CSV → create File record → categorize each row via AI → persist transactions."""
    # 1. Store raw file to object storage (S3 or local)
    key = f"{user_id}/{filename}"
    location = storage.put(key, data)

    # 2. Create a File record in PostgreSQL
    file_record = userstore.create_file(user_id=user_id, file_name=filename)
    file_id = file_record["file_id"]

    # 3. Parse CSV rows
    rows = _parse_csv(data)

    # 4. Categorize each row and insert transactions
    inserted = 0
    samples = []
    for row in rows:
        cat_result = ai_client.categorize(
            description=row["description"], amount=row["amount"], date=row["date"]
        )
        txn = {
            "time": row["date"],
            "description": row["description"],
            "amount": row["amount"],
            "category": cat_result["category"],
            "confident": cat_result.get("confidence", 0),
        }
        userstore.add_transaction(file_id, txn)
        inserted += 1
        if len(samples) < 5:
            samples.append(txn)
    return {
        "filename": filename,
        "file_id": file_id,
        "stored_at": location,
        "rows_parsed": len(rows),
        "rows_inserted": inserted,
        "sample_categorized": samples,
    }


def handle_summary(user_id: str, month: Optional[str], userstore) -> dict:
    summary = userstore.summary(user_id, month=month)
    total = sum(v["total"] for v in summary.values())
    sorted_cats = sorted(summary.items(), key=lambda kv: -abs(kv[1]["total"]))
    return {
        "user_id": user_id,
        "month": month,
        "total_spend": total,
        "by_category": dict(sorted_cats),
        "top_3_drivers": [
            {"category": cat, "total": v["total"], "count": v["count"]}
            for cat, v in sorted_cats[:3]
        ],
    }


def handle_list_transactions(user_id: str, month: Optional[str], userstore) -> dict:
    return {"user_id": user_id, "month": month, "transactions": userstore.list_transactions(user_id, month=month)}


def handle_chat(user_id: str, input_text: str, ai_client, userstore) -> dict:
    """Process a chat message: send to AI → save to chat_history → return response."""
    # Get recent chat history for context
    history = userstore.get_chat_history(user_id, limit=10)

    # Build context from history (oldest first for conversation flow)
    context_messages = []
    for entry in reversed(history):
        context_messages.append({"role": "user", "content": entry["input"]})
        context_messages.append({"role": "assistant", "content": entry["output"]})

    # Get AI response (use categorize as a proxy — the AI client can be extended)
    # For now, generate a simple response based on the input
    try:
        ai_response = ai_client.chat(input_text, context=context_messages)
    except AttributeError:
        # Fallback if AI client doesn't have a chat method
        ai_response = f"I received your message: '{input_text}'. Chat AI is not configured yet."

    # Save to chat history
    record = userstore.add_chat_history(
        user_id=user_id,
        input_text=input_text,
        output_text=ai_response,
    )

    return {
        "user_id": user_id,
        "input": input_text,
        "output": ai_response,
        "chat_history_id": record["chat_history_id"],
        "time": record["time"],
    }


def handle_get_chat_history(user_id: str, limit: int, userstore) -> dict:
    """Retrieve chat history for a user."""
    history = userstore.get_chat_history(user_id, limit=limit)
    return {
        "user_id": user_id,
        "count": len(history),
        "history": history,
    }
