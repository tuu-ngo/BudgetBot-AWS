# BudgetBot — AI Money Coach

**Domain:** FinTech. Upload a bank statement CSV → AI categorizes each transaction → spending summary by category + AI chat coach.

---

## Architecture overview



**AI adapters** — swap via env var, no code change:


| `AI_BACKEND` | Description                                                |
| ------------ | ---------------------------------------------------------- |
| `local`      | Keyword-based rule matching, no AWS call. Default for dev. |
| `bedrock`    | AWS Bedrock `Converse` API with Claude 3.5 Haiku.          |


**Storage adapters:**


| `STORAGE_BACKEND` | Description                                         |
| ----------------- | --------------------------------------------------- |
| `local`           | Saves files to local filesystem (`_data/uploads/`). |
| `s3`              | Saves to S3 bucket. Required in `aws` flow mode.    |


**Database:** PostgreSQL only (local Docker or RDS in AWS).

---

## Run locally

### 1. Start PostgreSQL

```bash
docker volume create c258ad4d2fa2438d3119648e6d0428693d835a2e6ade584507b6187dd92cfb98
docker compose up -d
```

Apply the schema:

```bash
psql postgresql://postgres:postgres@localhost:5432/budgetbot -f sql/init_db.sql
```

### 2. Install dependencies and start the server

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
uvicorn src.app:app --reload --port 8000
```

### 3. Verify

```bash
# Health check
curl http://localhost:8000/health

# Open the web UI
open http://localhost:8000        # macOS
start http://localhost:8000       # Windows
```

### 4. End-to-end smoke test

Open the web UI, sign up or log in through Cognito, then upload a CSV.
User-scoped APIs require the Cognito session cookie set by `/auth/callback`.

Run automated tests:

```bash
pytest -v
```

---

## Code structure

```
src/
├── app.py                   FastAPI app + all routes (thin router layer)
├── auth.py                  Cognito Hosted UI + JWT cookie verification
├── config.py                Env-driven settings
├── adapters/
│   ├── ai.py                BedrockAI (Converse API) | LocalAI (rule-based)
│   ├── storage.py           S3Storage | LocalStorage (filesystem)
│   ├── userstore.py         PostgresUserStore — all 5 tables
│   └── factory.py           Picks adapter based on env vars
├── handlers/
│   ├── api_handler.py       Upload, summary, transactions, budget caps
│   ├── chat_handler.py      AI chat + chat history
│   ├── budget_handler.py    Budget cap checks for frontend warnings
│   └── parser_handler.py    SQS event → CSV parse → DB write
└── lambdas/
    ├── lambda_api.py        Lambda 1 — API Gateway (Mangum wrapper)
    ├── lambda_parser.py     Lambda 2 — SQS-triggered CSV parser
    ├── lambda_chat.py       Lambda 3 — Chat routes (Mangum wrapper)
    └── lambda_budget.py     Lambda 4 — Budget cap checker

frontend/
└── index.html               Single-page UI (served by FastAPI or CloudFront+S3)

sql/
└── init_db.sql              PostgreSQL schema (idempotent, safe to re-run)

sample_data/
├── bank_statement_q2_2026.csv   Full Q2 2026 sample (VND)
├── smoke_test_5_rows.csv        Minimal 5-row test fixture
└── postgres_test_statement.csv  Integration test fixture
```

### Database schema (5 tables)


| Table          | Purpose                                                                        |
| -------------- | ------------------------------------------------------------------------------ |
| `user`         | Account, password, budget total                                                |
| `file`         | Uploaded statement files with `status` (`pending → processing → done / error`) |
| `transaction`  | Parsed rows: date, description, amount, category, confidence, review_status    |
| `chat_history` | Chat turns (input + output) per user                                           |
| `budget_cap`   | Per-user, per-category spending caps                                           |


### Transaction categories

`Food` · `Transport` · `Shopping` · `Utilities` · `Entertainment` · `Health` · `Subscriptions` · `Bills` · `Income` · `Transfer` · `Other`

Transactions with AI confidence below `REVIEW_THRESHOLD` (default `0.60`) are flagged as `review_status='review'` and surfaced via `GET /transactions/review`.

---

## API reference


| Method | Route                         | Description                                                  |
| ------ | ----------------------------- | ------------------------------------------------------------ |
| GET    | `/health`                     | Backend status + active adapters                             |
| GET    | `/auth/login`                 | Redirect to Cognito Hosted UI login                          |
| GET    | `/auth/signup`                | Redirect to Cognito Hosted UI signup                         |
| GET    | `/auth/callback`              | Exchange Cognito code and set HttpOnly session cookie        |
| GET    | `/auth/me`                    | Current authenticated user                                   |
| GET    | `/auth/logout`                | Clear session and redirect through Cognito logout            |
| GET    | `/users/me`                   | Current local user mapped from Cognito                       |
| POST   | `/upload`                     | Upload CSV bank statement                                    |
| GET    | `/upload/{file_id}/status`    | Poll async processing status                                 |
| GET    | `/files`                      | List uploaded files for user                                 |
| GET    | `/summary`                    | Spending summary by category (optional `?month=YYYY-MM`)     |
| GET    | `/transactions`               | List transactions (optional `?month=` and `?review_status=`) |
| GET    | `/transactions/review`        | Low-confidence transactions needing human review             |
| PATCH  | `/transactions/{id}/category` | Manually correct a category                                  |
| GET    | `/budget-caps`                | Get all budget caps for user                                 |
| PUT    | `/budget-caps/{category}`     | Set a budget cap                                             |
| DELETE | `/budget-caps/{category}`     | Remove a budget cap                                          |
| POST   | `/budget/check`               | Return budget cap warnings for frontend display              |
| POST   | `/chat`                       | Send message to AI coach (optional `?month=` context)        |
| GET    | `/chat/history`               | Get chat history                                             |


All user-scoped routes require the Cognito session cookie. The backend resolves
`user_id` from verified Cognito JWT claims; the frontend does not send
`X-User-Id` and does not store tokens in localStorage.

---

## Environment variables

```bash
# AI backend
AI_BACKEND=local                   # local | bedrock
AI_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0
AWS_REGION=ap-southeast-1

# Storage backend
STORAGE_BACKEND=local              # local | s3
STORAGE_BUCKET=                    # required when STORAGE_BACKEND=s3
STORAGE_LOCAL_DIR=./_data/uploads

# Database
USERSTORE_POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/budgetbot

# Flow mode
FLOW_MODE=local                    # local (sync) | aws (S3 + SQS async)
SQS_QUEUE_URL=                     # required when FLOW_MODE=aws

# Cognito Hosted UI auth
COGNITO_REGION=ap-southeast-1
COGNITO_USER_POOL_ID=
COGNITO_CLIENT_ID=
COGNITO_CLIENT_SECRET=
COGNITO_DOMAIN=
COGNITO_REDIRECT_URI=http://localhost:8000/auth/callback
COGNITO_LOGOUT_URI=http://localhost:5173/login
AUTH_SUCCESS_REDIRECT_URI=http://localhost:5173/upload
AUTH_COOKIE_NAME=budgetbot_session
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax

# Lambda names
PARSER_LAMBDA_NAME=budgetbot-parser

# Thresholds / misc
REVIEW_THRESHOLD=0.60              # confidence below this → review queue
LOG_LEVEL=INFO
SERVE_FRONTEND=true                # false = deploy frontend separately
CORS_ORIGINS=http://localhost:5173
```

### Cognito setup

Create a Cognito User Pool manually in AWS:

1. Create a User Pool with email sign-up/sign-in.
2. Create an App Client for Hosted UI with Authorization Code grant enabled.
3. Add scopes: `openid`, `email`, `profile`.
4. Configure callback URLs:
   - Local: `http://localhost:8000/auth/callback`
   - AWS: your deployed backend callback URL.
5. Configure sign-out URLs:
   - Local: `http://localhost:5173/login`
   - AWS: your deployed frontend login URL.
6. Create a Hosted UI domain and set `COGNITO_DOMAIN` to the full `https://...amazoncognito.com` URL.

For AWS HTTPS deployments set:

```bash
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=none
CORS_ORIGINS=https://your-frontend-domain.example
```

---

## Deploy to AWS

### Flip env vars

```diff
- AI_BACKEND=local
+ AI_BACKEND=bedrock
+ AI_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0

- STORAGE_BACKEND=local
+ STORAGE_BACKEND=s3
+ STORAGE_BUCKET=budgetbot-statements-<account-id>

- FLOW_MODE=local
+ FLOW_MODE=aws
+ SQS_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/<account-id>/budgetbot-parse-queue

+ USERSTORE_POSTGRES_URL=postgresql://user:pw@<rds-endpoint>:5432/budgetbot
```

### Lambda handlers


| Lambda            | Handler path                        | Trigger                                 |
| ----------------- | ----------------------------------- | --------------------------------------- |
| Lambda 1 — API    | `src/lambdas/lambda_api.handler`    | API Gateway (all routes except `/chat`) |
| Lambda 2 — Parser | `src/lambdas/lambda_parser.handler` | SQS (`budgetbot-parse-queue`)           |
| Lambda 3 — Chat   | `src/lambdas/lambda_chat.handler`   | API Gateway (`/chat/*`)                 |
| Lambda 4 — Budget | `src/lambdas/lambda_budget.handler` | Optional direct budget-check invocation |


All Lambdas share the same `requirements.txt`. `mangum` is already included.

### Cost notes (Singapore — ap-southeast-1)

- **RDS PostgreSQL** db.t3.micro ≈ $1.25/48 h. Use Single-AZ for hackathon, skip Multi-AZ.
- **RDS Proxy** — recommended with Lambda + Postgres to avoid connection exhaustion (each Lambda container opens its own `psycopg2` connection otherwise).
- Bedrock Haiku is priced per token; low for single-transaction classification calls.

### Frontend deployment options


| Option            | Config                                                                                                                        |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Served by FastAPI | `SERVE_FRONTEND=true` (default). Backend serves `frontend/index.html` at `/`.                                                 |
| CloudFront + S3   | Upload `frontend/index.html` to S3 + CloudFront. Set `SERVE_FRONTEND=false` and set `CORS_ORIGINS` to your CloudFront domain. |


---

## Sample CSV format

```csv
date,description,amount
2026-05-02,Highlands Coffee - Bui Vien,-65000
2026-05-04,Salary deposit credit,18500000
2026-05-07,Netflix monthly subscription,-180000
```

Header row is optional. **Negative amounts = expenses; positive = income.** Currency is assumed VND locally; the Bedrock model infers meaning from descriptions so currency does not need to be specified.