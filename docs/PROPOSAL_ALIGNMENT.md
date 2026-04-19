# V2AI Proposal Alignment

This document maps each block in your proposal diagram to implementation files.

## Workflow Diagram Mapping

1. User Upload Video
- API endpoint: `POST /upload-video`
- Code: `src/app/api/main.py`, `src/app/services/video_pipeline_service.py`
- UI: `src/ui/streamlit_app.py`

2. Video Preprocessing
- Uploaded binary persisted in `artifacts/uploads/`
- Code: `V2AIPipelineService._save_local_video`

3. Speech-to-Text
- OpenAI Whisper transcription over video/audio stream
- Code: `V2AIPipelineService._transcribe`

4. Transcript + Metadata
- Transcript segments saved in `artifacts/transcripts/<session_id>.json`
- Session metadata stored in PostgreSQL table `lecture_sessions`
- Includes video fingerprint (`video_sha256`) and size metadata

5. Chunk + Embed
- Transcript segments are grouped and embedded with sentence transformers
- FAISS index saved per session in `artifacts/vectorstore/<session_id>/`

6. Question Context Build
- Retriever selects top-k session chunks for each question
- Prompt contains timestamp-rich transcript context only

7. LLM + RAG Response
- Hugging Face generation model answers using retrieved context
- Timestamp citations returned with each answer

8. Multi-Format Output Generation
- Flashcards and quiz questions generated from transcript + summary context
- Returned in upload response and rendered in UI

8. Streamlit UI Interface
- Upload/process controls, summary/concepts, QA panel, clickable timestamp jumps
- Code: `src/ui/streamlit_app.py`

9. Store Session
- PostgreSQL stores session and question logs
- MinIO stores uploaded video and transcript artifact copies

10. Clickable Response
- Citations provide `start_hms` and `end_hms`
- UI jump buttons set video player start time to citation timestamp

11. Automated Data Cleanup
- `scripts/cleanup_sessions.py` removes old sessions and local artifacts
- Supports retention policy for long-running deployments

## Methodology Mapping

- Data ingestion and processing: `upload-video` + Whisper + artifact persistence
- NLP extraction: BART summary + Sentence-BERT concept ranking
- LangChain context flow: retrieval + prompt + generation parser chain
- Containerization: Dockerfiles and docker-compose stack
- Deployment: Kubernetes manifests under `k8s/`
- Database strategy: PostgreSQL session schema (`lecture_sessions`, `query_logs`)
- File strategy: MinIO object store integration

## Guide Feedback Coverage

- LangChain usage elaborated: yes, documented and implemented in session QA flow.
- Experiment tracking: MLflow logging active, optional WandB hooks available.
- CI/CD details: GitHub Actions workflows for CI and CD.
- Accuracy substantiation: evaluation script logs measurable metrics and report artifact.
- Model versioning: MLflow model registry script included.
- Monitoring: request logs, Prometheus endpoint, drift report script.
