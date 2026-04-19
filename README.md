# V2AI: AI Lecture Video Understanding System

This repository implements your proposal pipeline end-to-end:

- Video upload from Streamlit to FastAPI (local file or YouTube URL)
- Video preprocessing and OpenAI Whisper transcription
- Transcript + metadata persistence
- Chunking + embedding (Sentence-BERT) for retrieval
- LangChain context flow for question answering
- Flashcards and quiz generation from transcript context
- Hugging Face summarization and generation
- Session storage in PostgreSQL
- Artifact storage/versioning in MinIO
- Experiment tracking with MLflow (optional WandB)
- Monitoring with logs + Prometheus + drift checks
- Containerized deployment with Docker and Kubernetes
- GitHub CI/CD workflows

Proposal mapping: see `docs/PROPOSAL_ALIGNMENT.md`.

## 1. Tech Stack (as in proposal)

- Backend: FastAPI
- Frontend: Streamlit
- STT: OpenAI Whisper
- NLP: Hugging Face Transformers + Sentence-BERT
- Context flow orchestration: LangChain
- Vector index: FAISS
- DB: PostgreSQL
- Object store: MinIO
- Tracking: MLflow (+ optional WandB)
- Containerization: Docker
- Orchestration: Kubernetes

## 2. Project File Map (important)

- `src/app/services/video_pipeline_service.py`
  - Full V2AI pipeline implementation.
- `src/app/api/main.py`
  - API endpoints for upload, ask, session retrieval.
- `src/app/db/models.py`
  - PostgreSQL schema (`lecture_sessions`, `query_logs`).
- `src/app/storage/minio_store.py`
  - MinIO artifact upload helper.
- `src/ui/streamlit_app.py`
  - Attractive UI with clickable timestamp jumps.
- `docker-compose.yml`
  - Local multi-service stack.
- `k8s/*.yaml`
  - Kubernetes manifests.
- `.github/workflows/*.yml`
  - CI/CD pipelines.

## 3. API Endpoints

- `GET /health`
- `GET /metrics`
- `POST /upload-video`
  - form-data: `file`, optional `title`
  - returns `session_id`, summary, concepts, flashcards, quiz, duration, transcript stats
- `POST /upload-video-url`
  - json: `video_url`, optional `title`
  - currently supports YouTube (`youtube.com` / `youtu.be`) URLs
  - returns `session_id`, summary, concepts, flashcards, quiz, duration, transcript stats
- `POST /ask`
  - json: `session_id`, `question`
  - returns answer with timestamp citations
- `POST /query`
  - alias for ask (uses latest session if `session_id` omitted)
- `GET /session/{session_id}`

## 4. Local Run (Windows, no Docker)

### Step 1: Use Python 3.11

```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2: Set environment file

```powershell
Copy-Item .env.example .env
```

### Step 3: Start API

```powershell
$env:PYTHONPATH="src"
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 4: Start UI

```powershell
$env:PYTHONPATH="src"
streamlit run src/ui/streamlit_app.py
```

## 5. Docker Run

```powershell
docker compose up --build
```

Services:
- API: `http://localhost:8000`
- UI: `http://localhost:8501`
- MLflow: `http://localhost:5000`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`
- PostgreSQL: `localhost:5432`

GPU profile:

```powershell
docker compose --profile gpu up --build
```

## 6. Kubernetes Deploy

Before deploying, replace `YOUR_GITHUB_USERNAME` in:
- `k8s/api-deployment.yaml`
- `k8s/api-deployment-gpu.yaml`
- `k8s/ui-deployment.yaml`

Deploy sequence:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres-pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/minio-pvc.yaml
kubectl apply -f k8s/minio-deployment.yaml
kubectl apply -f k8s/mlflow-pvc.yaml
kubectl apply -f k8s/mlflow-deployment.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/ui-deployment.yaml
kubectl apply -f k8s/hpa-api.yaml
```

Optional GPU API:

```bash
kubectl apply -f k8s/api-deployment-gpu.yaml
```

## 7. Accuracy Claim Substantiation

Do not present 90-95% or 99.95% claims without measured evidence.

Use:

```powershell
$env:PYTHONPATH="src"
python -m app.experiments.evaluate_rag
```

Evidence artifact:
- `artifacts/reports/latest_eval.json`

Also track metrics trend in MLflow and attach run IDs in your report.

## 8. GitHub Versioning + CI/CD

- Branch model: `main`, `develop`, `feature/*`, `hotfix/*`
- Semantic tags: `vMAJOR.MINOR.PATCH`
- CI workflow: lint + tests
- CD workflow: build/push images to GHCR and deploy to Kubernetes

CD secret required:
- `KUBE_CONFIG_DATA` (base64 kubeconfig)

## 9. Server Run (your GPU server)

Target:
- `m25csa0xx@172.25.1.123`

Detailed setup:
- `docs/SERVER_SETUP.md`

## 10. Notes

- Whisper requires ffmpeg. API Docker images already install ffmpeg.
- For large videos, transcription can take several minutes.
- Session-specific vector indexes are automatically created during upload.
- Video fingerprint (`sha256`) is stored in session metadata for artifact traceability.

## 11. Automated Cleanup

Run cleanup for old sessions and local artifacts:

```powershell
$env:PYTHONPATH="src"
python scripts/cleanup_sessions.py --retention-days 30
```

Or with Makefile:

```bash
make cleanup DAYS=30
```
