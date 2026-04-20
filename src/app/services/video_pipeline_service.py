from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

try:
    import torch
except ImportError:  # pragma: no cover - optional runtime dependency
    torch = None

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
from sentence_transformers import SentenceTransformer
from sqlalchemy import desc, select
from transformers import AutoConfig, AutoModelForCausalLM, AutoModelForSeq2SeqLM, AutoTokenizer, pipeline

from app.config import Settings, load_settings
from app.db.models import LectureSession, QueryLog
from app.db.session import SessionLocal, init_database
from app.storage.minio_store import MinIOArtifactStore
from app.tracking.mlflow_tracker import MLflowTracker

logger = logging.getLogger(__name__)


def _format_seconds(total_seconds: float) -> str:
    value = int(max(total_seconds, 0))
    hours = value // 3600
    minutes = (value % 3600) // 60
    seconds = value % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []

    for value in values:
        normalized = re.sub(r"\s+", " ", value.strip().lower())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    return deduped


def _split_sentences(text: str) -> list[str]:
    if not text.strip():
        return []
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
        if sentence.strip()
    ]


def _sentence_for_concept(text: str, concept: str) -> str:
    concept_tokens = [token for token in concept.lower().split() if token]
    if not concept_tokens:
        return ""

    sentences = _split_sentences(text)
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if all(token in sentence_lower for token in concept_tokens):
            return sentence

    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(token in sentence_lower for token in concept_tokens):
            return sentence

    return ""


def _clean_generated_answer(
    answer: str,
    *,
    max_sentences: int = 6,
    max_chars: int = 900,
) -> str:
    compact = re.sub(r"\s+", " ", answer).strip()
    if not compact:
        return ""

    sentences = _split_sentences(compact)
    if not sentences:
        return compact[:max_chars]

    unique_sentences: list[str] = []
    seen: set[str] = set()
    for sentence in sentences:
        normalized = re.sub(r"\s+", " ", sentence.lower()).strip(" .")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_sentences.append(sentence)
        if len(unique_sentences) >= max_sentences:
            break

    cleaned = " ".join(unique_sentences) if unique_sentences else compact
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:")

    if cleaned and cleaned[-1] not in ".!?":
        cleaned = f"{cleaned}."

    return cleaned


def _extractive_summary(
    text: str,
    *,
    max_sentences: int = 5,
    max_chars: int = 700,
) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return ""

    sentences = _split_sentences(compact)
    if not sentences:
        return compact[:max_chars]

    selected: list[str] = []
    seen: set[str] = set()

    for sentence in sentences:
        normalized = re.sub(r"\s+", " ", sentence.lower()).strip(" .")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        selected.append(sentence)
        if len(selected) >= max_sentences:
            break

    summary = " ".join(selected).strip() if selected else compact
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:")
    if summary and summary[-1] not in ".!?":
        summary = f"{summary}."

    return summary


def _is_supported_video_url(url: str) -> bool:
    return bool(
        re.match(
            r"^https?://((www|m)\.)?(youtube\.com|youtu\.be)/",
            url.strip(),
            flags=re.IGNORECASE,
        )
    )


def _simple_keywords(text: str, top_k: int) -> list[str]:
    prioritized_phrases = [
        "neural network",
        "activation function",
        "back propagation",
        "learning rate",
        "loss function",
        "training data",
        "validation",
        "dropout",
        "regularization",
        "overfitting",
    ]
    stop_words = {
        "the",
        "and",
        "for",
        "that",
        "with",
        "this",
        "from",
        "have",
        "are",
        "was",
        "were",
        "your",
        "into",
        "their",
        "about",
        "then",
        "than",
        "they",
        "them",
        "will",
        "there",
        "what",
        "when",
        "where",
        "which",
        "whose",
        "while",
        "using",
        "model",
        "models",
        "lecture",
        "short",
        "these",
        "those",
        "learn",
        "learns",
        "learning",
        "make",
        "makes",
        "made",
        "need",
        "needs",
        "used",
    }

    tokens = [token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", text)]
    if not tokens:
        return []

    candidates: list[str] = []
    normalized_text = " ".join(tokens)
    for phrase in prioritized_phrases:
        if phrase in normalized_text:
            candidates.append(phrase)

    cleaned: list[str] = []
    for token in tokens:
        normalized = token.strip("-")
        if normalized.endswith("ies") and len(normalized) > 5:
            normalized = f"{normalized[:-3]}y"
        elif normalized.endswith("s") and len(normalized) > 5 and not normalized.endswith("ss"):
            normalized = normalized[:-1]

        if len(normalized) < 4 or normalized in stop_words:
            continue
        cleaned.append(normalized)

    counts: dict[str, int] = {}
    for token in cleaned:
        counts[token] = counts.get(token, 0) + 1

    bigram_counts: dict[str, int] = {}
    for left, right in zip(cleaned, cleaned[1:], strict=False):
        if left == right:
            continue
        phrase = f"{left} {right}"
        bigram_counts[phrase] = bigram_counts.get(phrase, 0) + 1

    ranked_bigrams = sorted(
        bigram_counts.items(),
        key=lambda item: (item[1], len(item[0])),
        reverse=True,
    )
    ranked_unigrams = sorted(
        counts.items(),
        key=lambda item: (item[1], len(item[0])),
        reverse=True,
    )

    for phrase, _ in ranked_bigrams:
        if len(candidates) >= top_k:
            break
        candidates.append(phrase)

    for term, _ in ranked_unigrams:
        if len(candidates) >= top_k:
            break
        candidates.append(term)

    return _dedupe_preserving_order(candidates)[:top_k]


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    try:
        loaded = json.loads(raw_text)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            loaded = json.loads(raw_text[start : end + 1])
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}


@lru_cache(maxsize=1)
def _ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg"):
        return

    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except ImportError as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError(
            "FFmpeg is required for transcription. Install FFmpeg or install imageio-ffmpeg."
        ) from exc

    ffmpeg_exe = Path(get_ffmpeg_exe()).resolve()
    if not ffmpeg_exe.exists():
        raise RuntimeError(f"FFmpeg executable not found at expected path: {ffmpeg_exe}")

    # Whisper calls `ffmpeg` by name. Create a local shim and prepend it to PATH.
    shim_dir = Path(__file__).resolve().parents[3] / "artifacts" / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim_path = shim_dir / "ffmpeg.exe"

    if not shim_path.exists():
        shutil.copy2(ffmpeg_exe, shim_path)

    current_path = os.getenv("PATH", "")
    entries = current_path.split(os.pathsep) if current_path else []
    shim_dir_str = str(shim_dir)

    if shim_dir_str not in entries:
        os.environ["PATH"] = (
            f"{shim_dir_str}{os.pathsep}{current_path}" if current_path else shim_dir_str
        )

    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "FFmpeg setup failed. Ensure ffmpeg is installed or available via imageio-ffmpeg."
        )


@lru_cache(maxsize=1)
def _build_whisper_model(model_name: str, use_gpu: bool):
    try:
        import whisper
    except ImportError as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError(
            "openai-whisper package is required for video transcription"
        ) from exc

    device = "cuda" if use_gpu and torch is not None and torch.cuda.is_available() else "cpu"
    return whisper.load_model(model_name, device=device)


@lru_cache(maxsize=1)
def _build_sentence_transformer(model_name: str, use_gpu: bool):
    device = "cuda" if use_gpu and torch is not None and torch.cuda.is_available() else "cpu"
    return SentenceTransformer(model_name, device=device)


@lru_cache(maxsize=1)
def _build_summarizer_pipeline(model_name: str, use_gpu: bool):
    return pipeline(
        task="summarization",
        model=model_name,
        device=0 if use_gpu else -1,
    )


class V2AIPipelineService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self._ensure_paths()
        init_database()
        
        self.tracker = MLflowTracker()

        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.settings.hf_embedding_model,
            model_kwargs={"device": "cuda" if self._use_cuda() else "cpu"},
        )
        self._active_generation_model_name = ""
        self._disable_neural_generation = False
        self.llm = self._build_generation_llm()
        self._disable_neural_summarizer = False
        self.minio_store = MinIOArtifactStore()

    def _use_cuda(self) -> bool:
        return bool(
            self.settings.use_gpu and torch is not None and torch.cuda.is_available()
        )

    def _ensure_paths(self) -> None:
        self.settings.uploads_path.mkdir(parents=True, exist_ok=True)
        self.settings.transcript_store_path.mkdir(parents=True, exist_ok=True)
        self.settings.vector_store_path.mkdir(parents=True, exist_ok=True)

    def _get_generation_model_candidates(self) -> list[str]:
        preferred = (
            self.settings.hf_generation_model_gpu
            if self._use_cuda()
            else self.settings.hf_generation_model_cpu
        )
        candidates = [
            preferred,
            self.settings.hf_generation_model,
            "Qwen/Qwen2.5-0.5B-Instruct",
        ]

        return _dedupe_preserving_order(candidates)

    def _build_generation_llm(self) -> HuggingFacePipeline | None:
        last_error: Exception | None = None
        for model_name in self._get_generation_model_candidates():
            try:
                tokenizer = AutoTokenizer.from_pretrained(model_name)
                config = AutoConfig.from_pretrained(model_name)
                
                if getattr(config, "is_encoder_decoder", False):
                    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
                    task = "text2text-generation"
                else:
                    model = AutoModelForCausalLM.from_pretrained(
                        model_name, 
                        torch_dtype=torch.float16 if self._use_cuda() else torch.float32
                    )
                    task = "text-generation"

                generator = pipeline(
                    task=task,
                    model=model,
                    tokenizer=tokenizer,
                    device=0 if self._use_cuda() else -1,
                    max_new_tokens=min(self.settings.generation_max_tokens, 1500),  # Increased for massive JSON context
                    temperature=self.settings.generation_temperature,
                    do_sample=False,
                    repetition_penalty=1.1,
                    return_full_text=False,
                )

                self._active_generation_model_name = model_name
                self._disable_neural_generation = False
                return HuggingFacePipeline(pipeline=generator)
            except Exception as exc:  # pragma: no cover - model loading path
                last_error = exc
                logger.warning(
                    "Failed to load generation model '%s'. Trying next fallback: %s",
                    model_name,
                    exc,
                )

        self._disable_neural_generation = True
        self._active_generation_model_name = "extractive-fallback"
        logger.warning(
            "Neural generation disabled for this process. "
            "Falling back to extractive response generation. Last error: %s",
            last_error,
        )
        return None

    def _transcribe(self, video_path: Path) -> dict[str, Any]:
        _ensure_ffmpeg_available()

        model = _build_whisper_model(
            self.settings.whisper_model_name,
            self._use_cuda(),
        )

        result = model.transcribe(
            str(video_path),
            language=self.settings.whisper_language or None,
            task="transcribe",
            verbose=False,
        )

        segments = result.get("segments", [])
        transcript_text = " ".join(
            str(segment.get("text", "")).strip()
            for segment in segments
            if str(segment.get("text", "")).strip()
        ).strip()

        if not transcript_text:
            raise RuntimeError("Whisper returned an empty transcript")

        return {
            "text": transcript_text,
            "segments": segments,
            "language": result.get("language", "unknown"),
        }

    def _get_summary_model_name(self) -> str:
        if self._use_cuda():
            return self.settings.hf_summary_model_gpu
        return self.settings.hf_summary_model_cpu

    def _get_summarizer(self):
        if self._disable_neural_summarizer:
            return None

        summary_model_name = self._get_summary_model_name()

        try:
            return _build_summarizer_pipeline(
                summary_model_name,
                self._use_cuda(),
            )
        except Exception as exc:  # pragma: no cover - model loading path
            self._disable_neural_summarizer = True
            logger.warning(
                "Failed to load summarization model '%s'. "
                "Falling back to extractive summary for this process: %s",
                summary_model_name,
                exc,
            )
            return None

    def _summarize_transcript(self, transcript_text: str) -> str:
        if len(transcript_text.split()) < 40:
            return transcript_text

        summarizer = self._get_summarizer()
        if summarizer is None:
            return _extractive_summary(transcript_text)

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=2200,
            chunk_overlap=250,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks = splitter.split_text(transcript_text)
        if not chunks:
            return transcript_text

        partial_summaries: list[str] = []
        for chunk in chunks[:8]:
            if self._disable_neural_summarizer:
                partial_summaries.append(
                    _extractive_summary(chunk, max_sentences=2, max_chars=220)
                )
                continue

            chunk_word_count = max(len(chunk.split()), 1)
            max_length = min(140, max(60, int(chunk_word_count * 0.7)))
            min_length = min(45, max(25, int(max_length * 0.45)))
            if min_length >= max_length:
                min_length = max(20, max_length - 20)

            try:
                summary_part = summarizer(
                    chunk,
                    max_length=max_length,
                    min_length=min_length,
                    do_sample=False,
                )[0]["summary_text"]
            except Exception as exc:  # pragma: no cover - runtime model path
                self._disable_neural_summarizer = True
                logger.warning(
                    "Neural summarization failed during chunking. "
                    "Using extractive fallback: %s",
                    exc,
                )
                summary_part = _extractive_summary(
                    chunk,
                    max_sentences=2,
                    max_chars=220,
                )
            partial_summaries.append(summary_part)

        merged = " ".join(partial_summaries)
        if len(partial_summaries) > 1:
            if self._disable_neural_summarizer:
                merged = _extractive_summary(merged, max_sentences=4, max_chars=500)
            else:
                merged_word_count = max(len(merged.split()), 1)
                merged_max_length = min(170, max(70, int(merged_word_count * 0.65)))
                merged_min_length = min(60, max(30, int(merged_max_length * 0.45)))
                if merged_min_length >= merged_max_length:
                    merged_min_length = max(25, merged_max_length - 25)

                try:
                    merged = summarizer(
                        merged,
                        max_length=merged_max_length,
                        min_length=merged_min_length,
                        do_sample=False,
                    )[0]["summary_text"]
                except Exception as exc:  # pragma: no cover - runtime model path
                    self._disable_neural_summarizer = True
                    logger.warning(
                        "Neural summarization failed during merge. "
                        "Using extractive fallback: %s",
                        exc,
                    )
                    merged = _extractive_summary(
                        merged,
                        max_sentences=4,
                        max_chars=500,
                    )

        return _extractive_summary(merged, max_sentences=5, max_chars=700)

    def _extract_concepts(self, transcript_text: str) -> list[str]:
        candidates = _simple_keywords(transcript_text, top_k=40)
        if not candidates:
            return []

        try:
            concept_model = _build_sentence_transformer(
                self.settings.hf_embedding_model,
                self._use_cuda(),
            )
            document_embedding = concept_model.encode(
                [transcript_text[:12000]],
                normalize_embeddings=True,
            )[0]
            candidate_embeddings = concept_model.encode(
                candidates,
                normalize_embeddings=True,
            )
            scores = np.dot(candidate_embeddings, document_embedding)
            ranked_indexes = np.argsort(scores)[::-1]

            ranked = [candidates[index] for index in ranked_indexes]
            return _dedupe_preserving_order(ranked)[: self.settings.concepts_top_k]
        except Exception as exc:  # pragma: no cover - embedding fallback path
            logger.warning("Sentence-BERT keyword extraction fallback: %s", exc)
            return _dedupe_preserving_order(candidates)[: self.settings.concepts_top_k]

    def _fallback_study_materials(
        self,
        transcript_text: str,
        summary_text: str,
        concepts: list[str],
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        selected = concepts[:6] if concepts else _simple_keywords(transcript_text, top_k=6)
        if not selected:
            selected = [
                "neural network",
                "training",
                "learning rate",
                "loss function",
                "overfitting",
                "regularization",
            ]

        flashcards: list[dict[str, str]] = []
        for concept in selected[:5]:
            support_sentence = _sentence_for_concept(transcript_text, concept)
            answer_text = support_sentence or summary_text
            answer_text = re.sub(r"\s+", " ", answer_text).strip()
            if len(answer_text) > 260:
                answer_text = answer_text[:260].rsplit(" ", 1)[0].rstrip(" ,;:")
            if answer_text and answer_text[-1] not in ".!?":
                answer_text = f"{answer_text}."

            flashcards.append(
                {
                    "question": f"What does the lecture explain about {concept}?",
                    "answer": answer_text or f"{concept} is discussed in the lecture.",
                }
            )

        extra_distractors = [
            "feature engineering",
            "data preprocessing",
            "inference latency",
            "model deployment",
        ]

        quiz_questions: list[dict[str, Any]] = []
        for index, concept in enumerate(selected[:3]):
            support_sentence = _sentence_for_concept(transcript_text, concept) or summary_text
            clue = re.sub(r"\s+", " ", support_sentence).strip()
            if len(clue) > 140:
                clue = clue[:140].rsplit(" ", 1)[0].rstrip(" ,;:")
            if clue and clue[-1] not in ".!?":
                clue = f"{clue}."

            distractors = [item for item in selected if item != concept][:3]
            for distractor in extra_distractors:
                if len(distractors) >= 3:
                    break
                if distractor != concept and distractor not in distractors:
                    distractors.append(distractor)

            while len(distractors) < 3:
                distractors.append(f"option {len(distractors) + 1}")
            options = distractors + [concept]
            rotation = index % len(options)
            options = options[rotation:] + options[:rotation]

            quiz_questions.append(
                {
                    "question": f"Which concept best matches this statement: {clue}",
                    "options": options,
                    "correct_answer": concept,
                }
            )

        return flashcards, quiz_questions

    def _fallback_answer_from_docs(
        self,
        question: str,
        docs: list[Document],
    ) -> str:
        merged = " ".join(doc.page_content for doc in docs if doc.page_content).strip()
        if not merged:
            return "I cannot find this in the lecture transcript."

        question_tokens = [
            token.lower()
            for token in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", question)
            if len(token) >= 4
        ]
        selected_sentences: list[str] = []
        seen: set[str] = set()

        for sentence in _split_sentences(merged):
            normalized = sentence.lower()
            if question_tokens and not any(token in normalized for token in question_tokens):
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            selected_sentences.append(sentence)
            if len(selected_sentences) >= 5:
                break

        source_text = " ".join(selected_sentences) if selected_sentences else merged
        answer = _extractive_summary(source_text, max_sentences=4, max_chars=750)
        self.tracker.start_run("inference")
        return answer or "I cannot find this in the lecture transcript."

    def _generate_study_materials(
        self,
        transcript_text: str,
        summary_text: str,
        concepts: list[str],
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        if self._disable_neural_generation or self.llm is None:
            return self._fallback_study_materials(transcript_text, summary_text, concepts)

        prompt = PromptTemplate.from_template(
            """
You are a rigorous university professor. Your task is to generate deeply conceptual, highly difficult study materials from the provided lecture transcript chunk.
The questions MUST require deep synthesis of the concepts, not mere definitions. They should be at the level of a graduate exam.
Do NOT ask basic "What is X?" questions. Instead, ask "Why is X preferred over Y in this scenario?" or "How does X affect the outcome of Y?".
For multiple-choice questions, provide exactly one correct answer and three highly plausible but tricky distractors.

You must reply with strictly valid JSON matching this schema exactly, and nothing else.
{{
    "flashcards": [
        {{"question": "Deep conceptual question 1?", "answer": "Detailed, thorough answer explaining the concept."}},
        {{"question": "Deep conceptual question 2?", "answer": "Detailed, thorough answer explaining the concept."}}
    ],
    "quiz_questions": [
        {{
            "question": "Challenging multiple choice question 1?",
            "options": ["Plausible Distractor A", "Plausible Distractor B", "Plausible Distractor C", "Correct Answer"],
            "correct_answer": "Correct Answer"
        }}
    ]
}}

Requirements:
- Generate exactly 3 flashcards from this specific chunk.
- Generate exactly 2 multiple-choice quiz questions from this specific chunk.

Summary of overall lecture:
{summary}

Concepts to focus on:
{concepts}

Transcript Chunk to analyze:
{transcript_excerpt}
""".strip()
        )

        chain = prompt | self.llm | StrOutputParser()

        words = transcript_text.split()
        chunk_size = max(len(words) // 3, 1)
        chunks = [
            " ".join(words[i : i + chunk_size])
            for i in range(0, len(words), chunk_size)
        ][:3]

        all_flashcards: list[dict[str, str]] = []
        all_quiz_questions: list[dict[str, Any]] = []
        last_error = ""

        for chunk in chunks:
            try:
                raw = str(
                    chain.invoke(
                        {
                            "summary": summary_text,
                            "concepts": ", ".join(concepts),
                            "transcript_excerpt": chunk[:5000],
                        }
                    )
                ).strip()
                payload = _extract_json_object(raw)
                
                for item in payload.get("flashcards", []):
                    question = str(item.get("question", "")).strip()
                    answer = str(item.get("answer", "")).strip()
                    if question and answer:
                        all_flashcards.append({"question": question, "answer": answer})

                for item in payload.get("quiz_questions", []):
                    question = str(item.get("question", "")).strip()
                    options = [str(opt).strip() for opt in item.get("options", []) if str(opt).strip()]
                    correct = str(item.get("correct_answer", "")).strip()

                    if not question or not correct:
                        continue
                    if correct not in options:
                        options = options[:3] + [correct]
                    if len(options) >= 2:
                        all_quiz_questions.append({
                            "question": question,
                            "options": options[:4],
                            "correct_answer": correct,
                        })

            except Exception as exc:
                logger.warning("Chunk generation failed: %s", exc)
                last_error = str(exc)
                continue

        if not all_flashcards and not all_quiz_questions:
            return [{"question": "LLM Parsing Failed", "answer": f"Generation Error: {last_error}"}], []

        # Deduplicate flashcards by exact question match
        unique_flashcards = []
        seen_q = set()
        for f in all_flashcards:
            q = f["question"].lower()
            if q not in seen_q:
                seen_q.add(q)
                unique_flashcards.append(f)

        return unique_flashcards[:10], all_quiz_questions[:5]

    def _segments_to_documents(
        self,
        segments: list[dict[str, Any]],
        source_name: str,
    ) -> list[Document]:
        docs: list[Document] = []
        current_text: list[str] = []
        current_start = 0.0
        current_end = 0.0

        for segment in segments:
            text = str(segment.get("text", "")).strip()
            if not text:
                continue

            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", start))

            if not current_text:
                current_start = start
            current_text.append(text)
            current_end = end

            joined = " ".join(current_text)
            if len(joined) >= 360:
                docs.append(
                    Document(
                        page_content=joined,
                        metadata={
                            "source": source_name,
                            "start_seconds": current_start,
                            "end_seconds": current_end,
                            "start_hms": _format_seconds(current_start),
                            "end_hms": _format_seconds(current_end),
                        },
                    )
                )
                current_text = []

        if current_text:
            joined = " ".join(current_text)
            docs.append(
                Document(
                    page_content=joined,
                    metadata={
                        "source": source_name,
                        "start_seconds": current_start,
                        "end_seconds": current_end,
                        "start_hms": _format_seconds(current_start),
                        "end_hms": _format_seconds(current_end),
                    },
                )
            )

        if not docs:
            raise RuntimeError("Unable to build transcript chunks for retrieval")

        return docs

    def _build_vector_index(
        self,
        session_id: str,
        segments: list[dict[str, Any]],
        source_name: str,
    ) -> None:
        docs = self._segments_to_documents(segments, source_name)
        vector_store = FAISS.from_documents(docs, self.embeddings)

        session_index_path = self.settings.vector_store_path / session_id
        session_index_path.mkdir(parents=True, exist_ok=True)
        vector_store.save_local(str(session_index_path))

    def _save_local_video(self, filename: str, data: bytes, session_id: str) -> Path:
        sanitized_name = Path(filename).name
        local_path = self.settings.uploads_path / f"{session_id}_{sanitized_name}"
        local_path.write_bytes(data)
        return local_path

    def _download_video_from_url(self, video_url: str) -> tuple[Path, str]:
        if not _is_supported_video_url(video_url):
            raise ValueError(
                "Only YouTube URLs are supported in this input mode. "
                "Please provide a youtube.com or youtu.be link."
            )

        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError(
                "yt-dlp is required for URL ingestion. Install it with `pip install yt-dlp`."
            ) from exc

        _ensure_ffmpeg_available()
        ffmpeg_path = shutil.which("ffmpeg")

        download_id = str(uuid.uuid4())
        output_template = self.settings.uploads_path / f"{download_id}_youtube.%(ext)s"
        ydl_opts: dict[str, Any] = {
            "outtmpl": str(output_template),
            "noplaylist": True,
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "restrictfilenames": True,
            "quiet": True,
            "no_warnings": True,
            "extractor_args": {"youtube": ["player_client=android,web"]},
        }
        
        cookie_path = Path("/app/cookies.txt")
        if cookie_path.exists():
            ydl_opts["cookiefile"] = str(cookie_path)
            
        if ffmpeg_path:
            ydl_opts["ffmpeg_location"] = ffmpeg_path

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)

            if isinstance(info, dict) and info.get("entries"):
                entries = [entry for entry in info.get("entries", []) if entry]
                info = entries[0] if entries else {}

            if not isinstance(info, dict) or not info:
                raise RuntimeError("Unable to extract download metadata from the provided URL")

            video_title = str(info.get("title", "YouTube Lecture")).strip()
            requested_downloads = info.get("requested_downloads") or []

            downloaded_path_str = ""
            if requested_downloads and isinstance(requested_downloads, list):
                first_item = requested_downloads[0] or {}
                if isinstance(first_item, dict):
                    downloaded_path_str = str(first_item.get("filepath", "")).strip()

            if not downloaded_path_str:
                downloaded_path_str = str(info.get("_filename", "")).strip()
            if not downloaded_path_str:
                downloaded_path_str = str(ydl.prepare_filename(info)).strip()

        downloaded_path = Path(downloaded_path_str)
        if not downloaded_path.is_absolute():
            downloaded_path = (Path.cwd() / downloaded_path).resolve()

        if not downloaded_path.exists():
            raise RuntimeError("YouTube download completed but output file was not found")

        return downloaded_path, video_title

    def _persist_session(
        self,
        session_id: str,
        title: str,
        video_filename: str,
        video_path: Path,
        transcript_text: str,
        summary_text: str,
        concepts: list[str],
        flashcards: list[dict[str, str]],
        quiz_questions: list[dict[str, Any]],
        duration_seconds: float,
        metadata_json: dict[str, Any],
    ) -> None:
        with SessionLocal() as db:
            record = LectureSession(
                id=session_id,
                title=title,
                video_filename=video_filename,
                video_path=str(video_path.as_posix()),
                transcript_text=transcript_text,
                summary_text=summary_text,
                concepts=concepts,
                flashcards=flashcards,
                quiz_questions=quiz_questions,
                duration_seconds=duration_seconds,
                transcript_word_count=len(transcript_text.split()),
                metadata_json=metadata_json,
            )
            db.add(record)
            db.commit()

    def create_session(
        self,
        filename: str,
        content: bytes,
        title: str | None = None,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        if not content:
            raise ValueError("Uploaded file is empty")

        session_id = str(uuid.uuid4())
        session_title = (title or Path(filename).stem or "Lecture Session").strip()

        local_video_path = self._save_local_video(filename, content, session_id)
        transcription = self._transcribe(local_video_path)

        transcript_text = transcription["text"]
        segments = transcription["segments"]
        summary_text = self._summarize_transcript(transcript_text)
        concepts = self._extract_concepts(transcript_text)
        flashcards, quiz_questions = self._generate_study_materials(
            transcript_text=transcript_text,
            summary_text=summary_text,
            concepts=concepts,
        )

        self._build_vector_index(session_id, segments, source_name=Path(filename).name)

        duration_seconds = 0.0
        if segments:
            duration_seconds = float(segments[-1].get("end", 0.0))

        video_sha256 = hashlib.sha256(content).hexdigest()

        metadata = {
            "session_id": session_id,
            "video_filename": filename,
            "language": transcription["language"],
            "duration_seconds": duration_seconds,
            "segment_count": len(segments),
            "video_size_bytes": len(content),
            "video_sha256": video_sha256,
        }
        if source_url:
            metadata["source_url"] = source_url

        transcript_payload = {
            "metadata": metadata,
            "summary": summary_text,
            "concepts": concepts,
            "flashcards": flashcards,
            "quiz_questions": quiz_questions,
            "segments": segments,
        }
        transcript_path = self.settings.transcript_store_path / f"{session_id}.json"
        transcript_path.write_text(json.dumps(transcript_payload, indent=2), encoding="utf-8")

        try:
            self.minio_store.upload_file(
                local_video_path,
                f"sessions/{session_id}/video/{Path(filename).name}",
            )
            self.minio_store.upload_file(
                transcript_path,
                f"sessions/{session_id}/transcript/{session_id}.json",
            )
        except Exception as exc:  # pragma: no cover - external service path
            logger.warning("MinIO upload skipped: %s", exc)

        self._persist_session(
            session_id=session_id,
            title=session_title,
            video_filename=Path(filename).name,
            video_path=local_video_path,
            transcript_text=transcript_text,
            summary_text=summary_text,
            concepts=concepts,
            flashcards=flashcards,
            quiz_questions=quiz_questions,
            duration_seconds=duration_seconds,
            metadata_json=metadata,
        )

        self.tracker.log_pipeline_session(
            session_id=session_id,
            transcription_meta={"duration_seconds": duration_seconds, "segment_count": len(segments), "language": metadata.get("language")},
            summarization_meta={"summary_length": len(summary_text)},
            indexing_meta={"vector_store_chunks": len(segments)},
            model_params={"generation_model": self._active_generation_model_name}
        )

        return {
            "session_id": session_id,
            "title": session_title,
            "video_filename": Path(filename).name,
            "summary": summary_text,
            "concepts": concepts,
            "flashcards": flashcards,
            "quiz_questions": quiz_questions,
            "duration_seconds": round(duration_seconds, 2),
            "transcript_word_count": len(transcript_text.split()),
            "metadata": metadata,
        }

    def create_session_from_url(
        self,
        video_url: str,
        title: str | None = None,
    ) -> dict[str, Any]:
        cleaned_url = video_url.strip()
        if not cleaned_url:
            raise ValueError("Video URL is required")

        downloaded_path, inferred_title = self._download_video_from_url(cleaned_url)

        try:
            content = downloaded_path.read_bytes()
            final_title = (title or inferred_title or downloaded_path.stem).strip()
            return self.create_session(
                filename=downloaded_path.name,
                content=content,
                title=final_title,
                source_url=cleaned_url,
            )
        finally:
            downloaded_path.unlink(missing_ok=True)

    def _load_vector_store(self, session_id: str) -> FAISS:
        index_dir = self.settings.vector_store_path / session_id
        index_file = index_dir / "index.faiss"
        if not index_file.exists():
            raise FileNotFoundError(f"No vector index found for session_id={session_id}")

        return FAISS.load_local(
            folder_path=str(index_dir),
            embeddings=self.embeddings,
            allow_dangerous_deserialization=True,
        )

    def ask_question(self, session_id: str, question: str) -> dict[str, Any]:
        start_time = time.perf_counter()

        vector_store = self._load_vector_store(session_id)
        retriever = vector_store.as_retriever(search_kwargs={"k": self.settings.retrieval_k})
        docs = retriever.invoke(question)

        if not docs:
            raise RuntimeError("No context retrieved for this question")

        context_blocks = []
        for doc in docs:
            start_hms = doc.metadata.get("start_hms", "00:00:00")
            end_hms = doc.metadata.get("end_hms", "00:00:00")
            context_blocks.append(f"[{start_hms}-{end_hms}] {doc.page_content}")
        context = "\n\n".join(context_blocks)

        prompt = PromptTemplate.from_template(
            """
You are a lecture understanding assistant.
Use only the transcript context to answer the question.
Answer in 3 to 5 concise sentences.
Avoid repeating the same sentence.
If the context does not contain the answer, say: "I cannot find this in the lecture transcript.".

Transcript Context:
{context}

Question:
{question}

Answer:
""".strip()
        )

        if self._disable_neural_generation or self.llm is None:
            answer = self._fallback_answer_from_docs(question, docs)
        else:
            chain = prompt | self.llm | StrOutputParser()
            raw_answer = str(chain.invoke({"context": context, "question": question})).strip()
            answer = _clean_generated_answer(raw_answer)
            if not answer:
                answer = "I cannot find this in the lecture transcript."

        citations: list[dict[str, Any]] = []
        seen = set()
        for doc in docs:
            key = (
                doc.metadata.get("start_seconds", 0.0),
                doc.metadata.get("end_seconds", 0.0),
                doc.page_content[:80],
            )
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                {
                    "source": str(doc.metadata.get("source", "unknown")),
                    "start_seconds": float(doc.metadata.get("start_seconds", 0.0)),
                    "end_seconds": float(doc.metadata.get("end_seconds", 0.0)),
                    "start_hms": str(doc.metadata.get("start_hms", "00:00:00")),
                    "end_hms": str(doc.metadata.get("end_hms", "00:00:00")),
                    "text": doc.page_content,
                }
            )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        with SessionLocal() as db:
            record = QueryLog(
                session_id=session_id,
                question=question,
                answer=answer,
                latency_ms=latency_ms,
                citations=citations,
            )
            db.add(record)
            db.commit()

        return {
            "session_id": session_id,
            "question": question,
            "answer": answer,
            "citations": citations,
            "latency_ms": round(latency_ms, 2),
            "question_length": len(question),
            "answer_length": len(answer),
            "model_name": self._active_generation_model_name or self.settings.hf_generation_model,
        }

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.get(LectureSession, session_id)
            if row is None:
                return None

            return {
                "session_id": row.id,
                "title": row.title,
                "video_filename": row.video_filename,
                "video_path": row.video_path,
                "summary": row.summary_text,
                "concepts": row.concepts,
                "flashcards": row.flashcards,
                "quiz_questions": row.quiz_questions,
                "duration_seconds": row.duration_seconds,
                "transcript_word_count": row.transcript_word_count,
                "created_at": str(row.created_at),
                "metadata": row.metadata_json,
            }

    def _delete_session_artifacts(self, session_id: str) -> None:
        for video in self.settings.uploads_path.glob(f"{session_id}_*"):
            if video.is_file():
                video.unlink(missing_ok=True)

        transcript = self.settings.transcript_store_path / f"{session_id}.json"
        if transcript.exists():
            transcript.unlink(missing_ok=True)

        vector_dir = self.settings.vector_store_path / session_id
        if vector_dir.exists() and vector_dir.is_dir():
            shutil.rmtree(vector_dir, ignore_errors=True)

    def cleanup_old_sessions(self, retention_days: int = 30) -> dict[str, Any]:
        if retention_days < 1:
            raise ValueError("retention_days must be >= 1")

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        removed_session_ids: list[str] = []

        with SessionLocal() as db:
            stmt = select(LectureSession).where(LectureSession.created_at < cutoff)
            sessions = db.scalars(stmt).all()

            for row in sessions:
                removed_session_ids.append(row.id)
                db.delete(row)

            db.commit()

        for session_id in removed_session_ids:
            self._delete_session_artifacts(session_id)

        return {
            "retention_days": retention_days,
            "removed_count": len(removed_session_ids),
            "removed_session_ids": removed_session_ids,
        }

    def get_latest_session_id(self) -> str | None:
        with SessionLocal() as db:
            stmt = select(LectureSession.id).order_by(desc(LectureSession.created_at)).limit(1)
            session_id = db.scalar(stmt)
            return session_id


@lru_cache(maxsize=1)
def get_video_pipeline_service() -> V2AIPipelineService:
    return V2AIPipelineService(settings=load_settings())
