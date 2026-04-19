from __future__ import annotations

import argparse
import json

from app.services.video_pipeline_service import get_video_pipeline_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove old lecture sessions and local artifacts based on retention policy"
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Delete sessions older than this number of days",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = get_video_pipeline_service()
    report = service.cleanup_old_sessions(retention_days=args.retention_days)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
