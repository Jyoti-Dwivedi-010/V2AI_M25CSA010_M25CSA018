from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.experiments.evaluate_rag import run_evaluation
from app.experiments.register_model import register_model
from app.monitoring.drift_check import run_drift_check
from app.services.rag_service import get_rag_service
from app.services.video_pipeline_service import get_video_pipeline_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run complete V2AI pipeline: optional video session processing, "
            "evaluation, versioning, and monitoring"
        )
    )
    parser.add_argument(
        "--video-path",
        default="",
        help="Optional lecture video path for session processing",
    )
    parser.add_argument(
        "--title",
        default="",
        help="Optional title for uploaded lecture session",
    )
    parser.add_argument(
        "--question",
        default="",
        help="Optional question asked immediately after session creation",
    )
    parser.add_argument(
        "--skip-eval",
        action="store_true",
        help="Skip evaluation stage",
    )
    parser.add_argument(
        "--skip-register",
        action="store_true",
        help="Skip model registration in MLflow model registry",
    )
    parser.add_argument(
        "--skip-drift-check",
        action="store_true",
        help="Skip monitoring drift check step",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.video_path.strip():
        video_path = Path(args.video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        video_service = get_video_pipeline_service()
        session = video_service.create_session(
            filename=video_path.name,
            content=video_path.read_bytes(),
            title=args.title or None,
        )
        print("[PIPELINE] Video session created")
        print(json.dumps(session, indent=2))

        if args.question.strip():
            answer = video_service.ask_question(
                session_id=session["session_id"],
                question=args.question.strip(),
            )
            print("[PIPELINE] Session question answered")
            print(json.dumps(answer, indent=2))

    # Step 1: build/load vector index.
    service = get_rag_service()
    print(
        f"[PIPELINE] RAG service ready. Vector store at: {service.settings.vector_store_path}"
    )

    # Step 2: run evaluation and log experiments.
    if not args.skip_eval:
        eval_report = run_evaluation()
        print("[PIPELINE] Evaluation complete")
        print(json.dumps(eval_report, indent=2))

    # Step 3: register model version in MLflow.
    if not args.skip_register:
        run_id = register_model()
        print(f"[PIPELINE] Model registered via run_id={run_id}")

    # Step 4: run drift report.
    if not args.skip_drift_check:
        drift_report = run_drift_check()
        print("[PIPELINE] Drift report generated")
        print(json.dumps(drift_report, indent=2))


if __name__ == "__main__":
    main()
