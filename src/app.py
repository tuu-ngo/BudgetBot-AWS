"""BudgetBot — FastAPI application.

Local dev:  uvicorn src.app:app --reload --port 8000
Lambda:     imported by src/lambdas/lambda_api.py and lambda_chat.py (via Mangum)

This file is a thin router. All business logic lives in src/handlers/.
"""
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import config
from src.adapters import factory
from src.handlers import api_handler, chat_handler, budget_handler

app = FastAPI(title="BudgetBot — AI Money Coach")

_origins = (
    [o.strip() for o in config.cors_origins.split(",") if o.strip()]
    if config.cors_origins != "*"
    else ["http://localhost:5173", "http://127.0.0.1:5173"]
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

DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


def _uid(x_user_id: str = Header(default=DEFAULT_USER_ID)) -> str:
    """Resolve user from X-User-Id header; falls back to the default test user."""
    return x_user_id or DEFAULT_USER_ID


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
        user = userstore.create_user(
            account=body.account,
            password=body.password,
            budget=body.budget,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"user": user}


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
    user_id: str = Depends(_uid),
) -> dict:
    """
    FLOW_MODE=local  → processes inline, returns categorized results immediately.
    FLOW_MODE=aws    → returns {presigned_url, file_id}; parsing happens async via SQS.
    """
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
    user_id: str = Depends(_uid),
) -> dict:
    return api_handler.handle_summary(user_id, month, userstore)


@app.get("/transactions")
def transactions(
    month:         Optional[str] = None,
    review_status: Optional[str] = None,
    user_id: str = Depends(_uid),
) -> dict:
    return api_handler.handle_list_transactions(
        user_id, month, userstore, review_status=review_status
    )


@app.get("/transactions/review")
def review_queue(user_id: str = Depends(_uid)) -> dict:
    """Transactions with low AI confidence that need human review."""
    return api_handler.handle_review_queue(user_id, userstore)


@app.patch("/transactions/{transaction_id}/category")
def update_category(
    transaction_id: str,
    body: CategoryUpdate,
) -> dict:
    """User manually corrects a transaction category."""
    result = api_handler.handle_update_category(
        transaction_id, body.category, userstore
    )
    if not result:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result


# =============================================================================
# Files list
# =============================================================================

@app.get("/files")
def list_files(user_id: str = Depends(_uid)) -> dict:
    return {"user_id": user_id, "files": userstore.list_files(user_id)}


# =============================================================================
# Budget caps
# =============================================================================

@app.get("/budget-caps")
def get_caps(user_id: str = Depends(_uid)) -> dict:
    return api_handler.handle_get_caps(user_id, userstore)


@app.put("/budget-caps/{category}")
def set_cap(
    category: str,
    body: BudgetCapBody,
    user_id: str = Depends(_uid),
) -> dict:
    try:
        return api_handler.handle_set_cap(user_id, category, body.cap_amount, userstore)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/budget-caps/{category}")
def delete_cap(
    category: str,
    user_id: str = Depends(_uid),
) -> dict:
    return api_handler.handle_delete_cap(user_id, category, userstore)


# =============================================================================
# Chat (Lambda 3 in AWS; same app locally)
# =============================================================================

@app.post("/chat")
def chat(
    body: ChatRequest,
    user_id: str = Depends(_uid),
) -> dict:
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
    limit:   int = 50,
    user_id: str = Depends(_uid),
) -> dict:
    return chat_handler.handle_get_chat_history(user_id, limit, userstore)


# =============================================================================
# Budget check endpoint (frontend warning display)
# =============================================================================

@app.post("/budget/check")
def budget_check(user_id: str = Depends(_uid)) -> dict:
    """Return budget cap warnings for the current user."""
    return budget_handler.check_budget_caps(user_id, userstore)


# =============================================================================
# Static frontend (disabled when deploying frontend separately)
# =============================================================================
# Frontend is a Vite/React SPA. Build it first:
#   cd frontend && npm install && npm run build
# This creates frontend/dist/ which FastAPI serves below.
# =============================================================================

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"

if config.serve_frontend and FRONTEND_DIST_DIR.exists():
    # Serve the built JS/CSS/assets bundle
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIST_DIR / "index.html")

    # SPA fallback: any unknown path returns index.html so React Router can handle it
    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        return FileResponse(FRONTEND_DIST_DIR / "index.html")
