#!/usr/bin/env bash
# start_api_gpu.sh
# Starts the V2AI GPU API container using docker run (not compose).
# Use this when docker-compose runtime: nvidia is not picked up correctly.
#
# Usage:
#   cd ~/v2ai
#   chmod +x scripts/start_api_gpu.sh
#   bash scripts/start_api_gpu.sh
#
# Credentials are read from the .env file in the same directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[ERROR] .env file not found at $PROJECT_DIR/.env"
  echo "Run: cp .env.server-docker .env && echo 'HF_TOKEN=...' >> .env"
  exit 1
fi

# Load .env (ignore comments and empty lines)
set -o allexport
source <(grep -v '^\s*#' "$ENV_FILE" | grep -v '^\s*$')
set +o allexport

HF_TOKEN="${HF_TOKEN:-}"
WANDB_API_KEY="${WANDB_API_KEY:-}"

# Detect compose network name (docker-compose uses <project>_default)
NETWORK="v2ai_default"
if ! docker network inspect "$NETWORK" &>/dev/null; then
  echo "[WARN] Network $NETWORK not found, using bridge"
  NETWORK="bridge"
fi

# Stop and remove existing gpu container if running
if docker inspect v2ai-api-gpu &>/dev/null; then
  echo "==> Stopping existing v2ai-api-gpu container..."
  docker stop v2ai-api-gpu 2>/dev/null || true
  docker rm v2ai-api-gpu 2>/dev/null || true
fi

echo "==> Starting v2ai-api-gpu with --runtime=nvidia (GPU-1 only)..."
docker run -d \
  --name v2ai-api-gpu \
  --runtime=nvidia \
  --restart unless-stopped \
  --network "$NETWORK" \
  -e NVIDIA_VISIBLE_DEVICES=1 \
  -e PROJECT_ROOT=/app \
  -e APP_ENV=docker-gpu \
  -e PROJECT_NAME=V2AI-Lecture-Video-Understanding-System \
  -e MLFLOW_TRACKING_URI=http://v2ai-mlflow:5000 \
  -e MLFLOW_EXPERIMENT_NAME=rag_context_flow_experiments \
  -e REGISTERED_MODEL_NAME=rag-context-model \
  -e HF_TOKEN="$HF_TOKEN" \
  -e HF_SUMMARY_MODEL=facebook/bart-large-cnn \
  -e HF_SUMMARY_MODEL_CPU=sshleifer/distilbart-cnn-12-6 \
  -e HF_SUMMARY_MODEL_GPU=facebook/bart-large-cnn \
  -e HF_GENERATION_MODEL=google/flan-t5-base \
  -e HF_GENERATION_MODEL_CPU=google/flan-t5-small \
  -e HF_GENERATION_MODEL_GPU=google/flan-t5-base \
  -e HF_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2 \
  -e WHISPER_MODEL_NAME=base \
  -e WHISPER_LANGUAGE=en \
  -e DATABASE_URL=postgresql+psycopg2://v2ai:v2ai_secure_pass@v2ai-postgres:5432/v2ai \
  -e MINIO_ENDPOINT=v2ai-minio:9000 \
  -e MINIO_ACCESS_KEY=minioadmin \
  -e MINIO_SECRET_KEY=minioadmin123 \
  -e MINIO_BUCKET=lecture-artifacts \
  -e MINIO_SECURE=false \
  -e UPLOADS_PATH=/app/artifacts/uploads \
  -e TRANSCRIPT_STORE_PATH=/app/artifacts/transcripts \
  -e VECTOR_STORE_PATH=/app/artifacts/vectorstore \
  -e REQUEST_LOG_PATH=/app/artifacts/monitoring/request_logs.jsonl \
  -e RETRIEVAL_TOP_K=4 \
  -e CONCEPTS_TOP_K=12 \
  -e GENERATION_MAX_TOKENS=256 \
  -e GENERATION_TEMPERATURE=0.2 \
  -e USE_GPU=true \
  -e WANDB_API_KEY="$WANDB_API_KEY" \
  -e WANDB_PROJECT=v2ai-rag \
  -p 8001:8000 \
  -v "$PROJECT_DIR/data:/app/data" \
  -v "$PROJECT_DIR/artifacts:/app/artifacts" \
  v2ai-api-gpu

echo "==> Container started. Waiting 15s for startup..."
sleep 15

echo "==> GPU check inside container:"
docker exec v2ai-api-gpu python3 -c "
import torch
print('  CUDA available:', torch.cuda.is_available())
print('  Device count  :', torch.cuda.device_count())
if torch.cuda.is_available():
    props = torch.cuda.get_device_properties(0)
    print('  GPU name      :', props.name)
    print('  GPU memory    :', round(props.total_memory/1e9, 1), 'GB')
"

echo ""
echo "==> API health check:"
curl -s http://localhost:8001/health

echo ""
echo ""
echo "==> Done. API running at http://localhost:8001"
echo "    Docs: http://localhost:8001/docs"
