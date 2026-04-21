# V2AI LLM Readable Context

## Purpose
This file is a structured handoff context for another LLM.
It summarizes architecture, flow, components, state, and pending work in plain language.

## Project Identity
- Project name: V2AI Lecture Video Understanding System
- Workspace root: D:/Mlops_Dlops/MAJOR PROJECT
- Primary objective: End-to-end lecture understanding pipeline with upload, transcription, summary, concept extraction, retrieval-based QA, citation grounding, tracking, and deployment automation

## High-Level Architecture
- Frontend: Streamlit UI
- Backend: FastAPI
- Core pipeline service: Video pipeline orchestration for ingestion, processing, indexing, and QA
- NLP/LLM stack: Whisper, Hugging Face generation and summarization, Sentence Transformers, LangChain components, FAISS
- Data stores: PostgreSQL or SQLite, MinIO object store, local artifacts
- Ops stack: MLflow, optional WandB, Prometheus metrics endpoint, drift checker
- Infra stack: Docker, Docker Compose, GitHub Actions CI/CD

## Runtime Request Flows

### Flow A: Local Video Upload
1. UI sends file to API upload endpoint.
2. API calls video pipeline service.
3. Service saves video artifact locally.
4. Whisper transcribes audio/video and outputs text plus segments.
5. Service summarizes transcript, extracts concepts, and generates study materials.
6. Service chunks transcript segments and builds per-session FAISS index.
7. Service stores session metadata and outputs in DB plus transcript artifacts.
8. Service uploads optional artifacts to MinIO.
9. API returns session payload to UI.

### Flow B: YouTube URL Upload
1. UI sends URL to API URL upload endpoint.
2. Service validates URL pattern and downloads via yt-dlp.
3. Service runs same processing flow as local upload.
4. Source URL is persisted in metadata.

### Flow C: Ask Question
1. UI sends question with session ID.
2. Service loads session FAISS index.
3. Retriever selects top-k transcript chunks.
4. Prompt is built from retrieved context plus question.
5. Generation model produces answer.
6. Service cleans/deduplicates answer text.
7. Service returns answer with timestamp citations.
8. Query logs and inference metrics are recorded.

## Core Components and Responsibilities

### API Layer
- Hosts endpoints for health, metrics, upload, upload-url, ask, query alias, and session retrieval.
- Handles request validation and structured response models.

### Video Pipeline Service
- Owns all main lecture session operations.
- Provides ingestion, transcription, summary, concept extraction, study materials, index build, session persistence, and QA.
- Includes resilience fallback paths when heavy models fail to load.

### Retrieval and Indexing
- FAISS index is created per lecture session.
- QA always reads from session-specific index path.
- Citations include source filename plus start/end timestamps.

### Storage and Persistence
- DB stores lecture_sessions and query_logs.
- Local artifacts store uploads, transcripts, vectorstore, monitoring logs, sample files.
- MinIO integration stores video and transcript artifacts when configured.

### Tracking and Monitoring
- Inference records logged to request log file.
- Prometheus metrics exposed via API metrics endpoint.
- MLflow run logging enabled with graceful disable if backend unavailable.
- Drift checker computes shifts on latency and question-length distributions.

### Experiments and Versioning
- Evaluation script computes keyword and source match based proxy metrics.
- Registration script logs pyfunc model to MLflow registry.
- Full-pipeline script orchestrates optional session run, evaluation, registration, and drift check.

## Model Strategy and Fallback Logic
- Summary model routing:
  - CPU path uses lightweight summary model.
  - GPU path uses full summary model.
- Generation model routing:
  - CPU path uses lightweight generation model first.
  - GPU path uses full generation model first.
  - Candidate fallback order is applied if model loading fails.
- If summarization model cannot load, extractive summary fallback is used.
- If generation model cannot load, extractive answer fallback is used instead of crashing pipeline.

## Important Environment Variables
- HF_GENERATION_MODEL
- HF_GENERATION_MODEL_CPU
- HF_GENERATION_MODEL_GPU
- HF_SUMMARY_MODEL
- HF_SUMMARY_MODEL_CPU
- HF_SUMMARY_MODEL_GPU
- HF_EMBEDDING_MODEL
- WHISPER_MODEL_NAME
- WHISPER_LANGUAGE
- USE_GPU
- DATABASE_URL
- MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET
- MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME, REGISTERED_MODEL_NAME
- API_BASE_URL

## Folder-Level Summary
- src: Application code
- src/app/api: FastAPI routes and schemas
- src/app/services: Video pipeline and RAG services
- src/app/db: SQLAlchemy models and session config
- src/app/storage: MinIO artifact client
- src/app/tracking: MLflow and optional WandB trackers
- src/app/monitoring: Request log and drift checks
- src/app/experiments: Evaluation and model registration
- src/ui: Streamlit frontend
- scripts: Utility and orchestration scripts
- docker: Container images for API/UI/MLflow
- data: Knowledge corpus and evaluation set
- artifacts: Runtime outputs and generated files
- docs: Architecture, alignment, SOP, setup documentation
- .github/workflows: CI and CD workflows

## Current Status Snapshot
- Core proposal pipeline is implemented and running locally.
- YouTube URL ingestion is implemented and connected to UI.
- CPU/GPU model routing and memory-safe fallback logic are implemented.
- Lint and tests are passing.
- Runtime artifacts exist for uploads, transcripts, vector indexes, and request logs.

## Known Constraints
- Heavy model loading on low-memory Windows environments can still be expensive.
- Fallback paths prevent full pipeline crashes but can reduce answer richness.
- Session index persistence should be reviewed for long-running server restarts.
- CD deploy job requires configured server SSH secrets and image owner setup.

## Remaining Work for Production-Grade Completion
1. Run and archive formal evaluation reports.
2. Register and stage model versions in MLflow registry.
3. Finalize server deployment variables and secrets.
4. Strengthen persistence strategy for API-side vector artifacts.
5. Extend automated tests beyond API path coverage.

## Suggested File Reading Order for Another LLM
1. README.md
2. docs/PROPOSAL_ALIGNMENT.md
3. docs/ARCHITECTURE_DIAGRAM.md
4. src/app/config.py
5. src/app/api/main.py
6. src/app/services/video_pipeline_service.py
7. src/ui/streamlit_app.py
8. src/app/experiments/evaluate_rag.py
9. src/app/experiments/register_model.py
10. docker-compose.yml
11. .github/workflows/ci.yml
12. .github/workflows/cd.yml
