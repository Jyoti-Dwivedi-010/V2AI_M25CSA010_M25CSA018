from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.video_pipeline_service import get_video_pipeline_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process lecture video into V2AI session and optionally ask a question"
    )
    parser.add_argument("video_path", help="Path to lecture video file")
    parser.add_argument("--title", default="", help="Optional session title")
    parser.add_argument(
        "--question",
        default="",
        help="Optional question to ask after session creation",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    video_path = Path(args.video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    service = get_video_pipeline_service()
    session = service.create_session(
        filename=video_path.name,
        content=video_path.read_bytes(),
        title=args.title or None,
    )

    print("[SESSION CREATED]")
    print(json.dumps(session, indent=2))

    if args.question.strip():
        answer = service.ask_question(session["session_id"], args.question.strip())
        print("[QUESTION ANSWERED]")
        print(json.dumps(answer, indent=2))


if __name__ == "__main__":
    main()
