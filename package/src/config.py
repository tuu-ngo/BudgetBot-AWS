"""Env-driven config for BudgetBot."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _bool(name: str, default: str = "false") -> bool:
    return _env(name, default).lower() in ("1", "true", "yes")


class Config:
    # AI
    ai_backend: str = _env("AI_BACKEND", "local")
    ai_model_id: str = _env("AI_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0")
    aws_region: str = _env("AWS_REGION", "ap-southeast-1")

    # Object storage
    storage_backend: str = _env("STORAGE_BACKEND", "local")
    storage_bucket: str = _env("STORAGE_BUCKET", "")
    storage_local_dir: str = _env("STORAGE_LOCAL_DIR", "./_data/uploads")

    # Database — PostgreSQL only
    userstore_postgres_url: str = _env("USERSTORE_POSTGRES_URL", "")

    # Flow mode:
    #   local — upload is processed inline (synchronous, no SQS/S3 event needed)
    #   aws   — upload returns presigned URL; parsing is SQS-triggered
    flow_mode: str = _env("FLOW_MODE", "local")

    # SQS
    sqs_queue_url: str = _env("SQS_QUEUE_URL", "")

    # SNS (budget alerts)
    sns_topic_arn: str = _env("SNS_TOPIC_ARN", "")

    # Budget Lambda name (for async invoke from Parser Lambda)
    budget_lambda_name: str = _env("BUDGET_LAMBDA_NAME", "budgetbot-budget-handler")

    # Parser Lambda name (for local async invoke simulation — unused in aws mode)
    parser_lambda_name: str = _env("PARSER_LAMBDA_NAME", "budgetbot-parser")

    # Confidence threshold — transactions below this go to review queue
    review_threshold: float = float(_env("REVIEW_THRESHOLD", "0.60"))

    # Misc
    default_user_id: str = _env("DEFAULT_USER_ID", "00000000-0000-0000-0000-000000000001")
    log_level: str = _env("LOG_LEVEL", "INFO")

    # Frontend serving (set false for split deploy: CloudFront+S3 or Amplify)
    serve_frontend: bool = _bool("SERVE_FRONTEND", "true")
    cors_origins: str = _env("CORS_ORIGINS", "*")


config = Config()
