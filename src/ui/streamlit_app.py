"""
streamlit_app.py — V2AI Lecture Video Understanding Studio
Enhanced UI with dark glassmorphism theme, animations, and full pipeline visibility.
"""
from __future__ import annotations

import os
import time
from typing import Any

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="V2AI · Lecture Intelligence Studio",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS — dark glassmorphism theme
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Base ───────────────────────────────────────────────── */
:root {
  --bg:       #080d1a;
  --bg2:      #0d1427;
  --glass:    rgba(255,255,255,0.05);
  --glass-b:  rgba(255,255,255,0.10);
  --border:   rgba(99,179,237,0.18);
  --accent:   #4f8ef7;
  --accent2:  #8b5cf6;
  --accent3:  #10b981;
  --gold:     #f59e0b;
  --danger:   #ef4444;
  --text:     #e2e8f0;
  --text-dim: #94a3b8;
  --mono:     'JetBrains Mono', monospace;
}

html, body, [data-testid="stAppViewContainer"] {
  font-family: 'Inter', sans-serif !important;
  background: radial-gradient(ellipse 80% 50% at 50% -20%, rgba(79,142,247,0.15) 0%, transparent 60%),
              radial-gradient(ellipse 60% 40% at 80% 80%, rgba(139,92,246,0.10) 0%, transparent 55%),
              var(--bg) !important;
  color: var(--text) !important;
}

[data-testid="stAppViewContainer"] > .main { background: transparent !important; }

/* ── Sidebar ────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0a1020 0%, #080d1a 100%) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }
[data-testid="stSidebar"] .stMarkdown h3 {
  font-size: 0.78rem !important;
  letter-spacing: 0.12em !important;
  text-transform: uppercase !important;
  color: var(--text-dim) !important;
  margin: 1.2rem 0 0.4rem !important;
}

/* ── Glass cards ────────────────────────────────────────── */
.v-card {
  background: var(--glass);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 1.4rem 1.6rem;
  margin-bottom: 1rem;
  transition: box-shadow 0.25s ease, border-color 0.25s ease;
}
.v-card:hover {
  box-shadow: 0 0 28px rgba(79,142,247,0.12);
  border-color: rgba(79,142,247,0.32);
}

/* ── Hero banner ────────────────────────────────────────── */
.hero-banner {
  background: linear-gradient(135deg, rgba(79,142,247,0.18) 0%, rgba(139,92,246,0.14) 100%);
  border: 1px solid rgba(79,142,247,0.28);
  border-radius: 20px;
  padding: 2rem 2.4rem;
  margin-bottom: 1.6rem;
  position: relative;
  overflow: hidden;
  animation: heroIn 0.7s ease-out;
}
.hero-banner::before {
  content: '';
  position: absolute; top: -60%; right: -20%;
  width: 360px; height: 360px;
  background: radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%);
  pointer-events: none;
}
.hero-banner h1 {
  font-size: clamp(1.6rem, 2.8vw, 2.5rem);
  font-weight: 700;
  margin: 0 0 0.5rem;
  background: linear-gradient(135deg, #fff 30%, var(--accent) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero-banner p { margin: 0; color: var(--text-dim); font-size: 1.02rem; }
.hero-badge {
  display: inline-flex; align-items: center; gap: 0.4rem;
  background: rgba(16,185,129,0.15); border: 1px solid rgba(16,185,129,0.35);
  border-radius: 999px; padding: 0.25rem 0.75rem;
  font-size: 0.78rem; font-weight: 500; color: var(--accent3);
  margin-top: 0.75rem;
}

/* ── Metric pills ───────────────────────────────────────── */
.metric-row { display: flex; gap: 0.75rem; flex-wrap: wrap; margin: 0.5rem 0; }
.metric-pill {
  background: rgba(79,142,247,0.10);
  border: 1px solid rgba(79,142,247,0.20);
  border-radius: 10px;
  padding: 0.55rem 1rem;
  font-size: 0.82rem;
  color: var(--text-dim);
  font-family: var(--mono);
}
.metric-pill strong { display: block; font-size: 1.1rem; color: var(--text); font-weight: 600; }

/* ── Concept chips ──────────────────────────────────────── */
.chip-wrap { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.5rem; }
.chip {
  display: inline-block;
  padding: 0.3rem 0.75rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-family: var(--mono);
  background: rgba(139,92,246,0.12);
  border: 1px solid rgba(139,92,246,0.30);
  color: #c4b5fd;
  transition: background 0.2s ease;
}
.chip:hover { background: rgba(139,92,246,0.22); }

/* ── Answer card ────────────────────────────────────────── */
.answer-card {
  background: rgba(16,185,129,0.06);
  border: 1px solid rgba(16,185,129,0.22);
  border-left: 4px solid var(--accent3);
  border-radius: 14px;
  padding: 1.2rem 1.4rem;
  margin: 1rem 0;
  animation: riseIn 0.4s ease-out;
}
.answer-card h3 { margin: 0 0 0.6rem; font-size: 1rem; color: var(--accent3); }
.answer-card p { margin: 0; line-height: 1.65; color: var(--text); }

/* ── Citation badge ─────────────────────────────────────── */
.cite-badge {
  display: inline-flex; align-items: center; gap: 0.35rem;
  background: rgba(79,142,247,0.10);
  border: 1px solid rgba(79,142,247,0.25);
  border-radius: 8px;
  padding: 0.2rem 0.6rem;
  font-family: var(--mono);
  font-size: 0.75rem;
  color: var(--accent);
}

/* ── 3D Flashcard ──────────────────────────────────────────── */
.flashcard {
  background: transparent;
  perspective: 1000px;
  height: 160px;
  margin: 0.5rem 0;
}
.flashcard-inner {
  position: relative;
  width: 100%;
  height: 100%;
  text-align: center;
  transition: transform 0.6s cubic-bezier(0.4, 0.0, 0.2, 1);
  transform-style: preserve-3d;
  cursor: pointer;
}
.flashcard:hover .flashcard-inner {
  transform: rotateY(180deg);
}
.flashcard-front, .flashcard-back {
  position: absolute;
  width: 100%;
  height: 100%;
  -webkit-backface-visibility: hidden;
  backface-visibility: hidden;
  border-radius: 12px;
  padding: 1.2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
}
.flashcard-front {
  background: rgba(245,158,11,0.06);
  border: 1px solid rgba(245,158,11,0.20);
}
.flashcard-front .fc-q {
  font-weight: 600;
  color: var(--gold);
  font-size: 1rem;
}
.flashcard-back {
  background: rgba(16,185,129,0.08);
  border: 1px solid rgba(16,185,129,0.30);
  color: #e2e8f0;
  transform: rotateY(180deg);
  font-size: 0.95rem;
  line-height: 1.5;
  overflow-y: auto;
}

/* ── Quiz card ──────────────────────────────────────────── */
.quiz-card {
  background: rgba(79,142,247,0.06);
  border: 1px solid rgba(79,142,247,0.18);
  border-radius: 12px;
  padding: 0.9rem 1.1rem;
  margin: 0.5rem 0;
}
.quiz-card .qz-q { font-weight: 600; color: var(--accent); font-size: 0.9rem; margin-bottom: 0.5rem; }
.quiz-card .qz-opt { color: var(--text-dim); font-size: 0.85rem; margin: 0.2rem 0; }
.quiz-card .qz-ans { color: var(--accent3); font-size: 0.82rem; margin-top: 0.4rem; font-weight: 600; }

/* ── Section title ──────────────────────────────────────── */
.section-title {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin: 1.2rem 0 0.6rem;
}

/* ── Status indicator ───────────────────────────────────── */
.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; }
.status-dot.green { background: var(--accent3); box-shadow: 0 0 6px var(--accent3); }
.status-dot.yellow { background: var(--gold); box-shadow: 0 0 6px var(--gold); }
.status-dot.red { background: var(--danger); box-shadow: 0 0 6px var(--danger); }

/* ── Progress bar ───────────────────────────────────────── */
.progress-track { background: rgba(255,255,255,0.06); border-radius: 999px; height: 4px; overflow: hidden; margin: 0.5rem 0; }
.progress-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--accent), var(--accent2)); animation: progressAnim 2s ease infinite; }
@keyframes progressAnim { 0%{width:0%} 60%{width:85%} 100%{width:100%} }

/* ── Buttons ────────────────────────────────────────────── */
.stButton > button {
  background: linear-gradient(135deg, var(--accent), var(--accent2)) !important;
  border: none !important;
  border-radius: 10px !important;
  color: #fff !important;
  font-weight: 600 !important;
  font-family: 'Inter', sans-serif !important;
  transition: opacity 0.2s ease, transform 0.15s ease !important;
}
.stButton > button:hover { opacity: 0.88 !important; transform: translateY(-1px) !important; }
.stButton > button:active { transform: translateY(0) !important; }

/* ── Inputs ─────────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  color: var(--text) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px rgba(79,142,247,0.15) !important;
}
label, .stSelectbox label, .stRadio label { color: var(--text-dim) !important; font-size: 0.85rem !important; }

/* ── Alert / warning ────────────────────────────────────── */
.v-alert {
  background: rgba(239,68,68,0.08);
  border: 1px solid rgba(239,68,68,0.25);
  border-radius: 10px;
  padding: 0.75rem 1rem;
  color: #fca5a5;
  font-size: 0.88rem;
}

/* ── Animations ─────────────────────────────────────────── */
@keyframes heroIn { from{opacity:0;transform:translateY(-12px)} to{opacity:1;transform:translateY(0)} }
@keyframes riseIn { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
@keyframes fadeIn { from{opacity:0} to{opacity:1} }

/* ── Scrollbar ──────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(99,179,237,0.25); border-radius: 6px; }

/* ── Divider ────────────────────────────────────────────── */
hr { border: none; border-top: 1px solid var(--border); margin: 1rem 0; }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seconds_to_hms(total_seconds: float) -> str:
    v = int(max(total_seconds, 0))
    return f"{v // 3600:02d}:{(v % 3600) // 60:02d}:{v % 60:02d}"


def _alert(msg: str) -> None:
    st.markdown(f"<div class='v-alert'>{msg}</div>", unsafe_allow_html=True)


def _init_state() -> None:
    defaults: dict[str, Any] = {
        "session_id": "",
        "video_bytes": b"",
        "video_url": "",
        "video_start": 0,
        "concepts": [],
        "flashcards": [],
        "quiz_questions": [],
        "summary": "",
        "citations": [],
        "answer": "",
        "model_name": "",
        "latency_ms": 0.0,
        "question_input": "",
        "api_status": "unknown",
        "model_info": {},
        "processing": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


_init_state()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        "<div style='margin-top:0.5rem'>"
        "<span style='font-size:1.5rem'>🎓</span>"
        "<span style='font-size:1.1rem;font-weight:700;margin-left:0.5rem;color:#e2e8f0'>V2AI</span>"
        "<br><span style='font-size:0.75rem;color:#64748b'>Lecture Intelligence Studio</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("<div class='section-title'>🔧 Configuration</div>", unsafe_allow_html=True)
    api_base_url = st.text_input(
        "API Base URL",
        value=os.getenv("API_BASE_URL", "http://localhost:8000"),
        help="FastAPI backend endpoint",
    )

    # Health check
    if st.button("Check API Health", use_container_width=True):
        try:
            r = requests.get(f"{api_base_url.rstrip('/')}/health", timeout=5)
            if r.status_code == 200:
                st.session_state["api_status"] = "online"
                hdot = "green"
            else:
                st.session_state["api_status"] = "error"
                hdot = "red"
        except Exception:
            st.session_state["api_status"] = "offline"
            hdot = "red"

    status = st.session_state["api_status"]
    if status == "online":
        st.markdown("<span class='status-dot green'></span> API Online", unsafe_allow_html=True)
    elif status in ("error", "offline"):
        st.markdown("<span class='status-dot red'></span> API Offline", unsafe_allow_html=True)

    # Model Info
    if st.button("Fetch Model Info", use_container_width=True):
        try:
            r = requests.get(f"{api_base_url.rstrip('/')}/model-info", timeout=5)
            if r.status_code == 200:
                st.session_state["model_info"] = r.json()
        except Exception:
            pass

    if st.session_state["model_info"]:
        mi = st.session_state["model_info"]
        st.markdown("<div class='section-title'>🤖 Active Models</div>", unsafe_allow_html=True)
        gpu_icon = "⚡" if mi.get("use_gpu") else "🖥️"
        st.markdown(
            f"<div style='font-size:0.8rem;color:#94a3b8'>"
            f"{gpu_icon} <b style='color:#e2e8f0'>Device:</b> {'GPU' if mi.get('use_gpu') else 'CPU'}<br>"
            f"📝 <b style='color:#e2e8f0'>LLM:</b> {mi.get('generation_model','—')}<br>"
            f"📊 <b style='color:#e2e8f0'>Summary:</b> {mi.get('summary_model','—')}<br>"
            f"🔍 <b style='color:#e2e8f0'>Embed:</b> {mi.get('embedding_model','—')}<br>"
            f"🎙️ <b style='color:#e2e8f0'>Whisper:</b> {mi.get('whisper_model','—')}"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("<div class='section-title'>📚 Pipeline</div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:0.78rem;color:#64748b;line-height:1.8'>"
        "① Upload video / YouTube URL<br>"
        "② Whisper ASR → Transcript<br>"
        "③ HuggingFace → Summary<br>"
        "④ Sentence-BERT → Concepts<br>"
        "⑤ LangChain + FAISS → RAG<br>"
        "⑥ HuggingFace → Answer<br>"
        "⑦ MLflow / WandB → Tracking"
        "</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Hero Banner
# ---------------------------------------------------------------------------
st.markdown(
    """
<div class='hero-banner'>
  <h1>🎓 V2AI · Lecture Intelligence Studio</h1>
  <p>
    Upload any lecture video or YouTube URL — get instant transcription, AI summary,
    key concept extraction, flashcards, quiz questions, and contextual QA with
    timestamped citations.
  </p>
  <div class='hero-badge'>
    <span>🧠</span> Whisper + LangChain + HuggingFace + FAISS + MLflow
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Main Layout
# ---------------------------------------------------------------------------
upload_col, session_col = st.columns([1, 1.1], gap="medium")

# ── Column 1: Upload ─────────────────────────────────────────────────────────
with upload_col:
    st.markdown("<div class='v-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>📤 Step 1 · Upload Lecture</div>", unsafe_allow_html=True)

    lecture_title = st.text_input(
        "Lecture title (optional)",
        value="",
        placeholder="e.g. Transformer Architecture Deep Dive",
    )
    input_mode = st.radio(
        "Input source",
        options=["📁 Local Video File", "▶️ YouTube URL"],
        horizontal=True,
    )

    uploaded_file = None
    youtube_url = ""
    if "Local" in input_mode:
        uploaded_file = st.file_uploader(
            "Choose video file",
            type=["mp4", "mov", "mkv", "webm", "avi"],
            accept_multiple_files=False,
        )
    else:
        youtube_url = st.text_input(
            "YouTube link",
            value="",
            placeholder="https://www.youtube.com/watch?v=...",
        )

    process_clicked = st.button("🚀 Process Lecture", type="primary", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if process_clicked:
        if "Local" in input_mode and uploaded_file is None:
            st.warning("Please upload a video file first.")
        elif "YouTube" in input_mode and not youtube_url.strip():
            st.warning("Please paste a YouTube URL first.")
        else:
            endpoint = ""
            response = None

            if "Local" in input_mode and uploaded_file is not None:
                payload_bytes = uploaded_file.getvalue()
                files = {
                    "file": (
                        uploaded_file.name,
                        payload_bytes,
                        uploaded_file.type or "application/octet-stream",
                    )
                }
                endpoint = f"{api_base_url.rstrip('/')}/upload-video"
                request_kwargs = {
                    "files": files,
                    "data": {"title": lecture_title.strip()},
                    "timeout": 7200,
                }
            else:
                payload_bytes = b""
                endpoint = f"{api_base_url.rstrip('/')}/upload-video-url"
                request_kwargs = {
                    "json": {
                        "video_url": youtube_url.strip(),
                        "title": lecture_title.strip() or None,
                    },
                    "timeout": 7200,
                }

            # Progress animation
            prog_area = st.empty()
            prog_area.markdown(
                "<div class='v-card'>"
                "<div class='section-title'>⚙️ Processing Pipeline</div>"
                "<p style='color:#94a3b8;font-size:0.85rem'>Running Whisper transcription → Summarization → Embedding → Index build...</p>"
                "<div class='progress-track'><div class='progress-fill'></div></div>"
                "</div>",
                unsafe_allow_html=True,
            )

            try:
                with st.spinner("Processing lecture — this may take 1-3 minutes..."):
                    t0 = time.time()
                    response = requests.post(endpoint, **request_kwargs)
                    elapsed = round(time.time() - t0, 1)

                prog_area.empty()

                if response.status_code != 200:
                    _alert(f"Pipeline failed ({response.status_code}): {response.text[:300]}")
                else:
                    result: dict[str, Any] = response.json()
                    st.session_state.update(
                        {
                            "session_id": result["session_id"],
                            "video_start": 0,
                            "summary": result["summary"],
                            "concepts": result["concepts"],
                            "flashcards": result.get("flashcards", []),
                            "quiz_questions": result.get("quiz_questions", []),
                            "video_bytes": payload_bytes if "Local" in input_mode else b"",
                            "video_url": youtube_url.strip() if "YouTube" in input_mode else "",
                        }
                    )
                    st.markdown(
                        f"<div class='v-card' style='border-color:rgba(16,185,129,0.3)'>"
                        f"<div class='section-title'>✅ Lecture Processed</div>"
                        f"<div class='metric-row'>"
                        f"<div class='metric-pill'><strong>{_seconds_to_hms(result['duration_seconds'])}</strong>Duration</div>"
                        f"<div class='metric-pill'><strong>{result['transcript_word_count']:,}</strong>Words</div>"
                        f"<div class='metric-pill'><strong>{elapsed}s</strong>Pipeline</div>"
                        f"</div>"
                        f"<p style='font-size:0.75rem;color:#64748b;margin:0.4rem 0 0'>Session ID: {result['session_id']}</p>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            except requests.RequestException as exc:
                prog_area.empty()
                _alert(f"Cannot reach API at {endpoint}: {exc}")

# ── Column 2: Session Intelligence ───────────────────────────────────────────
with session_col:
    if st.session_state["session_id"]:
        # Summary
        import json
        raw_summary = st.session_state.get("summary", "")
        explained_text = ""
        summarized_text = raw_summary
        
        try:
            summary_data = json.loads(raw_summary)
            if isinstance(summary_data, dict) and "explained" in summary_data:
                explained_text = summary_data.get("explained", "")
                summarized_text = summary_data.get("summarized", "")
        except:
            pass

        st.markdown("<div class='v-card'><div class='section-title'>📄 AI Summary</div>", unsafe_allow_html=True)
        
        if explained_text:
            tab_exp, tab_sum = st.tabs(["💡 AI Explained", "📝 AI Summarized"])
            with tab_exp:
                st.markdown(f"<p style='line-height:1.7;color:#cbd5e1'>{explained_text}</p>", unsafe_allow_html=True)
            with tab_sum:
                st.markdown(f"<p style='line-height:1.7;color:#cbd5e1'>{summarized_text}</p>", unsafe_allow_html=True)
        else:
            st.markdown(f"<p style='line-height:1.7;color:#cbd5e1'>{summarized_text}</p>", unsafe_allow_html=True)
            
        st.markdown("</div>", unsafe_allow_html=True)

        # Key Concepts
        if st.session_state["concepts"]:
            chips = "".join(
                f"<span class='chip'>{c}</span>" for c in st.session_state["concepts"]
            )
            st.markdown(
                f"<div class='v-card'>"
                f"<div class='section-title'>🏷️ Key Concepts</div>"
                f"<div class='chip-wrap'>{chips}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<div class='v-card' style='text-align:center;padding:3rem 2rem'>"
            "<div style='font-size:3rem'>🎓</div>"
            "<p style='color:#64748b;margin-top:0.75rem'>Upload and process a lecture video<br>to see AI-generated insights here.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Flashcards + Quiz (tabs)
# ---------------------------------------------------------------------------
if st.session_state["session_id"]:
    st.markdown("<hr>", unsafe_allow_html=True)
    tab_flash, tab_quiz, tab_video = st.tabs(["📇 Flashcards", "🧪 Quiz", "🎬 Video Player"])

    with tab_flash:
        flashcards = st.session_state["flashcards"]
        if flashcards:
            cols = st.columns(2)
            for i, card in enumerate(flashcards):
                with cols[i % 2]:
                    st.markdown(
                        f'''
                        <div class="flashcard">
                          <div class="flashcard-inner">
                            <div class="flashcard-front">
                              <div class="fc-q">Q{i+1}. {card["question"]}</div>
                            </div>
                            <div class="flashcard-back">
                              <div class="fc-a">{card["answer"]}</div>
                            </div>
                          </div>
                        </div>
                        ''',
                        unsafe_allow_html=True,
                    )
        else:
            st.info("No flashcards yet. Process a lecture first.")

    with tab_quiz:
        quiz_q = st.session_state["quiz_questions"]
        if quiz_q:
            for i, quiz in enumerate(quiz_q, start=1):
                opts_html = "".join(
                    f"<div class='qz-opt'>{'✅' if opt == quiz.get('correct_answer') else '○'} {opt}</div>"
                    for opt in quiz.get("options", [])
                )
                st.markdown(
                    f"<div class='quiz-card'>"
                    f"<div class='qz-q'>{i}. {quiz['question']}</div>"
                    f"{opts_html}"
                    f"<div class='qz-ans'>✔ {quiz.get('correct_answer','—')}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No quiz questions yet. Process a lecture first.")

    with tab_video:
        if st.session_state["video_bytes"]:
            st.video(
                st.session_state["video_bytes"],
                start_time=int(st.session_state["video_start"]),
            )
        elif st.session_state["video_url"]:
            st.video(
                st.session_state["video_url"],
                start_time=int(st.session_state["video_start"]),
            )
        else:
            st.info("No video available.")

# ---------------------------------------------------------------------------
# QA Section
# ---------------------------------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    "<div class='section-title'>💬 Step 2 · Ask Questions With Context</div>",
    unsafe_allow_html=True,
)

qa_col, _ = st.columns([2, 0.8])
with qa_col:
    question = st.text_area(
        "Your question",
        value=st.session_state.get("question_input", ""),
        height=110,
        placeholder="e.g. Explain how the attention mechanism works in transformers.",
    )

    ask_col, clear_col = st.columns(2)
    with ask_col:
        ask_clicked = st.button("🔍 Ask V2AI", type="primary", use_container_width=True)
    with clear_col:
        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state.update(
                {"answer": "", "citations": [], "question_input": ""}
            )
            st.rerun()

if ask_clicked:
    st.session_state["question_input"] = question
    if not st.session_state["session_id"]:
        st.warning("Process a lecture first to create a session.")
    elif not question.strip():
        st.warning("Please enter a question.")
    else:
        endpoint = f"{api_base_url.rstrip('/')}/ask"
        try:
            with st.spinner("Retrieving context and generating answer..."):
                response = requests.post(
                    endpoint,
                    json={
                        "session_id": st.session_state["session_id"],
                        "question": question.strip(),
                    },
                    timeout=240,
                )
            if response.status_code != 200:
                _alert(f"Ask failed ({response.status_code}): {response.text[:300]}")
            else:
                payload: dict[str, Any] = response.json()
                st.session_state.update(
                    {
                        "answer": payload["answer"],
                        "citations": payload["citations"],
                        "model_name": payload["model_name"],
                        "latency_ms": payload["latency_ms"],
                    }
                )
        except requests.RequestException as exc:
            _alert(f"Cannot reach API: {exc}")

# Display answer
if st.session_state["answer"]:
    st.markdown(
        f"<div class='answer-card'>"
        f"<h3>🤖 Generated Answer</h3>"
        f"<p>{st.session_state['answer']}</p>"
        f"<div class='metric-row' style='margin-top:0.75rem'>"
        f"<div class='metric-pill'><strong>{st.session_state['latency_ms']} ms</strong>Latency</div>"
        f"<div class='metric-pill'><strong style='font-size:0.82rem'>{st.session_state['model_name']}</strong>Model</div>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

# Citations
if st.session_state["citations"]:
    st.markdown(
        "<div class='section-title'>📌 Timestamped Evidence</div>",
        unsafe_allow_html=True,
    )
    for idx, cit in enumerate(st.session_state["citations"], start=1):
        ts_badge = (
            f"<span class='cite-badge'>🕒 {cit['start_hms']} → {cit['end_hms']}</span>"
        )
        st.markdown(
            f"<div class='v-card' style='padding:0.9rem 1.1rem;margin-bottom:0.5rem'>"
            f"<b style='font-size:0.9rem'>[{idx}] {cit['source']}</b> {ts_badge}<br>"
            f"<div style='color:#94a3b8;font-size:0.85rem;margin-top:0.4rem'>{cit['text'][:280]}…</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.button(f"⏩ Jump to {cit['start_hms']}", key=f"jump_{idx}"):
            st.session_state["video_start"] = int(cit.get("start_seconds", 0))
            st.rerun()
