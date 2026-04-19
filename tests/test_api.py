from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import main
from app.api.main import app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"


def test_query_endpoint_uses_service(monkeypatch) -> None:
    class DummyService:
        def get_latest_session_id(self):
            return "session-123"

        def ask_question(self, session_id: str, question: str):
            return {
                "session_id": session_id,
                "question": question,
                "answer": "Dummy answer from test service",
                "citations": [
                    {
                        "source": "lecture.mp4",
                        "start_seconds": 12.0,
                        "end_seconds": 18.5,
                        "start_hms": "00:00:12",
                        "end_hms": "00:00:18",
                        "text": "test citation",
                    }
                ],
                "latency_ms": 12.5,
                "question_length": len(question),
                "answer_length": 30,
                "model_name": "dummy-model",
            }

    monkeypatch.setattr(main, "_get_video_pipeline_service", lambda: DummyService())
    monkeypatch.setattr(main, "log_request", lambda record: None)
    monkeypatch.setattr(main.tracker, "log_inference", lambda record: None)

    client = TestClient(app)
    response = client.post("/query", json={"question": "How does CI work?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"].startswith("Dummy answer")
    assert payload["model_name"] == "dummy-model"


def test_upload_video_url_endpoint_uses_service(monkeypatch) -> None:
    class DummyService:
        def create_session_from_url(self, video_url: str, title: str | None = None):
            return {
                "session_id": "session-url-123",
                "title": title or "Demo Lecture",
                "video_filename": "youtube_demo.mp4",
                "summary": "A concise summary.",
                "concepts": ["neural network", "regularization"],
                "flashcards": [
                    {
                        "question": "What is regularization?",
                        "answer": "A method to reduce overfitting.",
                    }
                ],
                "quiz_questions": [
                    {
                        "question": "Which helps reduce overfitting?",
                        "options": ["dropout", "batching", "caching", "indexing"],
                        "correct_answer": "dropout",
                    }
                ],
                "duration_seconds": 42.0,
                "transcript_word_count": 120,
            }

    monkeypatch.setattr(main, "_get_video_pipeline_service", lambda: DummyService())

    client = TestClient(app)
    response = client.post(
        "/upload-video-url",
        json={
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "title": "YouTube Lecture",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "session-url-123"
    assert payload["video_filename"] == "youtube_demo.mp4"
