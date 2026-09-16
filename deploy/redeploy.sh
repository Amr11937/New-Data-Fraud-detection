#!/usr/bin/env bash
# Rebuild the backend image, push a new tag to ECR, register a new task
# definition revision, and roll the ECS service onto it.
#
# Prereqs: `aws configure` already run, Docker Desktop running, and
# frontend/dist already built into backend/frontend_dist (run
# `cd frontend && npm run build && rm -rf ../backend/frontend_dist/* && \
#   cp -r dist/* ../backend/frontend_dist/` first if the frontend changed).
#
# See DEPLOYMENT.md for the resource names this script assumes.
set -euo pipefail

AWS_ACCOUNT_ID="486872284508"
AWS_REGION="us-east-1"
ECR_REPO="pcrf-fms"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
CLUSTER="pcrf-fms-cluster"
SERVICE="pcrf-fms-service"
FAMILY="pcrf-fms"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAG="$(date +%Y%m%d-%H%M%S)"

echo "=== Building image (tag: $TAG) ==="
cd "$REPO_ROOT/backend"
docker build -t "${ECR_REPO}:${TAG}" .

echo "=== Pushing to ECR ==="
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
docker tag "${ECR_REPO}:${TAG}" "${ECR_URI}:${TAG}"
docker tag "${ECR_REPO}:${TAG}" "${ECR_URI}:latest"
docker push "${ECR_URI}:${TAG}"
docker push "${ECR_URI}:latest"

echo "=== Registering new task definition revision ==="
CURRENT_TASKDEF=$(aws ecs describe-task-definition --task-definition "$FAMILY" --query 'taskDefinition' --output json)
NEW_TASKDEF=$(echo "$CURRENT_TASKDEF" | python -c "
import json, sys
td = json.load(sys.stdin)
td['containerDefinitions'][0]['image'] = '${ECR_URI}:${TAG}'
for key in ('taskDefinitionArn','revision','status','requiresAttributes','compatibilities','registeredAt','registeredBy'):
    td.pop(key, None)
print(json.dumps(td))
")
TASKDEF_FILE="$REPO_ROOT/deploy/.tmp_taskdef.json"
echo "$NEW_TASKDEF" > "$TASKDEF_FILE"
NEW_TASKDEF_ARN=$(aws ecs register-task-definition --cli-input-json "file://$TASKDEF_FILE" --query 'taskDefinition.taskDefinitionArn' --output text)
rm -f "$TASKDEF_FILE"
echo "New task definition: $NEW_TASKDEF_ARN"

echo "=== Updating ECS service ==="
aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" --task-definition "$NEW_TASKDEF_ARN" --force-new-deployment --output text --query 'service.serviceName'

echo "=== Waiting for the service to stabilize (this can take a few minutes) ==="
aws ecs wait services-stable --cluster "$CLUSTER" --services "$SERVICE"

echo "=== Done. New revision is live. ==="
