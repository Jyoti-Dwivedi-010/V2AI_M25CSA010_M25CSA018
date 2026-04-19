# SERVER_DEPLOY_COMMANDS.md
# Copy-paste these commands one section at a time after SSH-ing into the server.
# SSH command: ssh sujiv1@10.6.0.46 (password: sujiv1)

## Step 1 — Clone the repository
```bash
git clone https://github.com/Jyoti-Dwivedi-010/V2AI_M25CSA010_M25CSA018.git ~/v2ai
cd ~/v2ai
```

If already cloned, update it:
```bash
cd ~/v2ai
git fetch origin
git reset --hard origin/main
```

---

## Step 2 — Set credentials and create .env
```bash
cd ~/v2ai

# Copy the server env template
cp .env.server-docker .env

# Append your real credentials (these are NOT committed to git)
echo "HF_TOKEN=YOUR_HF_TOKEN_HERE" >> .env
echo "WANDB_API_KEY=YOUR_WANDB_API_KEY_HERE" >> .env

# Create artifact directories
mkdir -p artifacts/uploads artifacts/transcripts artifacts/vectorstore \
    artifacts/monitoring artifacts/reports artifacts/mlflow \
    artifacts/postgres artifacts/minio artifacts/prometheus artifacts/grafana
```

---

## Step 3 — Export credentials to shell environment
```bash
export HF_TOKEN=YOUR_HF_TOKEN_HERE
export WANDB_API_KEY=YOUR_WANDB_API_KEY_HERE
```

---

## Step 4 — Start base services (postgres, minio, mlflow, prometheus, grafana)
```bash
cd ~/v2ai
docker-compose up -d postgres minio mlflow prometheus grafana
```

Wait 20 seconds, then check:
```bash
docker-compose ps
```

All these should show "Up": postgres, minio, mlflow, prometheus, grafana

---

## Step 5 — Start GPU API (GPU-1 ONLY) and UI
```bash
cd ~/v2ai
docker-compose --profile gpu up -d api-gpu ui
```

Wait 30 seconds (models loading), then:
```bash
docker-compose ps
```

---

## Step 6 — Health check
```bash
curl http://localhost:8001/health
# Should return: {"status":"ok","environment":"docker-gpu"}

curl http://localhost:8501/_stcore/health
# Should return: ok
```

---

## Step 7 — Tail logs to confirm pipeline is working
```bash
docker-compose logs -f api-gpu
```

---

## Service URLs (from your local PC on same network)
| Service | URL |
|---|---|
| **Streamlit UI** | http://10.6.0.46:8501 |
| **FastAPI** | http://10.6.0.46:8001 |
| **API Docs** | http://10.6.0.46:8001/docs |
| **MLflow** | http://10.6.0.46:5000 |
| **Prometheus** | http://10.6.0.46:9090 |
| **Grafana** | http://10.6.0.46:3000 (admin / v2ai_grafana) |
| **MinIO Console** | http://10.6.0.46:9001 (minioadmin / minioadmin123) |

---

## Useful commands
```bash
# View all running containers
docker-compose ps

# View GPU usage (confirm GPU-1 is being used)
docker exec v2ai-api-gpu python3 -c "import torch; print('CUDA:', torch.cuda.is_available(), '| Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"

# Stop all services
docker-compose --profile gpu down

# Rebuild and restart (after code changes)
git pull origin main
docker-compose --profile gpu up -d --build api-gpu ui

# Run evaluation
docker exec v2ai-api-gpu python3 -m app.experiments.evaluate_rag

# Run model registration
docker exec v2ai-api-gpu python3 -m app.experiments.register_model
```
