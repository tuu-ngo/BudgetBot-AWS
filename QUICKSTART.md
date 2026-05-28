# 🚀 BudgetBot Lambda - Quick Start Reference

## 📋 Quick Summary

```
┌─────────────────────────────────────────────────────────────┐
│               Lambda Architecture Overview                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  📱 Frontend (React)                                          │
│         │                                                     │
│         ▼                                                     │
│  🌐 API Gateway                                              │
│         │                                                     │
│    ┌────┴──────────────────┬────────────┐                   │
│    │                       │            │                    │
│    ▼                       ▼            ▼                    │
│  Lambda API           Lambda Chat   CloudFront             │
│  (All HTTP routes)    (Chat only)    (Frontend)            │
│    │                       │                                 │
│    ├─ /users/*             ├─ /chat                         │
│    ├─ /upload              └─ /chat/history                │
│    ├─ /summary                                              │
│    ├─ /transactions                                         │
│    └─ /budget-caps                                          │
│    │                                                         │
│    ├─ SQS message (async)                                   │
│    │    ↓                                                    │
│    │  Lambda Parser                                         │
│    │  (SQS trigger)  ─── AI (Bedrock) ───┐                │
│    │    │                                 │                 │
│    │    ├─ Download CSV                   │                 │
│    │    ├─ Parse CSV                      ▼                │
│    │    ├─ Categorize with AI  ─────────────────────┐     │
│    │    ├─ Save to RDS                              │      │
│    │    └─ Invoke Budget Lambda (async)             │      │
│    │         ↓                                       │      │
│    │      Lambda Budget                             │      │
│    │      (Async)                                   │      │
│    │        ├─ Check budget caps                    │      │
│    │        ├─ Calculate spending                   │      │
│    │        └─ SNS alert if over budget             │      │
│    │                                                │      │
│    └──────────────────────┬───────────────────────┴──────┘
│                           │                         │
│                           ▼                         ▼
│                    📊 RDS PostgreSQL  🎯 Bedrock AI
│                    (Transactions)     (Categorization)
│                                       (Chat)
│                                       
│                                       📧 SNS Email Alerts
│
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Lambda Functions At a Glance

| Lambda | Trigger | Timeout | Memory | Purpose |
|--------|---------|---------|--------|---------|
| **API** | HTTP (API Gateway) | 60s | 512MB | Route requests, user management, upload |
| **Parser** | SQS Message | 300s | 1024MB | Parse CSV, AI categorization, DB insert |
| **Chat** | HTTP (API Gateway) | 30s | 512MB | Chat interaction, AI responses |
| **Budget** | Async Invoke | 30s | 256MB | Check budget, SNS alerts |

---

## 💻 Local Development

### Start Local Server
```bash
# Terminal 1: Backend
export FLOW_MODE=local
uvicorn src.app:app --reload --port 8000

# Terminal 2: Frontend (if needed)
cd frontend
npm run dev
```

### Test Upload (Local)
```bash
curl -X POST \
  -F "file=@sample_data/bank_statement_q2_2026.csv" \
  -H "X-User-Id: test-user-001" \
  http://localhost:8000/upload
```

### Test Chat (Local)
```bash
curl -X POST \
  -H "X-User-Id: test-user-001" \
  -H "Content-Type: application/json" \
  -d '{"message": "How much did I spend on food?"}' \
  http://localhost:8000/chat
```

---

## 📦 Build & Deploy

### One-Command Deploy (Dev)
```bash
make deploy ENVIRONMENT=dev
```

### One-Command Deploy (Prod)
```bash
make deploy ENVIRONMENT=prod
```

### Manual Steps
```bash
# 1. Build packages
make build

# 2. Create layer
make layer

# 3. Deploy individual functions
make deploy-api
make deploy-parser
make deploy-chat
make deploy-budget

# 4. Check logs
make logs-api
make logs-parser
```

---

## 🔍 Monitoring

### View Logs
```bash
# Real-time logs
make logs-api
make logs-parser

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/budgetbot-parser-prod \
  --filter-pattern "ERROR" \
  --region ap-southeast-1
```

### Check Metrics
```bash
# Duration, errors, throttles
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=budgetbot-api-prod \
  --start-time 2024-05-28T00:00:00Z \
  --end-time 2024-05-28T23:59:59Z \
  --period 3600 \
  --statistics Average,Maximum
```

### List All Functions
```bash
make list-functions
```

---

## 🧪 Testing

### Run Tests Locally
```bash
# All tests
pytest tests/ -v

# Specific test
pytest tests/test_smoke.py::test_upload -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### Test with SAM (Simulates AWS)
```bash
# Start local API gateway
sam local start-api --port 3000

# Invoke function with test event
sam local invoke LambdaParser -e events/parser_event.json
```

---

## 🔐 Environment Variables

### Development (.env.dev)
```bash
FLOW_MODE=local
STORAGE_BACKEND=local
STORAGE_LOCAL_DIR=./_data/uploads
USERSTORE_POSTGRES_URL=postgresql://postgres:password@localhost:5432/budgetbot
AI_BACKEND=local
REVIEW_THRESHOLD=0.6
DEFAULT_USER_ID=test-user-001
```

### Production (.env.prod)
```bash
FLOW_MODE=aws
STORAGE_BACKEND=s3
STORAGE_BUCKET=budgetbot-uploads-prod
AWS_REGION=ap-southeast-1
USERSTORE_POSTGRES_URL=postgresql://admin:SECURE_PASSWORD@rds-prod-endpoint:5432/budgetbot
AI_BACKEND=bedrock
AI_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0
SQS_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/ACCOUNT_ID/budgetbot-parser-queue
SNS_TOPIC_ARN=arn:aws:sns:ap-southeast-1:ACCOUNT_ID:budgetbot-budget-alerts
REVIEW_THRESHOLD=0.75
```

---

## 🐛 Troubleshooting

### Problem: Lambda times out
```
❌ Issue: "Task timed out after 30.00 seconds"
✅ Solution: 
   - Increase timeout: make deploy TIMEOUT=60
   - Check RDS connection (might be slow)
   - Optimize cold start (reduce dependencies)
```

### Problem: SQS messages not being processed
```
❌ Issue: Messages in queue, Lambda not invoked
✅ Solution:
   - Check SQS trigger mapping: aws lambda list-event-source-mappings
   - Check Lambda permissions for SQS
   - Check dead letter queue
   - Check Lambda error logs
```

### Problem: RDS connection refused
```
❌ Issue: "psycopg2.OperationalError: could not connect to server"
✅ Solution:
   - Ensure Lambda has VPC config
   - Check security group allows 5432
   - Check RDS is in same VPC
   - Ping RDS endpoint from Lambda
```

### Problem: Bedrock access denied
```
❌ Issue: "AccessDeniedException: User is not authorized"
✅ Solution:
   - Check IAM role has bedrock:InvokeModel
   - Check region supports Bedrock
   - Check model ID is correct format
   - Check quota not exceeded
```

### Problem: S3 access denied
```
❌ Issue: "NoSuchBucket" or "AccessDenied"
✅ Solution:
   - Verify bucket name in config
   - Check IAM role has s3:GetObject, s3:PutObject
   - Check bucket policy allows cross-region access
   - Check CORS if frontend accessing directly
```

---

## 📊 API Endpoints

### Users
```bash
# Create user
POST /users
  Body: {"account": "john@example.com", "password": "...", "budget": 5000}

# Get user
GET /users/{user_id}
  Header: X-User-Id: user-123

# Update user
PUT /users/{user_id}
  Body: {"password": "...", "budget": 5000}
```

### Upload & Files
```bash
# Upload file
POST /upload
  File: multipart/form-data
  Header: X-User-Id: user-123
  Response: {"file_id": "...", "status": "processing"}

# List user's files
GET /files
  Header: X-User-Id: user-123
  Query: skip=0&limit=10

# Get file status
GET /files/{file_id}
  Response: {"status": "done|processing|error"}
```

### Transactions & Summary
```bash
# Get transactions
GET /transactions
  Query: month=2024-05&category=Food&skip=0&limit=50
  Header: X-User-Id: user-123

# Get spending summary
GET /summary
  Query: month=2024-05
  Header: X-User-Id: user-123
  Response: {
    "by_category": {"Food": 500, "Transport": 200, ...},
    "total": 700,
    "month": "2024-05"
  }
```

### Budget & Alerts
```bash
# Set budget cap
POST /budget-caps
  Body: {"category": "Food", "cap_amount": 500}
  Header: X-User-Id: user-123

# Get budget caps
GET /budget-caps
  Header: X-User-Id: user-123
  Response: {"Food": 500, "Transport": 200, ...}
```

### Chat
```bash
# Send message
POST /chat
  Body: {"message": "How much did I spend?", "month": "2024-05"}
  Header: X-User-Id: user-123
  Response: {"response": "You spent $700 in May..."}

# Get chat history
GET /chat/history?limit=50
  Header: X-User-Id: user-123
  Response: [
    {"role": "user", "message": "...", "timestamp": "..."},
    {"role": "assistant", "message": "...", "timestamp": "..."}
  ]
```

---

## 🔗 Links & Resources

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Mangum (FastAPI → Lambda)](https://mangum.io/)
- [AWS SAM](https://aws.amazon.com/serverless/sam/)

---

## 📞 Common Commands Cheat Sheet

```bash
# Build & Deploy
make build                    # Build all packages
make deploy                   # Deploy all lambdas
make deploy ENVIRONMENT=prod  # Deploy to production

# Development
make dev                      # Start local server
make test                     # Run tests
make lint                     # Lint code
make format                   # Format code with Black

# Monitoring
make logs-api                 # Tail API logs
make logs-parser              # Tail Parser logs
make metrics-api              # Show API metrics
make list-functions           # List all functions
make health                   # Check Lambda health

# Cleanup
make clean                    # Clean build artifacts

# AWS CLI Direct
aws lambda invoke \
  --function-name budgetbot-api-prod \
  --region ap-southeast-1 \
  response.json && cat response.json

aws logs tail /aws/lambda/budgetbot-api-prod --follow

aws s3 ls s3://budgetbot-uploads-prod/
```

---

## ✅ Pre-Launch Checklist

- [ ] Local tests passing (`make test`)
- [ ] Code formatted (`make format`)
- [ ] No security issues (`make security`)
- [ ] Environment variables set
- [ ] RDS migrations applied
- [ ] S3 bucket created
- [ ] SQS queue created
- [ ] SNS topic created
- [ ] IAM roles configured
- [ ] VPC security groups configured
- [ ] CloudWatch alarms set
- [ ] CloudFront cache invalidated (frontend)
- [ ] DNS updated (if new domain)
- [ ] Database backup configured
- [ ] Disaster recovery plan documented

---

## 🎓 Next Steps

1. **Immediate** (Today)
   - Review [LAMBDA_ARCHITECTURE.md](LAMBDA_ARCHITECTURE.md)
   - Review [CODE_ORGANIZATION.md](CODE_ORGANIZATION.md)
   - Test locally with `make dev`

2. **Short Term** (This week)
   - Deploy to dev environment: `make deploy ENVIRONMENT=dev`
   - Test end-to-end flow
   - Fix any issues from real testing
   - Set up monitoring

3. **Production** (Next week)
   - Final security review
   - Load testing
   - Canary deployment to prod
   - Monitor metrics and logs

---

## 📧 Support

For issues or questions:
1. Check [LAMBDA_ARCHITECTURE.md](LAMBDA_ARCHITECTURE.md) for architecture details
2. Check [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for deployment help
3. Check [CODE_ORGANIZATION.md](CODE_ORGANIZATION.md) for code patterns
4. Check CloudWatch logs: `make logs-*`
5. Search AWS documentation

