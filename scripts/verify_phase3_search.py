"""Verify Phase 3 semantic search service (browse + text query)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ContBVideoRetr"))

from services.faiss_search import faiss_index_available  # noqa: E402
from services.search_api import create_search_service  # noqa: E402


def main() -> int:
    print("=== Phase 3 search verification ===")
    if not faiss_index_available():
        print("SKIP no FAISS index artifacts")
        return 0

    failed = 0
    svc = create_search_service()
    print(f"Service: {svc.source_label}")

    browse = svc.list_all(limit=10, offset=0)
    if browse.total <= 0 or not browse.items:
        print("FAIL browse returned no items")
        failed += 1
    else:
        print(f"OK browse: {len(browse.items)} items, total={browse.total}")

    resp = svc.text_query("person walking outdoors", limit=5, offset=0)
    if not resp.items:
        print("FAIL semantic query returned no items")
        failed += 1
    else:
        top = resp.items[0]
        print(
            f"OK semantic: top={top.shot_id} score={top.score:.3f} "
            f"latency={resp.latency_ms:.0f}ms"
        )

    if browse.items:
        seed = browse.items[0].shot_id
        sim = svc.similarity_query(seed, limit=5, offset=0)
        if not sim.items:
            print(f"FAIL similarity from {seed}")
            failed += 1
        else:
            print(f"OK similarity: {len(sim.items)} hits from {seed}")

    print("=== Done ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
