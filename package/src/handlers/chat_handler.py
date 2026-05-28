"""Business logic for Lambda 3 — Chat handler.

Flow:
    1. Load recent chat history from RDS (conversation context)
    2. Load user's recent transactions from RDS (spending context for AI)
    3. Call Bedrock (or LocalAI) with spending context injected into system prompt
    4. Save turn to chat_history
    5. Return response
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def handle_chat(
    user_id: str,
    input_text: str,
    ai_client,
    userstore,
    month: Optional[str] = None,
) -> dict:
    """Process a chat message with spending context from RDS."""

    # 1. Recent conversation history (last 10 turns, oldest-first for Bedrock messages)
    history_records = userstore.get_chat_history(user_id, limit=10)
    context_messages = []
    for entry in reversed(history_records):
        context_messages.append({"role": "user",      "content": entry["input"]})
        context_messages.append({"role": "assistant", "content": entry["output"]})

    # 2. Spending context: use the requested month if given, otherwise cap at the
    #    200 most-recent transactions to prevent context-window overflow (FP-10).
    transactions = userstore.list_transactions(user_id, month=month)
    if not month:
        transactions = transactions[:200]

    # 3. Call AI
    try:
        response_text = ai_client.chat(
            message=input_text,
            context=context_messages,
            transactions=transactions,
        )
    except AttributeError:
        response_text = (
            "Chat is not configured. "
            "Set AI_BACKEND=bedrock and ensure Bedrock model access is enabled."
        )
    except Exception as exc:
        logger.exception("AI chat error: %s", exc)
        response_text = f"Sorry, I encountered an error: {exc}"

    # 4. Persist
    record = userstore.add_chat_history(
        user_id=user_id,
        input_text=input_text,
        output_text=response_text,
    )

    return {
        "user_id":         user_id,
        "input":           input_text,
        "output":          response_text,
        "chat_history_id": record["chat_history_id"],
        "time":            record["time"],
    }


def handle_get_chat_history(user_id: str, limit: int, userstore) -> dict:
    history = userstore.get_chat_history(user_id, limit=limit)
    return {"user_id": user_id, "count": len(history), "history": history}
