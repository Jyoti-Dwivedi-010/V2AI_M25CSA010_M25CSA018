from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    session_id: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    latency_ms: float
    model_name: str


class Citation(BaseModel):
    source: str
    start_seconds: float
    end_seconds: float
    start_hms: str
    end_hms: str
    text: str


class AskRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    question: str = Field(min_length=3, max_length=2000)


class AskResponse(BaseModel):
    session_id: str
    answer: str
    citations: list[Citation]
    latency_ms: float
    model_name: str


class Flashcard(BaseModel):
    question: str
    answer: str


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_answer: str

class UploadVideoUrlRequest(BaseModel):
    video_url: str = Field(min_length=10, max_length=2000)
    title: str | None = Field(default=None, max_length=200)


class UploadVideoResponse(BaseModel):
    session_id: str
    title: str
    video_filename: str
    summary: str
    concepts: list[str]
    flashcards: list[Flashcard]
    quiz_questions: list[QuizQuestion]
    duration_seconds: float
    transcript_word_count: int


class SessionResponse(BaseModel):
    session_id: str
    title: str
    video_filename: str
    video_path: str
    summary: str
    concepts: list[str]
    flashcards: list[Flashcard]
    quiz_questions: list[QuizQuestion]
    duration_seconds: float
    transcript_word_count: int
    created_at: str
    metadata: dict


class HealthResponse(BaseModel):
    status: str
    environment: str


class RebuildIndexResponse(BaseModel):
    status: str
    detail: str
