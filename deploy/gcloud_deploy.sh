#!/usr/bin/env bash
# gcloud_deploy.sh — Deploy V2AI to Google Cloud Run (CPU) or GKE (GPU)
# Requirements: gcloud CLI authenticated, Docker installed locally
# Usage: bash deploy/gcloud_deploy.sh [region] [project-id]
#
# IMPORTANT: Run this on your LOCAL WINDOWS PC (WSL or Git Bash)
# or on Google Cloud Shell — NOT on the university server.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_ID="${2:-your-gcloud-project-id}"
REGION="${1:-asia-south1}"
REPO="v2ai"
REGISTRY="gcr.io/$PROJECT_ID"
IMAGE_API="$REGISTRY/v2ai-api"
IMAGE_UI="$REGISTRY/v2ai-ui"
SERVICE_API="v2ai-api"
SERVICE_UI="v2ai-ui"

# ── Detect Windows (Git Bash / PowerShell) ────────────────────────────────────
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
  echo "[INFO] Detected Windows environment (Git Bash)"
fi

echo "=================================================================="
echo " V2AI — Google Cloud Deployment"
echo " Project : $PROJECT_ID"
echo " Region  : $REGION"
echo "=================================================================="

# ── Step 1: Authenticate ──────────────────────────────────────────────────────
echo ""
echo "[1/7] Authenticating with Google Cloud..."
gcloud auth configure-docker --quiet
gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"

# ── Step 2: Enable APIs ───────────────────────────────────────────────────────
echo ""
echo "[2/7] Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  --quiet

# ── Step 3: Build & push API image ────────────────────────────────────────────
echo ""
echo "[3/7] Building and pushing API image..."
docker build -f docker/Dockerfile.api -t "$IMAGE_API:latest" .
docker push "$IMAGE_API:latest"

# ── Step 4: Build & push UI image ─────────────────────────────────────────────
echo ""
echo "[4/7] Building and pushing UI image..."
docker build -f docker/Dockerfile.ui -t "$IMAGE_UI:latest" .
docker push "$IMAGE_UI:latest"

# ── Step 5: Deploy PostgreSQL via Cloud SQL ───────────────────────────────────
echo ""
echo "[5/7] Setting up Cloud SQL (PostgreSQL)..."
INSTANCE_NAME="v2ai-postgres"
DB_NAME="v2ai"
DB_USER="v2ai"
DB_PASS="v2ai_secure_pass"

# Create instance if it doesn't exist
if ! gcloud sql instances describe "$INSTANCE_NAME" --quiet 2>/dev/null; then
  gcloud sql instances create "$INSTANCE_NAME" \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region="$REGION" \
    --quiet
fi

# Create database and user
gcloud sql databases create "$DB_NAME" --instance="$INSTANCE_NAME" --quiet 2>/dev/null || true
gcloud sql users create "$DB_USER" \
  --instance="$INSTANCE_NAME" \
  --password="$DB_PASS" \
  --quiet 2>/dev/null || true

CLOUD_SQL_CONNECTION=$(gcloud sql instances describe "$INSTANCE_NAME" --format="value(connectionName)")
echo "Cloud SQL connection: $CLOUD_SQL_CONNECTION"

# ── Step 6: Deploy API to Cloud Run ──────────────────────────────────────────
echo ""
echo "[6/7] Deploying API to Cloud Run..."
gcloud run deploy "$SERVICE_API" \
  --image "$IMAGE_API:latest" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 4 \
  --concurrency 4 \
  --min-instances 0 \
  --max-instances 3 \
  --add-cloudsql-instances "$CLOUD_SQL_CONNECTION" \
  --set-env-vars "\
APP_ENV=cloudrun,\
PROJECT_NAME=V2AI-Lecture-Video-Understanding-System,\
DATABASE_URL=postgresql+psycopg2://v2ai:v2ai_secure_pass@localhost/v2ai?host=/cloudsql/$CLOUD_SQL_CONNECTION,\
HF_TOKEN=${HF_TOKEN:-your_hf_token_here},\
HF_GENERATION_MODEL=google/flan-t5-small,\
HF_GENERATION_MODEL_CPU=google/flan-t5-small,\
HF_SUMMARY_MODEL=sshleifer/distilbart-cnn-12-6,\
HF_SUMMARY_MODEL_CPU=sshleifer/distilbart-cnn-12-6,\
HF_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2,\
WHISPER_MODEL_NAME=base,\
WHISPER_LANGUAGE=en,\
USE_GPU=false,\
MLFLOW_TRACKING_URI=http://localhost:5000,\
MLFLOW_EXPERIMENT_NAME=rag_context_flow_experiments,\
RETRIEVAL_TOP_K=4,\
CONCEPTS_TOP_K=12,\
GENERATION_MAX_TOKENS=256,\
GENERATION_TEMPERATURE=0.2,\
MINIO_ENDPOINT=,\
MINIO_BUCKET=lecture-artifacts,\
UPLOADS_PATH=/tmp/uploads,\
TRANSCRIPT_STORE_PATH=/tmp/transcripts,\
VECTOR_STORE_PATH=/tmp/vectorstore,\
REQUEST_LOG_PATH=/tmp/request_logs.jsonl" \
  --quiet

API_URL=$(gcloud run services describe "$SERVICE_API" \
  --region "$REGION" \
  --format "value(status.url)")
echo "API deployed at: $API_URL"

# ── Step 7: Deploy UI to Cloud Run ───────────────────────────────────────────
echo ""
echo "[7/7] Deploying UI to Cloud Run..."
gcloud run deploy "$SERVICE_UI" \
  --image "$IMAGE_UI:latest" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --concurrency 10 \
  --min-instances 0 \
  --max-instances 2 \
  --set-env-vars "API_BASE_URL=$API_URL" \
  --quiet

UI_URL=$(gcloud run services describe "$SERVICE_UI" \
  --region "$REGION" \
  --format "value(status.url)")

echo ""
echo "=================================================================="
echo " DEPLOYMENT COMPLETE"
echo "=================================================================="
echo " UI  : $UI_URL"
echo " API : $API_URL"
echo " API docs: $API_URL/docs"
echo "=================================================================="
