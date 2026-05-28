"""Lambda 1 — API Gateway handler.

Wraps the FastAPI app with Mangum for Lambda + API Gateway proxy integration.
Handles all user-facing HTTP routes: upload, summary, transactions, users, budget-caps.

Deploy: set handler to  src/lambdas/lambda_api.handler
"""
from src.app import app  # FastAPI app — same app used by uvicorn locally

try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    # Mangum not installed — only happens during local dev where this file isn't used
    handler = None
