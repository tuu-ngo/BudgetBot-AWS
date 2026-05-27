"""FastAPI app for BudgetBot. Runtime-agnostic. PostgreSQL enabled."""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import config
from src.adapters import factory
from src import handlers


app = FastAPI(title="BudgetBot — W7 Capstone Starter")


# CORS — allow frontend to live on a different origin (CloudFront / Amplify / separate ALB).
# CORS_ORIGINS env var controls this; default '*' is permissive for hackathon.
_allowed = ["*"] if config.cors_origins == "*" else [o.strip() for o in config.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ai_client = factory.make_ai()
storage = factory.make_storage()
userstore = factory.make_userstore()


def _resolve_user_id(x_user_id: Optional[str]) -> str:
    return x_user_id or config.default_user_id


# =============================================================================
# Pydantic models for request bodies
# =============================================================================

class UserCreate(BaseModel):
    account: str
    password: str
    budget: int = 0


class UserUpdate(BaseModel):
    account: Optional[str] = None
    password: Optional[str] = None
    budget: Optional[int] = None


class ChatRequest(BaseModel):
    message: str


# =============================================================================
# Health
# =============================================================================

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "backends": {
            "ai": config.ai_backend,
            "storage": "postgres",
        },
    }


# =============================================================================
# User CRUD
# =============================================================================

@app.post("/users")
def create_user(body: UserCreate) -> dict:
    """Create a new user."""
    try:
        user = userstore.create_user(
            account=body.account,
            password=body.password,
            budget=body.budget,
        )
        return {"status": "created", "user": user}
    except Exception as e:
        if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Account already exists")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/{user_id}")
def get_user(user_id: str) -> dict:
    """Get user by ID."""
    user = userstore.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Don't expose password in GET response
    user.pop("password", None)
    return {"user": user}


@app.put("/users/{user_id}")
def update_user(user_id: str, body: UserUpdate) -> dict:
    """Update user fields."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    user = userstore.update_user(user_id, **updates)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "updated", "user": user}


@app.delete("/users/{user_id}")
def delete_user(user_id: str) -> dict:
    """Delete a user and all associated data (cascade)."""
    deleted = userstore.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted", "user_id": user_id}


# =============================================================================
# File upload + transaction processing
# =============================================================================

@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    user_id = _resolve_user_id(x_user_id)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    return handlers.handle_upload(
        user_id=user_id,
        filename=file.filename or "statement.csv",
        data=data,
        ai_client=ai_client,
        storage=storage,
        userstore=userstore,
    )


# =============================================================================
# Transactions & Summary
# =============================================================================

@app.get("/summary")
def summary(
    month: Optional[str] = None,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    """`month` format: YYYY-MM. Omit for all-time summary."""
    return handlers.handle_summary(_resolve_user_id(x_user_id), month, userstore)


@app.get("/transactions")
def transactions(
    month: Optional[str] = None,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    return handlers.handle_list_transactions(_resolve_user_id(x_user_id), month, userstore)


# =============================================================================
# Files list
# =============================================================================

@app.get("/files")
def list_files(
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    """List all uploaded files for a user."""
    user_id = _resolve_user_id(x_user_id)
    files = userstore.list_files(user_id)
    return {"user_id": user_id, "files": files}


# =============================================================================
# Chat
# =============================================================================

@app.post("/chat")
def chat(
    body: ChatRequest,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    """Send a chat message and get an AI response. Saves to chat_history."""
    user_id = _resolve_user_id(x_user_id)
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    return handlers.handle_chat(
        user_id=user_id,
        input_text=body.message,
        ai_client=ai_client,
        userstore=userstore,
    )


@app.get("/chat/history")
def chat_history(
    limit: int = 50,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    """Retrieve chat history for a user."""
    user_id = _resolve_user_id(x_user_id)
    return handlers.handle_get_chat_history(user_id, limit, userstore)


# ---- Static frontend ----
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


if config.serve_frontend:
    @app.get("/")
    def index() -> FileResponse:
        """Convenience: serves frontend/index.html at /. Set SERVE_FRONTEND=false
        if you deploy the frontend separately (CloudFront+S3, Amplify, ALB)."""
        return FileResponse(FRONTEND_DIR / "index.html")
