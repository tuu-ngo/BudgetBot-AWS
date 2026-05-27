"""Env-driven config for BudgetBot."""
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Config:
    ai_backend: str = _env("AI_BACKEND", "local")
    ai_model_id: str = _env("AI_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0")
    aws_region: str = _env("AWS_REGION", "ap-southeast-1")

    storage_backend: str = _env("STORAGE_BACKEND", "local")
    storage_bucket: str = _env("STORAGE_BUCKET", "")
    storage_local_dir: str = _env("STORAGE_LOCAL_DIR", "./_data/uploads")

    # PostgreSQL — the only supported database backend
    userstore_postgres_url: str = _env("USERSTORE_POSTGRES_URL", "")

    default_user_id: str = _env("DEFAULT_USER_ID", "test-user-001")
    log_level: str = _env("LOG_LEVEL", "INFO")

    # Frontend serving (opt-out so backend can be pure API for split deploys)
    serve_frontend: bool = _env("SERVE_FRONTEND", "true").lower() == "true"
    cors_origins: str = _env("CORS_ORIGINS", "*")

config = Config()
