"""BudgetBot — FastAPI application.

Local dev:  uvicorn src.app:app --reload --port 8000
Lambda:     imported by src/lambdas/lambda_api.py and lambda_chat.py (via Mangum)

This file is a thin router. All business logic lives in src/handlers/.
"""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import config
from src.adapters import factory
from src.handlers import api_handler, chat_handler, budget_handler

app = FastAPI(title="BudgetBot — AI Money Coach")

_origins = (
    ["*"] if config.cors_origins == "*"
    else [o.strip() for o in config.cors_origins.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Adapters — initialised once at startup
ai_client = factory.make_ai()
storage    = factory.make_storage()
userstore  = factory.make_userstore()


def _uid(x_user_id: Optional[str]) -> str:
    return x_user_id or config.default_user_id


# =============================================================================
# Pydantic request bodies
# =============================================================================

class UserCreate(BaseModel):
    account:  str
    password: str
    budget:   int = 0


class UserUpdate(BaseModel):
    account:  Optional[str] = None
    password: Optional[str] = None
    budget:   Optional[int] = None


class ChatRequest(BaseModel):
    message: str
    month:   Optional[str] = None  # optional month filter for spending context


class CategoryUpdate(BaseModel):
    category: str


class BudgetCapBody(BaseModel):
    cap_amount: int


# =============================================================================
# Health
# =============================================================================

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "flow_mode": config.flow_mode,
        "backends": {
            "ai":      config.ai_backend,
            "storage": config.storage_backend,
            "db":      "postgres",
        },
    }


# =============================================================================
# User CRUD
# =============================================================================

@app.post("/users", status_code=201)
def create_user(body: UserCreate) -> dict:
    try:
        user = userstore.create_user(account=body.account, password=body.password, budget=body.budget)
        return {"status": "created", "user": user}
    except Exception as e:
        if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Account already exists")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/{user_id}")
def get_user(user_id: str) -> dict:
    user = userstore.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.pop("password", None)
    return {"user": user}


@app.put("/users/{user_id}")
def update_user(user_id: str, body: UserUpdate) -> dict:
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    user = userstore.update_user(user_id, **updates)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "updated", "user": user}


@app.delete("/users/{user_id}")
def delete_user(user_id: str) -> dict:
    deleted = userstore.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted", "user_id": user_id}


# =============================================================================
# Upload + file status
# =============================================================================

@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    """
    FLOW_MODE=local  → processes inline, returns categorized results immediately.
    FLOW_MODE=aws    → returns {presigned_url, file_id}; parsing happens async via SQS.
    """
    user_id = _uid(x_user_id)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        return api_handler.handle_upload(
            user_id=user_id,
            filename=file.filename or "statement.csv",
            data=data,
            storage=storage,
            userstore=userstore,
            ai_client=ai_client,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/upload/{file_id}/status")
def file_status(file_id: str) -> dict:
    """Poll processing status for a file (useful in aws flow_mode)."""
    result = api_handler.handle_file_status(file_id, userstore)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


# =============================================================================
# Summary & Transactions
# =============================================================================

@app.get("/summary")
def summary(
    month: Optional[str] = None,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    return api_handler.handle_summary(_uid(x_user_id), month, userstore)


@app.get("/transactions")
def transactions(
    month:         Optional[str] = None,
    review_status: Optional[str] = None,
    x_user_id:     Optional[str] = Header(default=None),
) -> dict:
    return api_handler.handle_list_transactions(
        _uid(x_user_id), month, userstore, review_status=review_status
    )


@app.get("/transactions/review")
def review_queue(x_user_id: Optional[str] = Header(default=None)) -> dict:
    """Transactions with low AI confidence that need human review."""
    return api_handler.handle_review_queue(_uid(x_user_id), userstore)


@app.patch("/transactions/{transaction_id}/category")
def update_category(
    transaction_id: str,
    body: CategoryUpdate,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    """User manually corrects a transaction category."""
    result = api_handler.handle_update_category(transaction_id, body.category, userstore)
    if not result:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result


# =============================================================================
# Files list
# =============================================================================

@app.get("/files")
def list_files(x_user_id: Optional[str] = Header(default=None)) -> dict:
    uid = _uid(x_user_id)
    return {"user_id": uid, "files": userstore.list_files(uid)}


# =============================================================================
# Budget caps
# =============================================================================

@app.get("/budget-caps")
def get_caps(x_user_id: Optional[str] = Header(default=None)) -> dict:
    return api_handler.handle_get_caps(_uid(x_user_id), userstore)


@app.put("/budget-caps/{category}")
def set_cap(
    category: str,
    body: BudgetCapBody,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    try:
        return api_handler.handle_set_cap(_uid(x_user_id), category, body.cap_amount, userstore)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/budget-caps/{category}")
def delete_cap(
    category: str,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    return api_handler.handle_delete_cap(_uid(x_user_id), category, userstore)


# =============================================================================
# Chat (Lambda 3 in AWS; same app locally)
# =============================================================================

@app.post("/chat")
def chat(
    body: ChatRequest,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    user_id = _uid(x_user_id)
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    return chat_handler.handle_chat(
        user_id=user_id,
        input_text=body.message,
        ai_client=ai_client,
        userstore=userstore,
        month=body.month,
    )


@app.get("/chat/history")
def chat_history(
    limit:     int = 50,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    return chat_handler.handle_get_chat_history(_uid(x_user_id), limit, userstore)


# =============================================================================
# Budget check endpoint (for manual trigger / testing)
# =============================================================================

@app.post("/budget/check")
def budget_check(x_user_id: Optional[str] = Header(default=None)) -> dict:
    """Manually trigger a budget cap check (useful for local testing)."""
    return budget_handler.check_and_alert(_uid(x_user_id), userstore)


# =============================================================================
# Static frontend (disabled when deploying frontend separately)
# =============================================================================

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

if config.serve_frontend:
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")
