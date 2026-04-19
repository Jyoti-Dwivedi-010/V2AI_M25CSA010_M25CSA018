"""
wandb_tracker.py
----------------
WandB integration wired to the V2AI pipeline.
Gracefully disabled if WANDB_API_KEY is not set or wandb is unavailable.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    import wandb  # type: ignore[import-untyped]
    _WANDB_AVAILABLE = True
except ImportError:  # pragma: no cover
    wandb = None  # type: ignore[assignment]
    _WANDB_AVAILABLE = False


class WandBTracker:
    def __init__(self) -> None:
        self.enabled = False
        api_key = os.getenv("WANDB_API_KEY", "")
        wandb_project = os.getenv("WANDB_PROJECT", "v2ai-rag")
        wandb_entity = os.getenv("WANDB_ENTITY", "")

        if not _WANDB_AVAILABLE or not api_key:
            logger.info("WandB disabled: not installed or WANDB_API_KEY not set.")
            return

        try:
            wandb.login(key=api_key, relogin=True, verify=False)
            self._project = wandb_project
            self._entity = wandb_entity or None
            self.enabled = True
            logger.info("WandB enabled. Project: %s", wandb_project)
        except Exception as exc:  # pragma: no cover
            logger.warning("WandB login failed: %s", exc)

    def log_metrics(
        self,
        metrics: dict[str, Any],
        config: dict[str, Any] | None = None,
        run_name: str = "v2ai-eval",
    ) -> None:
        if not self.enabled:
            return
        try:
            with wandb.init(
                project=self._project,
                entity=self._entity,
                name=run_name,
                config=config or {},
                reinit=True,
            ):
                wandb.log(metrics)
        except Exception as exc:  # pragma: no cover
            logger.warning("WandB log_metrics failed: %s", exc)

    def log_pipeline_session(
        self,
        session_id: str,
        session_meta: dict[str, Any],
    ) -> None:
        """Log a processed lecture session as a WandB artifact + metrics."""
        if not self.enabled:
            return
        try:
            with wandb.init(
                project=self._project,
                entity=self._entity,
                name=f"session-{session_id[:8]}",
                config=session_meta,
                reinit=True,
            ):
                wandb.log(
                    {
                        "transcript_word_count": session_meta.get(
                            "transcript_word_count", 0
                        ),
                        "concept_count": len(session_meta.get("concepts", [])),
                        "summary_length": len(session_meta.get("summary", "")),
                        "duration_seconds": session_meta.get("duration_seconds", 0),
                    }
                )
        except Exception as exc:  # pragma: no cover
            logger.warning("WandB log_pipeline_session failed: %s", exc)

    def log_inference_metrics(
        self,
        session_id: str,
        latency_ms: float,
        question_length: int,
        answer_length: int,
        source_count: int,
    ) -> None:
        """Log individual inference call metrics."""
        if not self.enabled:
            return
        try:
            with wandb.init(
                project=self._project,
                entity=self._entity,
                name=f"inference-{session_id[:8]}",
                reinit=True,
            ):
                wandb.log(
                    {
                        "latency_ms": latency_ms,
                        "question_length": question_length,
                        "answer_length": answer_length,
                        "source_count": source_count,
                    }
                )
        except Exception as exc:  # pragma: no cover
            logger.warning("WandB log_inference_metrics failed: %s", exc)
