# SOP (Standard Operating Procedure)

## Objective
Establish repeatable and auditable process for development, experiments, deployment, and monitoring.

## A. Development SOP
1. Create branch from `develop` as `feature/<topic>`.
2. Implement changes with tests.
3. Ensure `ruff` and `pytest` pass.
4. Open PR to `develop`.
5. Merge to `main` only after review and release readiness.

## B. Data and Context SOP
1. Upload lecture videos through UI or `POST /upload-video`.
2. Confirm transcript artifact is generated in `artifacts/transcripts/`.
3. Confirm session index exists in `artifacts/vectorstore/<session_id>/`.
4. Document source lecture and upload timestamp in commit/report notes.

## C. Experiment SOP
1. Update `data/evaluation/eval_set.json`.
2. Run `python -m app.experiments.evaluate_rag`.
3. Verify metrics in:
   - MLflow experiment dashboard.
   - `artifacts/reports/latest_eval.json`.
4. If claiming 90-95% performance, include report screenshot and run ID.

## D. Model Versioning SOP
1. Run `python -m app.experiments.register_model`.
2. Record model version and associated git commit SHA.
3. Promote model stage only after evaluation threshold is met.

## E. Deployment SOP
1. Build and push Docker images.
2. Deploy storage services first (`postgres`, `minio`, `mlflow`).
3. Apply API and UI manifests in documented order.
3. Verify health checks and pods.
4. Run smoke tests through UI and API.

## F. Monitoring SOP
1. Check `/metrics` endpoint.
2. Review `request_logs.jsonl` regularly.
3. Review `query_logs` table for QA traceability.
4. Review MinIO bucket object history for artifact lineage.
5. Run drift report daily/weekly depending on traffic.
6. Trigger re-index and re-evaluation on drift alert.
7. Run cleanup policy script weekly:
   - `python scripts/cleanup_sessions.py --retention-days 30`

## G. Incident SOP
1. If API error rate spikes, pause rollout.
2. Roll back to previous image tag.
3. Restore previous model version.
4. File incident report with root cause and preventive action.
