# Project File Map

## Core App
- `src/app/config.py`: Centralized settings from environment variables.
- `src/app/api/schemas.py`: Request/response models.
- `src/app/api/main.py`: FastAPI app and endpoints.
- `src/app/services/rag_service.py`: LangChain + Hugging Face RAG chain and FAISS index.
- `src/app/services/video_pipeline_service.py`: V2AI upload, transcription, summary, chunk/embed, QA.
- `src/app/db/models.py`: Session and query relational schema.
- `src/app/db/session.py`: SQLAlchemy engine and session management.
- `src/app/storage/minio_store.py`: MinIO artifact storage integration.

## Tracking and Monitoring
- `src/app/tracking/mlflow_tracker.py`: MLflow logging helper.
- `src/app/tracking/wandb_tracker.py`: Optional WandB logging helper.
- `src/app/monitoring/request_logger.py`: Persist request traces.
- `src/app/monitoring/drift_check.py`: Drift analysis report.

## Experiment and Versioning
- `src/app/experiments/evaluate_rag.py`: Evaluate model outputs and produce accuracy evidence.
- `src/app/experiments/register_model.py`: Register model in MLflow registry.
- `scripts/run_full_pipeline.py`: One-command orchestrator for the full pipeline.

## Frontend
- `src/ui/streamlit_app.py`: Styled project UI.

## Data
- `data/knowledge/*.txt`: Knowledge corpus used by retriever.
- `data/evaluation/eval_set.json`: Evaluation set used for metric substantiation.

## Infrastructure
- `docker/Dockerfile.api`: API container.
- `docker/Dockerfile.api.gpu`: GPU API container.
- `docker/Dockerfile.ui`: UI container.
- `docker/Dockerfile.mlflow`: MLflow container.
- `docker-compose.yml`: Local orchestrated stack.
- `k8s/*.yaml`: Kubernetes manifests.
- `k8s/postgres-*.yaml`: PostgreSQL persistence and service resources.
- `k8s/minio-*.yaml`: MinIO persistence and service resources.

## Automation
- `.github/workflows/ci.yml`: Lint + tests.
- `.github/workflows/cd.yml`: Build, push, and deploy pipeline.
