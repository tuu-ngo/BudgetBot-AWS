import json
from datetime import datetime, timezone

def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Hello from CI/CD demo Lambda!",
            "deployed_by": "GitHub Actions",
            "deployed_at": datetime.now(timezone.utc).isoformat()
        })
    }