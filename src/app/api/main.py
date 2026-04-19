from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.api.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    RebuildIndexResponse,
    SessionResponse,
    UploadVideoResponse,
    UploadVideoUrlRequest,
)
from app.config import load_settings
from app.monitoring.drift_check import run_drift_check
from app.monitoring.request_logger import log_request
from app.tracking.mlflow_tracker import MLflowTracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = load_settings()
tracker = MLflowTracker()

app = FastAPI(
    title=settings.project_name,
    description="V2AI lecture video understanding API with Whisper, LangChain and Hugging Face",
    version="1.0.0",
)

ASK_COUNTER = Counter(
    "v2ai_ask_requests_total",
    "Total number of ask requests handled by the API",
)
UPLOAD_COUNTER = Counter(
    "v2ai_upload_requests_total",
    "Total number of uploaded lecture videos",
)
ASK_LATENCY = Histogram(
    "v2ai_ask_request_latency_seconds",
    "Latency of ask requests in seconds",
)


def _get_video_pipeline_service():
    from app.services.video_pipeline_service import get_video_pipeline_service

    return get_video_pipeline_service()


def _log_and_track(record: dict) -> None:
    log_request(record)
    try:
        tracker.log_inference(record)
    except Exception as exc:  # pragma: no cover - tracking server may be offline
        logger.warning("MLflow logging failed: %s", exc)


@app.middleware("http")
async def prometheus_http_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start

    if request.url.path in {"/ask", "/query"}:
        ASK_LATENCY.observe(elapsed)

    return response


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", environment=settings.app_env)


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/upload-video", response_model=UploadVideoResponse)
async def upload_video(
    file: Annotated[UploadFile, File(...)],
    title: Annotated[str | None, Form()] = None,
) -> UploadVideoResponse:
    UPLOAD_COUNTER.inc()

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing uploaded file name")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        service = _get_video_pipeline_service()
        result = service.create_session(
            filename=file.filename,
            content=content,
            title=title,
        )
    except Exception as exc:  # pragma: no cover - integration path
        logger.exception("Upload pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return UploadVideoResponse(
        session_id=result["session_id"],
        title=result["title"],
        video_filename=result["video_filename"],
        summary=result["summary"],
        concepts=result["concepts"],
        flashcards=result["flashcards"],
        quiz_questions=result["quiz_questions"],
        duration_seconds=result["duration_seconds"],
        transcript_word_count=result["transcript_word_count"],
    )


@app.post("/upload-video-url", response_model=UploadVideoResponse)
def upload_video_url(payload: UploadVideoUrlRequest) -> UploadVideoResponse:
    UPLOAD_COUNTER.inc()

    try:
        service = _get_video_pipeline_service()
        result = service.create_session_from_url(
            video_url=payload.video_url,
            title=payload.title,
        )
    except Exception as exc:  # pragma: no cover - integration path
        logger.exception("URL upload pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return UploadVideoResponse(
        session_id=result["session_id"],
        title=result["title"],
        video_filename=result["video_filename"],
        summary=result["summary"],
        concepts=result["concepts"],
        flashcards=result["flashcards"],
        quiz_questions=result["quiz_questions"],
        duration_seconds=result["duration_seconds"],
        transcript_word_count=result["transcript_word_count"],
    )


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    ASK_COUNTER.inc()

    try:
        service = _get_video_pipeline_service()
        result = service.ask_question(payload.session_id, payload.question)
    except Exception as exc:  # pragma: no cover - integration path
        logger.exception("Ask failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    record = {
        "session_id": result["session_id"],
        "question": result["question"],
        "answer": result["answer"],
        "sources": [
            f"{item['source']} [{item['start_hms']}-{item['end_hms']}]"
            for item in result["citations"]
        ],
        "latency_ms": result["latency_ms"],
        "question_length": result["question_length"],
        "answer_length": result["answer_length"],
        "model_name": result["model_name"],
    }
    _log_and_track(record)

    return AskResponse(
        session_id=result["session_id"],
        answer=result["answer"],
        citations=result["citations"],
        latency_ms=result["latency_ms"],
        model_name=result["model_name"],
    )


@app.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    try:
        service = _get_video_pipeline_service()
        session_id = payload.session_id or service.get_latest_session_id()
        if not session_id:
            raise HTTPException(
                status_code=400,
                detail="No lecture session available. Upload a video first.",
            )
        result = service.ask_question(session_id, payload.question)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        logger.exception("Query alias failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    sources = [
        f"{item['source']} [{item['start_hms']}-{item['end_hms']}]"
        for item in result["citations"]
    ]

    _log_and_track(
        {
            "session_id": result["session_id"],
            "question": result["question"],
            "answer": result["answer"],
            "sources": sources,
            "latency_ms": result["latency_ms"],
            "question_length": result["question_length"],
            "answer_length": result["answer_length"],
            "model_name": result["model_name"],
        }
    )

    return QueryResponse(
        answer=result["answer"],
        sources=sources,
        latency_ms=result["latency_ms"],
        model_name=result["model_name"],
    )


@app.get("/session/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    service = _get_video_pipeline_service()
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(**session)


@app.post("/rebuild-index", response_model=RebuildIndexResponse)
def rebuild_index() -> RebuildIndexResponse:
    return RebuildIndexResponse(
        status="ok",
        detail="Session-specific indexes are built automatically during /upload-video",
    )


@app.get("/model-info")
def model_info() -> dict:
    """Return the currently active model configuration."""
    service = _get_video_pipeline_service()
    active_model = getattr(service, "_active_generation_model_name", "unknown")
    use_gpu = getattr(service.settings, "use_gpu", False)
    return {
        "generation_model": active_model,
        "summary_model": service.settings.hf_summary_model,
        "embedding_model": service.settings.hf_embedding_model,
        "whisper_model": service.settings.whisper_model_name,
        "use_gpu": use_gpu,
        "environment": settings.app_env,
    }


@app.get("/drift-report")
def drift_report() -> dict:
    """Return the latest input distribution drift check result."""
    try:
        return run_drift_check()
    except Exception as exc:  # pragma: no cover
        logger.warning("Drift check failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
