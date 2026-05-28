from src.config import config
from src.adapters import ai, storage, userstore


def make_ai():
    if config.ai_backend == "bedrock":
        return ai.BedrockAI(region=config.aws_region, model_id=config.ai_model_id)
    if config.ai_backend == "local":
        return ai.LocalAI()
    raise ValueError(f"Unknown AI_BACKEND: {config.ai_backend!r}")


def make_storage():
    if config.storage_backend == "s3":
        return storage.S3Storage(bucket=config.storage_bucket, region=config.aws_region)
    if config.storage_backend == "local":
        return storage.LocalStorage(base_dir=config.storage_local_dir)
    raise ValueError(f"Unknown STORAGE_BACKEND: {config.storage_backend!r}")


def make_userstore():
    """Create the PostgreSQL userstore. This is the only supported backend."""
    return userstore.PostgresUserStore(url=config.userstore_postgres_url)
