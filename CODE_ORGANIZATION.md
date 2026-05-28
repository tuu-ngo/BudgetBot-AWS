# Code Organization Best Practices for BudgetBot Lambda

## 📁 Recommended File Structure

```
budgetbot-aws/
├── src/
│   ├── __init__.py
│   ├── app.py                      # FastAPI main app
│   ├── config.py                   # Configuration
│   ├── constants.py                # Constants
│   │
│   ├── lambdas/
│   │   ├── __init__.py
│   │   ├── lambda_api.py           # API Gateway handler (Mangum wrapper)
│   │   ├── lambda_parser.py        # SQS-triggered CSV parser
│   │   ├── lambda_chat.py          # Chat handler
│   │   ├── lambda_budget.py        # Budget checker
│   │   └── base.py                 # Common Lambda utilities
│   │
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── api_handler.py          # Business logic: upload, users, summary
│   │   ├── parser_handler.py       # Business logic: CSV parsing, categorization
│   │   ├── chat_handler.py         # Business logic: chat interaction
│   │   ├── budget_handler.py       # Business logic: budget checking
│   │   └── shared.py               # Shared logic (CSV parsing utilities, etc)
│   │
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── factory.py              # Dependency injection factory
│   │   ├── ai.py                   # AI client abstraction (Bedrock)
│   │   ├── storage.py              # Storage abstraction (S3 / Local)
│   │   ├── userstore.py            # Database client (PostgreSQL)
│   │   ├── sqs_client.py           # SQS client wrapper
│   │   └── sns_client.py           # SNS client wrapper
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── transaction.py          # Transaction model
│   │   ├── user.py                 # User model
│   │   ├── file.py                 # File model
│   │   └── schemas.py              # Pydantic schemas
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── csv_utils.py            # CSV parsing utilities
│   │   ├── logger.py               # Custom logger
│   │   ├── exceptions.py           # Custom exceptions
│   │   └── validators.py           # Input validation
│   │
│   └── errors/
│       ├── __init__.py
│       ├── handlers.py             # Error handlers
│       └── exceptions.py           # Custom exception classes
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   ├── test_smoke.py
│   ├── unit/
│   │   ├── test_csv_parser.py
│   │   ├── test_handlers.py
│   │   └── test_adapters.py
│   ├── integration/
│   │   ├── test_sqs_flow.py
│   │   └── test_db_flow.py
│   └── events/
│       ├── sqs_event.json
│       ├── api_event.json
│       └── budget_event.json
│
├── events/
│   ├── parser_event.json           # Sample SQS event
│   ├── budget_event.json           # Sample async event
│   └── api_event.json              # Sample API Gateway event
│
├── sql/
│   ├── init_db.sql                 # Database initialization
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   └── 002_add_columns.sql
│   └── queries/
│       ├── transactions.sql
│       └── budget_caps.sql
│
├── sample_data/
│   └── *.csv                       # Sample bank statements
│
├── frontend/
│   └── ...                         # React/Vue frontend
│
├── docker-compose.yml
├── Dockerfile.lambda              # Multi-stage build for Lambda
├── requirements.txt
├── requirements-dev.txt           # Dev dependencies
├── template.yaml                  # SAM template
├── Makefile                       # Deployment commands
├── LAMBDA_ARCHITECTURE.md         # Architecture documentation
├── DEPLOYMENT_GUIDE.md            # Deployment guide
├── .env.example                   # Example environment variables
├── .github/workflows/
│   └── deploy.yml                # GitHub Actions CI/CD
└── README.md
```

---

## 🔧 Code Organization Principles

### 1. **Separation of Concerns**

```python
# ❌ BAD: Everything mixed in one file
def lambda_handler(event, context):
    # Parse SQS
    # Download file
    # Parse CSV
    # Categorize
    # Save to DB
    # Invoke budget
    # Return response
    pass

# ✅ GOOD: Clear separation

# src/lambdas/lambda_parser.py - Entry point
from src.handlers.parser_handler import process_sqs_event

def handler(event, context):
    return process_sqs_event(event, context, ...)

# src/handlers/parser_handler.py - Business logic
def process_sqs_event(event, context, storage, ai_client, userstore):
    for record in event.get("Records", []):
        message = json.loads(record["body"])
        process_single_file(message, storage, ai_client, userstore)

# src/handlers/shared.py - Utilities
def process_single_file(message, storage, ai_client, userstore):
    # Download and parse
    csv_data = storage.download(message["s3_key"])
    rows = parse_csv(csv_data)
    
    # Categorize each row
    for row in rows:
        categorize_and_save(row, ai_client, userstore)
```

### 2. **Dependency Injection**

```python
# ❌ BAD: Global state, hard to test
import boto3
s3 = boto3.client("s3")

def upload_file(key, data):
    s3.put_object(Bucket="my-bucket", Key=key, Body=data)

# ✅ GOOD: Inject dependencies
class S3Storage:
    def __init__(self, s3_client, bucket):
        self.client = s3_client
        self.bucket = bucket
    
    def upload(self, key, data):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

# In handler
storage = S3Storage(boto3.client("s3"), "my-bucket")
upload_file(storage, key, data)

# Factory pattern
from src.adapters.factory import make_storage

storage = make_storage()  # Returns S3 or Local based on config
```

### 3. **Error Handling**

```python
# ❌ BAD: Silent failures
def categorize_transaction(description, amount):
    try:
        result = bedrock.invoke_model(...)
        return result
    except:
        return None  # Silently fails!

# ✅ GOOD: Explicit handling
class CategorizationError(Exception):
    pass

def categorize_transaction(description, amount):
    try:
        result = bedrock.invoke_model(...)
        if not result:
            raise CategorizationError("Empty response from Bedrock")
        return result
    except Exception as e:
        logger.error(f"Categorization failed: {str(e)}", 
                    extra={"description": description, "amount": amount})
        raise
```

### 4. **Configuration Management**

```python
# ❌ BAD: Hardcoded values
def handler(event, context):
    db_url = "postgresql://user:pass@localhost:5432/db"
    ai_model = "claude-3-haiku"
    threshold = 0.6

# ✅ GOOD: Environment-based config
from src.config import config

def handler(event, context):
    db_url = config.userstore_postgres_url
    ai_model = config.ai_model_id
    threshold = config.review_threshold
```

### 5. **Logging & Monitoring**

```python
# ❌ BAD: Insufficient logging
def parse_file(file_path):
    rows = open(file_path).readlines()
    return rows

# ✅ GOOD: Rich context
from src.utils.logger import get_logger

logger = get_logger(__name__)

def parse_file(file_id, file_path, user_id):
    logger.info("Parsing file", extra={
        "file_id": file_id,
        "file_path": file_path,
        "user_id": user_id
    })
    
    try:
        with open(file_path) as f:
            rows = f.readlines()
        
        logger.info("File parsed successfully", extra={
            "file_id": file_id,
            "row_count": len(rows)
        })
        return rows
    
    except FileNotFoundError as e:
        logger.error("File not found", extra={
            "file_id": file_id,
            "error": str(e)
        }, exc_info=True)
        raise
```

---

## 📊 Handler Organization Pattern

### Parser Handler Example

```python
# src/handlers/parser_handler.py

import json
import logging
from typing import Dict, List

from src.config import config
from src.utils.exceptions import ParseError, CategorizationError
from src.handlers.shared import parse_csv, categorize_and_save

logger = logging.getLogger(__name__)

def process_sqs_event(event: dict, context, storage, ai_client, userstore) -> dict:
    """
    Process SQS events containing CSV file metadata.
    
    Args:
        event: AWS Lambda SQS event
        context: AWS Lambda context
        storage: Storage adapter (S3/Local)
        ai_client: AI client (Bedrock)
        userstore: Database adapter
    
    Returns:
        Dict with processing results
    
    Flow:
        1. Parse SQS message
        2. Download file from S3
        3. Parse CSV
        4. Categorize each row
        5. Save to database
        6. Invoke Budget Lambda
    """
    results = []
    
    for record in event.get("Records", []):
        try:
            result = process_single_record(
                record, 
                storage, 
                ai_client, 
                userstore
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to process record", exc_info=True)
            results.append({
                "status": "error",
                "error": str(e)
            })
    
    return {
        "statusCode": 200,
        "results": results,
        "processedCount": sum(1 for r in results if r["status"] == "success")
    }


def process_single_record(record: dict, storage, ai_client, userstore) -> Dict:
    """Process one SQS record."""
    
    # Parse message
    try:
        message = json.loads(record["body"])
        user_id = message["user_id"]
        file_id = message["file_id"]
        s3_key = message["s3_key"]
    except (KeyError, json.JSONDecodeError) as e:
        raise ParseError(f"Invalid SQS message: {str(e)}")
    
    logger.info("Processing file", extra={
        "user_id": user_id,
        "file_id": file_id,
        "s3_key": s3_key
    })
    
    # Download file
    try:
        csv_data = storage.download(s3_key)
        logger.info("File downloaded", extra={
            "file_id": file_id,
            "size": len(csv_data)
        })
    except Exception as e:
        logger.error(f"Failed to download file: {str(e)}", exc_info=True)
        userstore.update_file_status(file_id, "error", str(e))
        raise
    
    # Parse CSV
    try:
        rows = parse_csv(csv_data)
        logger.info("CSV parsed", extra={
            "file_id": file_id,
            "row_count": len(rows)
        })
    except Exception as e:
        logger.error(f"Failed to parse CSV: {str(e)}", exc_info=True)
        userstore.update_file_status(file_id, "error", str(e))
        raise
    
    # Process rows
    inserted = 0
    review_count = 0
    errors = []
    
    for idx, row in enumerate(rows):
        try:
            categorize_and_save(
                row,
                file_id,
                user_id,
                ai_client,
                userstore
            )
            inserted += 1
        except CategorizationError as e:
            logger.warning(f"Categorization failed for row {idx}: {str(e)}")
            errors.append({"row": idx, "error": str(e)})
            review_count += 1
        except Exception as e:
            logger.error(f"Error processing row {idx}: {str(e)}", exc_info=True)
            errors.append({"row": idx, "error": str(e)})
    
    # Update file status
    userstore.update_file_status(file_id, "done")
    
    # Invoke Budget Lambda
    try:
        from src.adapters.factory import make_lambda_client
        lambda_client = make_lambda_client()
        lambda_client.invoke(
            FunctionName=config.budget_lambda_name,
            InvocationType="Event",
            Payload=json.dumps({
                "user_id": user_id,
                "file_id": file_id
            })
        )
        logger.info("Budget Lambda invoked", extra={"file_id": file_id})
    except Exception as e:
        logger.error(f"Failed to invoke Budget Lambda: {str(e)}", exc_info=True)
    
    return {
        "status": "success",
        "file_id": file_id,
        "user_id": user_id,
        "inserted": inserted,
        "review_count": review_count,
        "errors": errors
    }
```

---

## 🧪 Testing Structure

### Unit Tests

```python
# tests/unit/test_handlers.py

import pytest
from unittest.mock import Mock, patch
from src.handlers.parser_handler import process_single_record

@pytest.fixture
def mock_adapters():
    return {
        "storage": Mock(),
        "ai_client": Mock(),
        "userstore": Mock()
    }

def test_process_single_record_success(mock_adapters):
    """Test successful file processing."""
    
    # Arrange
    record = {
        "body": json.dumps({
            "user_id": "user-123",
            "file_id": "file-456",
            "s3_key": "uploads/user-123/statement.csv"
        })
    }
    
    mock_adapters["storage"].download.return_value = b"date,amount\n2024-01-01,100"
    mock_adapters["ai_client"].categorize.return_value = {
        "category": "Food",
        "confidence": 0.95
    }
    mock_adapters["userstore"].add_transaction.return_value = {
        "status": "ok"
    }
    
    # Act
    result = process_single_record(record, **mock_adapters)
    
    # Assert
    assert result["status"] == "success"
    assert result["inserted"] > 0
    mock_adapters["userstore"].update_file_status.assert_called()

def test_process_single_record_invalid_message(mock_adapters):
    """Test handling of invalid SQS message."""
    
    record = {"body": "invalid json"}
    
    with pytest.raises(ParseError):
        process_single_record(record, **mock_adapters)
```

### Integration Tests

```python
# tests/integration/test_sqs_flow.py

@pytest.mark.integration
def test_csv_upload_to_db_flow(db_connection, s3_client, lambda_client):
    """Test complete flow: upload → parse → categorize → save."""
    
    # 1. Upload file to S3
    s3_client.put_object(
        Bucket="test-bucket",
        Key="uploads/user-123/test.csv",
        Body=b"date,description,amount\n2024-01-01,Test Expense,100"
    )
    
    # 2. Invoke Lambda Parser
    response = lambda_client.invoke(
        FunctionName="budgetbot-parser-test",
        Payload=json.dumps({
            "Records": [{
                "body": json.dumps({
                    "user_id": "user-123",
                    "file_id": "file-456",
                    "s3_key": "uploads/user-123/test.csv"
                })
            }]
        })
    )
    
    # 3. Verify database was updated
    with db_connection.cursor() as cursor:
        cursor.execute("SELECT * FROM transactions WHERE file_id = %s", ("file-456",))
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0]["amount"] == 100
```

---

## 🚀 Deployment Best Practices

### 1. **Environment-Specific Configuration**

```bash
# .env.dev
FLOW_MODE=aws
ENVIRONMENT=dev
AI_BACKEND=bedrock
STORAGE_BACKEND=s3
REVIEW_THRESHOLD=0.6

# .env.prod
FLOW_MODE=aws
ENVIRONMENT=prod
AI_BACKEND=bedrock
STORAGE_BACKEND=s3
REVIEW_THRESHOLD=0.75
```

### 2. **Build Optimization**

```dockerfile
# Dockerfile.lambda

FROM public.ecr.aws/lambda/python:3.12

# Copy source code
COPY src/ ${LAMBDA_TASK_ROOT}/src/

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Set handler
CMD [ "src.lambdas.lambda_api.handler" ]
```

### 3. **Version Control**

```bash
# Tag releases
git tag -a v1.0.0 -m "Production release"
git push origin v1.0.0

# Deployment from tag
make deploy VERSION=1.0.0
```

---

## 📝 Checklist for Code Quality

- [ ] All handlers use dependency injection
- [ ] All handlers have comprehensive logging
- [ ] All handlers have error handling
- [ ] Configuration is environment-driven
- [ ] Unit tests cover happy paths
- [ ] Integration tests cover end-to-end flows
- [ ] No hardcoded values or secrets
- [ ] Type hints on all functions
- [ ] Docstrings on all public functions
- [ ] Code formatted with Black
- [ ] Linted with Pylint/Flake8
- [ ] Security checked with Bandit

