#!/usr/bin/env bash
# deploy_server.sh — Deploy V2AI to GPU server sujiv1@10.6.0.46
# Usage: bash scripts/deploy_server.sh
# Requires: sshpass (install with: sudo apt-get install sshpass)

set -euo pipefail

SERVER_HOST="10.6.0.46"
SERVER_USER="sujiv1"
SERVER_PASS="sujiv1"
REMOTE_DIR="~/v2ai"
REPO_URL="https://github.com/Jyoti-Dwivedi-010/V2AI_M25CSA010_M25CSA018.git"

echo "==> Deploying V2AI to $SERVER_USER@$SERVER_HOST"

# Check sshpass
if ! command -v sshpass &>/dev/null; then
  echo "[ERROR] sshpass not found. Install: sudo apt-get install sshpass"
  exit 1
fi

SSH="sshpass -p '$SERVER_PASS' ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_HOST"
SCP="sshpass -p '$SERVER_PASS' scp -o StrictHostKeyChecking=no"

echo "==> Cloning / pulling repo on server..."
eval $SSH "
  if [ -d $REMOTE_DIR ]; then
    cd $REMOTE_DIR && git pull origin main
  else
    git clone $REPO_URL $REMOTE_DIR && cd $REMOTE_DIR
  fi
"

echo "==> Copying .env.server-docker as .env..."
eval $SSH "cp $REMOTE_DIR/.env.server-docker $REMOTE_DIR/.env"

echo "==> Creating artifact directories..."
eval $SSH "
  cd $REMOTE_DIR
  mkdir -p artifacts/uploads artifacts/transcripts artifacts/vectorstore \
    artifacts/monitoring artifacts/reports artifacts/mlflow \
    artifacts/postgres artifacts/minio artifacts/prometheus artifacts/grafana
"

echo "==> Starting base services (postgres, minio, mlflow, prometheus, grafana)..."
eval $SSH "
  cd $REMOTE_DIR
  docker-compose up -d postgres minio mlflow prometheus grafana
  echo 'Waiting 15s for services to initialize...'
  sleep 15
"

echo "==> Starting GPU API (GPU-1 only) and UI..."
eval $SSH "
  cd $REMOTE_DIR
  docker-compose --profile gpu up -d api-gpu ui
"

echo "==> Deployment status:"
eval $SSH "cd $REMOTE_DIR && docker-compose ps"

echo ""
echo "==> Services available at:"
echo "    UI:         http://$SERVER_HOST:8501"
echo "    API:        http://$SERVER_HOST:8001"
echo "    MLflow:     http://$SERVER_HOST:5000"
echo "    Prometheus: http://$SERVER_HOST:9090"
echo "    Grafana:    http://$SERVER_HOST:3000  (admin / v2ai_grafana)"
echo "    MinIO:      http://$SERVER_HOST:9001  (minioadmin / minioadmin123)"
