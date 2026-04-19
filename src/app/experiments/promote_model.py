"""
promote_model.py
----------------
MLflow model stage promotion script.
Promotes the latest registered model version to Staging or Production.

Usage:
    python -m app.experiments.promote_model --stage staging
    python -m app.experiments.promote_model --stage production --version 3
"""
from __future__ import annotations

import argparse
import logging
import sys

logger = logging.getLogger(__name__)


def promote(stage: str, version: str | None = None) -> None:
    try:
        import mlflow
        from mlflow.tracking import MlflowClient
    except ImportError:
        print("[ERROR] mlflow not installed. Run: pip install mlflow")
        sys.exit(1)

    from app.config import load_settings

    settings = load_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    model_name = settings.registered_model_name

    # Get latest version if not specified
    if version is None:
        try:
            versions = client.get_latest_versions(model_name)
            if not versions:
                print(f"[ERROR] No registered versions found for model '{model_name}'")
                sys.exit(1)
            version = versions[-1].version
        except Exception as exc:
            print(f"[ERROR] Could not fetch model versions: {exc}")
            sys.exit(1)

    stage_map = {
        "staging": "Staging",
        "production": "Production",
        "none": "None",
        "archived": "Archived",
    }
    mlflow_stage = stage_map.get(stage.lower(), "Staging")

    try:
        client.transition_model_version_stage(
            name=model_name,
            version=str(version),
            stage=mlflow_stage,
            archive_existing_versions=(mlflow_stage == "Production"),
        )
        print(f"[OK] Model '{model_name}' v{version} → {mlflow_stage}")
    except Exception as exc:
        print(f"[ERROR] Stage transition failed: {exc}")
        sys.exit(1)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Promote MLflow model to a stage")
    parser.add_argument(
        "--stage",
        required=True,
        choices=["staging", "production", "none", "archived"],
        help="Target MLflow stage",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Model version to promote (default: latest)",
    )
    args = parser.parse_args()
    promote(stage=args.stage, version=args.version)


if __name__ == "__main__":
    main()
