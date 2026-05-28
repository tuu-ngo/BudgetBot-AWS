"""Lambda 3 — Chat handler.

Wraps the chat routes (/chat, /chat/history) as a separate Lambda function.
Uses the same FastAPI app — API Gateway routing rules direct /chat/* to this Lambda.

Alternatively: deploy as a standalone FastAPI sub-app (see comment below).

Handler: src/lambdas/lambda_chat.handler
"""
from src.app import app  # reuse the full FastAPI app; API GW path-based routing handles isolation

try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    handler = None

# ─── Alternative: standalone sub-app (lighter cold start) ────────────────────
# If you want a truly separate FastAPI app for the Chat Lambda:
#
# from fastapi import FastAPI, Header, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from typing import Optional
# from src.adapters import factory
# from src.handlers.chat_handler import handle_chat, handle_get_chat_history
#
# chat_app = FastAPI(title="BudgetBot Chat Lambda")
# ai_client = factory.make_ai()
# userstore  = factory.make_userstore()
#
# class ChatRequest(BaseModel):
#     message: str
#
# @chat_app.post("/chat")
# def chat(body: ChatRequest, x_user_id: Optional[str] = Header(default=None)):
#     user_id = x_user_id or "test-user-001"
#     return handle_chat(user_id, body.message, ai_client, userstore)
#
# @chat_app.get("/chat/history")
# def history(limit: int = 50, x_user_id: Optional[str] = Header(default=None)):
#     user_id = x_user_id or "test-user-001"
#     return handle_get_chat_history(user_id, limit, userstore)
#
# handler = Mangum(chat_app, lifespan="off")
