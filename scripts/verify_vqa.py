"""Verify Phase 3-4 VQA answering pipeline end-to-end (R1 + R3)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ContBVideoRetr"))

from services.faiss_search import faiss_index_available  # noqa: E402
from services.vqa_service import create_vqa_service  # noqa: E402


def main() -> int:
    print("=== VQA verification ===")
    if not faiss_index_available():
        print("SKIP no FAISS index")
        return 0
    svc = create_vqa_service()
    resp = svc.answer_query("what color is the car?", limit=5, offset=0)
    failed = 0
    if not resp.items:
        print("FAIL no retrieval results")
        failed += 1
    else:
        answered = [it for it in resp.items if it.text]
        if not answered:
            print("FAIL no VQA answers generated")
            failed += 1
        for it in answered:
            print(f"OK {it.shot_id}: '{it.text}' (score={it.score:.3f})")
    print("=== Done ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
