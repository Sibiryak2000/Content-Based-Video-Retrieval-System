"""Verify Phase 3 semantic search service."""

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
        print("SKIP no FAISS index")
        return 0
    failed = 0
    svc = create_search_service()
    browse = svc.list_all(limit=10, offset=0)
    if not browse.items:
        failed += 1
    else:
        print(f"OK browse: {len(browse.items)} items")
    resp = svc.text_query("person walking outdoors", limit=5, offset=0)
    if not resp.items:
        failed += 1
    else:
        print(f"OK semantic: top={resp.items[0].shot_id} score={resp.items[0].score:.3f}")
    if browse.items:
        sim = svc.similarity_query(browse.items[0].shot_id, limit=5, offset=0)
        if not sim.items:
            failed += 1
        else:
            print(f"OK similarity: {len(sim.items)} hits")
    print("=== Done ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
