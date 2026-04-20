from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv optional in constrained environments
    load_dotenv = None


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _resolve_project_path(project_root: Path, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return project_root / path


@dataclass(frozen=True)
class Settings:
    project_name: str
    app_env: str
    hf_generation_model: str
    hf_generation_model_cpu: str
    hf_generation_model_gpu: str
    hf_summary_model: str
    hf_summary_model_cpu: str
    hf_summary_model_gpu: str
    hf_embedding_model: str
    whisper_model_name: str
    whisper_language: str
    knowledge_base_path: Path
    uploads_path: Path
    transcript_store_path: Path
    vector_store_path: Path
    request_log_path: Path
    database_url: str
    mlflow_tracking_uri: str
    mlflow_experiment_name: str
    registered_model_name: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    enable_wandb: bool
    wandb_project: str
    wandb_entity: str
    use_gpu: bool
    retrieval_k: int
    concepts_top_k: int
    generation_max_tokens: int
    generation_temperature: float


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    default_project_root = Path(__file__).resolve().parents[2]
    dotenv_path = default_project_root / ".env"
    if load_dotenv is not None and dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path, override=False)

    project_root = Path(os.getenv("PROJECT_ROOT", str(default_project_root)))

    knowledge_base_path = _resolve_project_path(
        project_root, os.getenv("KNOWLEDGE_BASE_PATH", "data/knowledge")
    )
    uploads_path = _resolve_project_path(
        project_root, os.getenv("UPLOADS_PATH", "artifacts/uploads")
    )
    transcript_store_path = _resolve_project_path(
        project_root,
        os.getenv("TRANSCRIPT_STORE_PATH", "artifacts/transcripts"),
    )
    vector_store_path = _resolve_project_path(
        project_root, os.getenv("VECTOR_STORE_PATH", "artifacts/vectorstore")
    )
    request_log_path = _resolve_project_path(
        project_root, os.getenv("REQUEST_LOG_PATH", "artifacts/monitoring/request_logs.jsonl")
    )
    generation_model_default = os.getenv("HF_GENERATION_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
    generation_model_cpu = os.getenv(
        "HF_GENERATION_MODEL_CPU",
        "Qwen/Qwen2.5-0.5B-Instruct",
    )
    generation_model_gpu = os.getenv(
        "HF_GENERATION_MODEL_GPU",
        generation_model_default,
    )
    summary_model_default = os.getenv("HF_SUMMARY_MODEL", "facebook/bart-large-cnn")
    summary_model_cpu = os.getenv(
        "HF_SUMMARY_MODEL_CPU",
        "sshleifer/distilbart-cnn-12-6",
    )
    summary_model_gpu = os.getenv("HF_SUMMARY_MODEL_GPU", summary_model_default)

    return Settings(
        project_name=os.getenv("PROJECT_NAME", "MLOps-LLMOps-RAG"),
        app_env=os.getenv("APP_ENV", "dev"),
        hf_generation_model=generation_model_default,
        hf_generation_model_cpu=generation_model_cpu,
        hf_generation_model_gpu=generation_model_gpu,
        hf_summary_model=summary_model_default,
        hf_summary_model_cpu=summary_model_cpu,
        hf_summary_model_gpu=summary_model_gpu,
        hf_embedding_model=os.getenv(
            "HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        whisper_model_name=os.getenv("WHISPER_MODEL_NAME", "base"),
        whisper_language=os.getenv("WHISPER_LANGUAGE", "en"),
        knowledge_base_path=knowledge_base_path,
        uploads_path=uploads_path,
        transcript_store_path=transcript_store_path,
        vector_store_path=vector_store_path,
        request_log_path=request_log_path,
        database_url=os.getenv("DATABASE_URL", "sqlite:///artifacts/v2ai.db"),
        mlflow_tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        mlflow_experiment_name=os.getenv(
            "MLFLOW_EXPERIMENT_NAME", "rag_context_flow_experiments"
        ),
        registered_model_name=os.getenv("REGISTERED_MODEL_NAME", "rag-context-model"),
        minio_endpoint=os.getenv("MINIO_ENDPOINT", ""),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", ""),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY", ""),
        minio_bucket=os.getenv("MINIO_BUCKET", "lecture-artifacts"),
        minio_secure=_to_bool(os.getenv("MINIO_SECURE"), default=False),
        enable_wandb=_to_bool(os.getenv("ENABLE_WANDB"), default=False),
        wandb_project=os.getenv("WANDB_PROJECT", "rag-context-flow"),
        wandb_entity=os.getenv("WANDB_ENTITY", ""),
        use_gpu=_to_bool(os.getenv("USE_GPU"), default=False),
        retrieval_k=int(os.getenv("RETRIEVAL_TOP_K", "4")),
        concepts_top_k=int(os.getenv("CONCEPTS_TOP_K", "12")),
        generation_max_tokens=int(os.getenv("GENERATION_MAX_TOKENS", "256")),
        generation_temperature=float(os.getenv("GENERATION_TEMPERATURE", "0.2")),
    )
