# V2AI — Complete Setup & Deployment Guide

## Repository
https://github.com/Jyoti-Dwivedi-010/V2AI_M25CSA010_M25CSA018

---

## PART A: Deploy on GPU Server (sujiv1@10.6.0.46)

### Prerequisites
- You must be on the **same university network** as the server (i.e. connected to college WiFi/LAN)
- SSH access to `sujiv1@10.6.0.46` (password: `sujiv1`)

### Step 1 — SSH into server
```bash
ssh sujiv1@10.6.0.46
# Password: sujiv1
```

### Step 2 — Clone repository
```bash
git clone https://github.com/Jyoti-Dwivedi-010/V2AI_M25CSA010_M25CSA018.git ~/v2ai
cd ~/v2ai
```

### Step 3 — Create .env with your credentials
```bash
cp .env.server-docker .env

# Add your real credentials (replace the values below)
cat >> .env << 'EOF'
HF_TOKEN=<your_hf_token>         # see .env.secrets.example
WANDB_API_KEY=<your_wandb_key>   # see .env.secrets.example
EOF
```

### Step 4 — Create required directories
```bash
mkdir -p artifacts/{uploads,transcripts,vectorstore,monitoring,reports,mlflow,postgres,minio,prometheus,grafana}
```

### Step 5 — Export credentials & start services
```bash
export HF_TOKEN=<your_hf_token>
export WANDB_API_KEY=<your_wandb_key>

# Start base services
docker-compose up -d postgres minio mlflow prometheus grafana
sleep 20

# Start GPU API (GPU-1 only) + UI
docker-compose --profile gpu up -d api-gpu ui
```

### Step 6 — Verify
```bash
docker-compose ps

# Health check
curl http://localhost:8001/health
# Expected: {"status":"ok","environment":"docker-gpu"}
```

### Step 7 — Access services (from your local PC on the same network)
| Service | URL | Credentials |
|---|---|---|
| Streamlit UI | http://10.6.0.46:8501 | — |
| FastAPI | http://10.6.0.46:8001/docs | — |
| MLflow | http://10.6.0.46:5000 | — |
| Prometheus | http://10.6.0.46:9090 | — |
| Grafana | http://10.6.0.46:3000 | admin / v2ai_grafana |
| MinIO Console | http://10.6.0.46:9001 | minioadmin / minioadmin123 |

---

## PART B: Setup GitHub Secrets for Automatic CD

Go to: https://github.com/Jyoti-Dwivedi-010/V2AI_M25CSA010_M25CSA018/settings/secrets/actions

Add these **Repository Secrets**:

| Secret Name | Value |
|---|---|
| `SERVER_HOST` | `10.6.0.46` |
| `SERVER_USER` | `sujiv1` |
| `SERVER_PASSWORD` | `sujiv1` |
| `HF_TOKEN` | `<your_hf_token>` (from .env.secrets.example) |
| `WANDB_API_KEY` | `<your_wandb_key>` (from .env.secrets.example) |

After adding these, every push to `main` will **automatically build Docker images and deploy to the server**.

---

## PART C: Google Cloud Deployment (from your local Windows PC)

### Prerequisites
```powershell
# Install Google Cloud CLI
# Download: https://cloud.google.com/sdk/docs/install

# After installation, authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud auth configure-docker
```

### Run the deploy script
```bash
# In Git Bash or WSL on Windows:
cd "d:/Mlops_Dlops/MAJOR PROJECT"
chmod +x deploy/gcloud_deploy.sh

# Set credentials first
export HF_TOKEN=<your_hf_token>

# Deploy (replace with your Google Cloud project ID)
bash deploy/gcloud_deploy.sh asia-south1 YOUR_GCP_PROJECT_ID
```

---

## PART D: Running Evaluation & Model Registration

After the stack is running on the server:

```bash
# On the server (ssh in first)
cd ~/v2ai

# Run RAG evaluation (logs to MLflow + WandB)
docker exec v2ai-api-gpu python3 -m app.experiments.evaluate_rag

# Register model to MLflow
docker exec v2ai-api-gpu python3 -m app.experiments.register_model

# Promote to Staging
docker exec v2ai-api-gpu python3 -m app.experiments.promote_model --stage staging

# Promote to Production (after verification)
docker exec v2ai-api-gpu python3 -m app.experiments.promote_model --stage production
```

---

## Useful Commands

```bash
# View logs
docker-compose logs -f api-gpu

# Restart just the API
docker-compose --profile gpu restart api-gpu

# Rebuild after code changes
git pull origin main
docker-compose --profile gpu up -d --build api-gpu

# Stop everything
docker-compose --profile gpu down

# Check GPU is GPU-1 only
docker exec v2ai-api-gpu python3 -c "import torch; print(torch.cuda.current_device(), torch.cuda.get_device_name())"
```
