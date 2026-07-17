"""Verify Phase 4 R1/R3 submission confidence safeguard."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ContBVideoRetr"))

from models.result_item import ResultItem  # noqa: E402
from services.dres_client import submission_confidence_warning  # noqa: E402


def main() -> int:
    print("=== Submission confidence safeguard verification ===")
    low = ResultItem(video_id="00001", shot_id="00001_0000", score=0.05)
    high = ResultItem(video_id="00001", shot_id="00001_0000", score=0.9)
    browse = ResultItem(video_id="00001", shot_id="00001_0000", score=0.0)

    checks = [
        (submission_confidence_warning(low) is not None, "low score warns"),
        (submission_confidence_warning(high) is None, "high score silent"),
        (submission_confidence_warning(browse) is None, "browse-mode (score=0) silent"),
    ]
    failed = 0
    for ok, label in checks:
        print(f"{'OK' if ok else 'FAIL'} {label}")
        if not ok:
            failed += 1
    print("=== Done ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
