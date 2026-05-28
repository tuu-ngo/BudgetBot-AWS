# AWS Lambda Deployment Guide - Practical Implementation

## 📦 Step 1: Chuẩn Bị Dependencies

### Tạo Layer cho Shared Dependencies

```bash
# Create layer directory structure
mkdir -p lambda-layer/python
cd lambda-layer

# Install dependencies
pip install -r ../requirements.txt -t python/

# Remove unnecessary files
find python -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find python -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find python -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# Remove test files
find python -type f -name "test*.py" -delete
find python -type f -name "*test*.py" -delete

# Zip layer
zip -r lambda_layer.zip python/

# Upload to AWS
aws lambda publish-layer-version \
  --layer-name budgetbot-dependencies \
  --zip-file fileb://lambda_layer.zip \
  --compatible-runtimes python3.12 \
  --region ap-southeast-1
```

### Tối Ưu File Size (Optional)

```bash
# Chỉ keep essentials
# Remove: tests, docs, examples
# Compile .py → .pyc để tiết kiệm space

python -m compileall python/ -b
find python -name "*.py" -delete
find python -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true
```

---

## 🏗️ Step 2: Build Lambda Packages

Tạo `build.sh` script:

```bash
#!/bin/bash
set -e

REGION="ap-southeast-1"
ACCOUNT_ID="YOUR_ACCOUNT_ID"
LAYER_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:layer:budgetbot-dependencies"

echo "🔨 Building Lambda packages..."

# Clean
rm -rf build/ *.zip

# Build Lambda API
echo "📦 Packaging Lambda API..."
mkdir -p build/lambda_api
cp -r src/ build/lambda_api/
cd build/lambda_api
zip -r ../lambda_api.zip . -x "*.pyc" "*.pyo" "*/__pycache__/*" "*/tests/*"
cd ../..

# Build Lambda Parser
echo "📦 Packaging Lambda Parser..."
mkdir -p build/lambda_parser
cp -r src/ build/lambda_parser/
cd build/lambda_parser
zip -r ../lambda_parser.zip . -x "*.pyc" "*.pyo" "*/__pycache__/*" "*/tests/*"
cd ../..

# Build Lambda Chat
echo "📦 Packaging Lambda Chat..."
mkdir -p build/lambda_chat
cp -r src/ build/lambda_chat/
cd build/lambda_chat
zip -r ../lambda_chat.zip . -x "*.pyc" "*.pyo" "*/__pycache__/*" "*/tests/*"
cd ../..

# Build Lambda Budget
echo "📦 Packaging Lambda Budget..."
mkdir -p build/lambda_budget
cp -r src/ build/lambda_budget/
cd build/lambda_budget
zip -r ../lambda_budget.zip . -x "*.pyc" "*.pyo" "*/__pycache__/*" "*/tests/*"
cd ../..

echo "✅ Build complete!"
echo "Packages:"
ls -lh *.zip
```

---

## 🚀 Step 3: Deploy Individual Lambdas

### 3.1 Lambda API (API Gateway trigger)

```bash
#!/bin/bash
FUNCTION_NAME="budgetbot-api"
REGION="ap-southeast-1"
ROLE_ARN="arn:aws:iam::ACCOUNT:role/lambda-api-role"
LAYER_ARN="arn:aws:lambda:${REGION}:ACCOUNT:layer:budgetbot-dependencies"

# Create/Update function
aws lambda update-function-code \
  --function-name ${FUNCTION_NAME} \
  --zip-file fileb://build/lambda_api.zip \
  --region ${REGION} || \
aws lambda create-function \
  --function-name ${FUNCTION_NAME} \
  --runtime python3.12 \
  --role ${ROLE_ARN} \
  --handler src.lambdas.lambda_api.handler \
  --zip-file fileb://build/lambda_api.zip \
  --timeout 60 \
  --memory-size 512 \
  --layers ${LAYER_ARN} \
  --region ${REGION} \
  --environment "Variables={
    FLOW_MODE=aws,
    STORAGE_BACKEND=s3,
    STORAGE_BUCKET=budgetbot-uploads,
    AWS_REGION=${REGION},
    SQS_QUEUE_URL=https://sqs.${REGION}.amazonaws.com/ACCOUNT/budgetbot-parser-queue,
    USERSTORE_POSTGRES_URL=postgresql://user:pass@rds-endpoint:5432/budgetbot,
    REVIEW_THRESHOLD=0.6,
    DEFAULT_USER_ID=00000000-0000-0000-0000-000000000001
  }"

echo "✅ Lambda API deployed"
```

### 3.2 Lambda Parser (SQS trigger)

```bash
#!/bin/bash
FUNCTION_NAME="budgetbot-parser"
REGION="ap-southeast-1"
ROLE_ARN="arn:aws:iam::ACCOUNT:role/lambda-parser-role"
LAYER_ARN="arn:aws:lambda:${REGION}:ACCOUNT:layer:budgetbot-dependencies"

# Need VPC config để access RDS
SUBNET_IDS="subnet-xxx,subnet-yyy"
SECURITY_GROUP_IDS="sg-xxx"

aws lambda update-function-code \
  --function-name ${FUNCTION_NAME} \
  --zip-file fileb://build/lambda_parser.zip \
  --region ${REGION} || \
aws lambda create-function \
  --function-name ${FUNCTION_NAME} \
  --runtime python3.12 \
  --role ${ROLE_ARN} \
  --handler src.lambdas.lambda_parser.handler \
  --zip-file fileb://build/lambda_parser.zip \
  --timeout 300 \
  --memory-size 1024 \
  --layers ${LAYER_ARN} \
  --region ${REGION} \
  --vpc-config SubnetIds=${SUBNET_IDS},SecurityGroupIds=${SECURITY_GROUP_IDS} \
  --environment "Variables={
    FLOW_MODE=aws,
    STORAGE_BACKEND=s3,
    STORAGE_BUCKET=budgetbot-uploads,
    AWS_REGION=${REGION},
    AI_BACKEND=bedrock,
    AI_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0,
    USERSTORE_POSTGRES_URL=postgresql://user:pass@rds-endpoint:5432/budgetbot,
    REVIEW_THRESHOLD=0.6,
    BUDGET_LAMBDA_NAME=budgetbot-budget
  }"

echo "✅ Lambda Parser deployed"
```

### 3.3 Lambda Chat

```bash
#!/bin/bash
FUNCTION_NAME="budgetbot-chat"
REGION="ap-southeast-1"
ROLE_ARN="arn:aws:iam::ACCOUNT:role/lambda-chat-role"
LAYER_ARN="arn:aws:lambda:${REGION}:ACCOUNT:layer:budgetbot-dependencies"

aws lambda update-function-code \
  --function-name ${FUNCTION_NAME} \
  --zip-file fileb://build/lambda_chat.zip \
  --region ${REGION} || \
aws lambda create-function \
  --function-name ${FUNCTION_NAME} \
  --runtime python3.12 \
  --role ${ROLE_ARN} \
  --handler src.lambdas.lambda_chat.handler \
  --zip-file fileb://build/lambda_chat.zip \
  --timeout 30 \
  --memory-size 512 \
  --layers ${LAYER_ARN} \
  --region ${REGION} \
  --environment "Variables={
    AI_BACKEND=bedrock,
    AI_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0,
    USERSTORE_POSTGRES_URL=postgresql://user:pass@rds-endpoint:5432/budgetbot
  }"

echo "✅ Lambda Chat deployed"
```

### 3.4 Lambda Budget

```bash
#!/bin/bash
FUNCTION_NAME="budgetbot-budget"
REGION="ap-southeast-1"
ROLE_ARN="arn:aws:iam::ACCOUNT:role/lambda-budget-role"
LAYER_ARN="arn:aws:lambda:${REGION}:ACCOUNT:layer:budgetbot-dependencies"

aws lambda update-function-code \
  --function-name ${FUNCTION_NAME} \
  --zip-file fileb://build/lambda_budget.zip \
  --region ${REGION} || \
aws lambda create-function \
  --function-name ${FUNCTION_NAME} \
  --runtime python3.12 \
  --role ${ROLE_ARN} \
  --handler src.lambdas.lambda_budget.handler \
  --zip-file fileb://build/lambda_budget.zip \
  --timeout 30 \
  --memory-size 256 \
  --layers ${LAYER_ARN} \
  --region ${REGION} \
  --environment "Variables={
    USERSTORE_POSTGRES_URL=postgresql://user:pass@rds-endpoint:5432/budgetbot,
    SNS_TOPIC_ARN=arn:aws:sns:${REGION}:ACCOUNT:budgetbot-budget-alerts
  }"

echo "✅ Lambda Budget deployed"
```

---

## ⚙️ Step 4: Setup Infrastructure (Infrastructure as Code)

### SAM Template (Recommended)

Tạo `template.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2013-05-15

Description: BudgetBot Lambda Architecture

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]
  
  DBEndpoint:
    Type: String
    Description: RDS PostgreSQL endpoint
  
  DBPassword:
    Type: String
    NoEcho: true
    Description: RDS master password

Globals:
  Function:
    Timeout: 30
    MemorySize: 512
    Runtime: python3.12
    Architectures:
      - x86_64
    Layers:
      - !Ref DependenciesLayer
    Environment:
      Variables:
        AWS_REGION: !Ref AWS::Region

Resources:
  # ============================================================
  # Lambda Layer
  # ============================================================
  DependenciesLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      LayerName: !Sub 'budgetbot-dependencies-${Environment}'
      Description: Shared dependencies for BudgetBot Lambdas
      ContentUri: lambda-layer/
      CompatibleRuntimes:
        - python3.12
      RetentionPolicy: Delete

  # ============================================================
  # IAM Roles
  # ============================================================
  LambdaExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub 'budgetbot-lambda-role-${Environment}'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole
      Policies:
        - PolicyName: S3Access
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - s3:GetObject
                  - s3:PutObject
                  - s3:DeleteObject
                Resource: !Sub 'arn:aws:s3:::budgetbot-uploads-${Environment}/*'
              - Effect: Allow
                Action:
                  - s3:ListBucket
                Resource: !Sub 'arn:aws:s3:::budgetbot-uploads-${Environment}'
        - PolicyName: SQSAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - sqs:SendMessage
                  - sqs:ReceiveMessage
                  - sqs:DeleteMessage
                  - sqs:GetQueueAttributes
                Resource: !GetAtt ParserQueue.Arn
        - PolicyName: BedrockAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - bedrock:InvokeModel
                Resource: arn:aws:bedrock:*::foundation-model/*
        - PolicyName: SNSPublish
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - sns:Publish
                Resource: !Ref BudgetAlertTopic
        - PolicyName: LambdaInvoke
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - lambda:InvokeFunction
                Resource:
                  - !GetAtt LambdaBudget.Arn

  # ============================================================
  # SQS Queue
  # ============================================================
  ParserQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub 'budgetbot-parser-queue-${Environment}'
      VisibilityTimeout: 300
      MessageRetentionPeriod: 1209600  # 14 days
      ReceiveMessageWaitTimeSeconds: 10

  # ============================================================
  # SNS Topic
  # ============================================================
  BudgetAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub 'budgetbot-budget-alerts-${Environment}'
      DisplayName: BudgetBot Budget Alerts

  # ============================================================
  # Lambda Functions
  # ============================================================
  LambdaAPI:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub 'budgetbot-api-${Environment}'
      CodeUri: src/
      Handler: lambdas.lambda_api.handler
      Timeout: 60
      MemorySize: 512
      Environment:
        Variables:
          FLOW_MODE: aws
          STORAGE_BACKEND: s3
          STORAGE_BUCKET: !Sub 'budgetbot-uploads-${Environment}'
          SQS_QUEUE_URL: !Ref ParserQueue
          USERSTORE_POSTGRES_URL: !Sub 'postgresql://budgetbot:${DBPassword}@${DBEndpoint}:5432/budgetbot'
          REVIEW_THRESHOLD: '0.6'
      Events:
        ApiEvent:
          Type: Api
          Properties:
            RestApiId: !Ref BudgetBotApi
            Path: /{proxy+}
            Method: ANY
        RootApiEvent:
          Type: Api
          Properties:
            RestApiId: !Ref BudgetBotApi
            Path: /
            Method: ANY

  LambdaParser:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub 'budgetbot-parser-${Environment}'
      CodeUri: src/
      Handler: lambdas.lambda_parser.handler
      Timeout: 300
      MemorySize: 1024
      VpcConfig:
        SecurityGroupIds:
          - !Ref LambdaSecurityGroup
        SubnetIds:
          - !Ref PrivateSubnet1
          - !Ref PrivateSubnet2
      Environment:
        Variables:
          FLOW_MODE: aws
          STORAGE_BACKEND: s3
          STORAGE_BUCKET: !Sub 'budgetbot-uploads-${Environment}'
          AI_BACKEND: bedrock
          AI_MODEL_ID: anthropic.claude-3-5-haiku-20241022-v1:0
          USERSTORE_POSTGRES_URL: !Sub 'postgresql://budgetbot:${DBPassword}@${DBEndpoint}:5432/budgetbot'
          REVIEW_THRESHOLD: '0.6'
          BUDGET_LAMBDA_NAME: !Ref LambdaBudget
      Events:
        SQSEvent:
          Type: SQS
          Properties:
            Queue: !GetAtt ParserQueue.Arn
            BatchSize: 1

  LambdaChat:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub 'budgetbot-chat-${Environment}'
      CodeUri: src/
      Handler: lambdas.lambda_chat.handler
      Timeout: 30
      MemorySize: 512
      Environment:
        Variables:
          AI_BACKEND: bedrock
          AI_MODEL_ID: anthropic.claude-3-5-haiku-20241022-v1:0
          USERSTORE_POSTGRES_URL: !Sub 'postgresql://budgetbot:${DBPassword}@${DBEndpoint}:5432/budgetbot'
      Events:
        ChatApiEvent:
          Type: Api
          Properties:
            RestApiId: !Ref BudgetBotApi
            Path: /chat/{proxy+}
            Method: ANY

  LambdaBudget:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub 'budgetbot-budget-${Environment}'
      CodeUri: src/
      Handler: lambdas.lambda_budget.handler
      Timeout: 30
      MemorySize: 256
      Environment:
        Variables:
          USERSTORE_POSTGRES_URL: !Sub 'postgresql://budgetbot:${DBPassword}@${DBEndpoint}:5432/budgetbot'
          SNS_TOPIC_ARN: !Ref BudgetAlertTopic

  # ============================================================
  # API Gateway
  # ============================================================
  BudgetBotApi:
    Type: AWS::Serverless::Api
    Properties:
      Name: !Sub 'BudgetBot-${Environment}'
      StageName: !Ref Environment
      TracingEnabled: true
      MethodSettings:
        - ResourcePath: '/*'
          HttpMethod: '*'
          LoggingLevel: INFO
          DataTraceEnabled: true
      Domain:
        DomainName: !Sub 'api-${Environment}.budgetbot.com'
        CertificateArn: arn:aws:acm:REGION:ACCOUNT:certificate/xxx

Outputs:
  ApiEndpoint:
    Description: API Gateway endpoint
    Value: !Sub 'https://${BudgetBotApi}.execute-api.${AWS::Region}.amazonaws.com/${Environment}'

  ParserQueueUrl:
    Description: SQS Queue URL
    Value: !Ref ParserQueue

  BudgetAlertTopicArn:
    Description: SNS Topic ARN
    Value: !Ref BudgetAlertTopic
```

Deploy with SAM:
```bash
sam build
sam deploy \
  --template-file template.yaml \
  --stack-name budgetbot-stack \
  --region ap-southeast-1 \
  --parameter-overrides \
    Environment=prod \
    DBEndpoint=rds-endpoint \
    DBPassword=secure-password \
  --capabilities CAPABILITY_NAMED_IAM
```

---

## 🔧 Step 5: Monitor & Debug

### CloudWatch Logs

```bash
# View Lambda logs
aws logs tail /aws/lambda/budgetbot-api --follow
aws logs tail /aws/lambda/budgetbot-parser --follow

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/budgetbot-parser \
  --filter-pattern "ERROR"
```

### X-Ray Tracing

```bash
# Enable X-Ray in Lambda environment
aws lambda update-function-configuration \
  --function-name budgetbot-parser \
  --tracing-config Mode=Active
```

In code:
```python
from aws_xray_sdk.core import xray_recorder

@xray_recorder.capture('parse_csv')
def parse_csv(data: bytes):
    # Your code here
    pass
```

---

## 🔄 Step 6: CI/CD Pipeline (GitHub Actions)

Tạo `.github/workflows/deploy.yml`:

```yaml
name: Deploy BudgetBot Lambdas

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install aws-sam-cli
      
      - name: Run tests
        run: |
          pytest tests/ -v
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-southeast-1
      
      - name: Build & Deploy
        if: github.ref == 'refs/heads/main'
        run: |
          sam build
          sam deploy \
            --no-confirm-changeset \
            --no-fail-on-empty-changeset \
            --stack-name budgetbot-prod \
            --parameter-overrides Environment=prod
```

---

## 📋 Deployment Checklist

```
Pre-Deployment:
  ☐ Test locally (FLOW_MODE=local)
  ☐ Run unit tests (pytest)
  ☐ Security scan (bandit, safety)
  ☐ Verify environment variables
  
Deployment:
  ☐ Build Lambda packages
  ☐ Upload Layer
  ☐ Create/Update Lambda functions
  ☐ Setup SQS triggers
  ☐ Configure API Gateway
  ☐ Create SNS topic
  ☐ Setup IAM roles
  ☐ Configure RDS security group
  ☐ Configure NAT Gateway (for outbound)
  
Post-Deployment:
  ☐ Test API endpoints (curl/postman)
  ☐ Check CloudWatch logs
  ☐ Monitor metrics (latency, errors)
  ☐ Test file upload → parsing flow
  ☐ Test budget alert
  ☐ Test chat functionality
  ☐ Load testing
  
Monitoring:
  ☐ Setup CloudWatch alarms
  ☐ Enable X-Ray tracing
  ☐ Setup log insights queries
  ☐ Create dashboard
```

---

## 🚨 Troubleshooting

### Common Issues

**1. RDS Connection Timeout**
```
❌ Problem: Lambda can't connect to RDS
✅ Solution:
   - Check VPC config on Lambda
   - Security group allows inbound 5432
   - RDS security group allows Lambda's security group
   - NAT Gateway exists for outbound
```

**2. Cold Start Too Long**
```
❌ Problem: Cold start > 30s
✅ Solution:
   - Reduce layer size
   - Minimize imports in handler
   - Use provisioned concurrency
   - Consider Lambda SnapStart (Java only)
```

**3. SQS Messages Not Processing**
```
❌ Problem: Messages stay in queue
✅ Solution:
   - Check Lambda function permissions
   - Verify SQS trigger mapping
   - Check Lambda timeout
   - Check CloudWatch logs for errors
   - Increase batch size if needed
```

**4. Bedrock Errors**
```
❌ Problem: "AccessDenied" calling Bedrock
✅ Solution:
   - Check IAM role has bedrock:InvokeModel
   - Check region supports Bedrock
   - Check model ID is correct
   - Check quota limits
```

---

## 💡 Tips & Tricks

### Faster Iterations
```bash
# Local hot reload with dependencies
uvicorn src.app:app --reload --port 8000

# Test Lambda locally with SAM
sam local start-api --port 3000

# Invoke function locally
sam local invoke LambdaParser -e events/sqs_event.json
```

### Cost Optimization
- Use reserved concurrency
- Scale down memory for simple functions
- Use S3 event notifications instead of polling
- Enable X-Ray sampling (not 100%)
- Archive old logs to S3

### Security
- Use Secrets Manager for passwords
- Enable VPC endpoints for S3, Secrets Manager
- Use KMS for encryption
- Enable CloudTrail logging
- Regular security audits

