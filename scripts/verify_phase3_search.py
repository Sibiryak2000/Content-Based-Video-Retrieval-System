"""Phase 3 joint verification — semantic search smoke test."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ContBVideoRetr"))

from pipeline.config import load_config  # noqa: E402
from services.faiss_search import faiss_index_available  # noqa: E402
from services.search_api import create_search_service  # noqa: E402


def main() -> int:
    cfg = load_config(REPO / "config.yaml")
    print("=== Phase 3 search verification ===")
    print(f"FAISS available: {faiss_index_available(cfg)}")

    search = create_search_service()
    print(f"Service: {type(search).__name__} — {search.source_label}")

    browse = search.list_all(5, 0)
    print(f"Browse page: {len(browse.items)} items, total={browse.total}")

    if not faiss_index_available(cfg):
        print("SKIP semantic tests (no index)")
        return 0

    for query in ("person walking", "ocean water"):
        resp = search.text_query(query, limit=5, offset=0)
        print(f"\nQuery: {query!r} ({resp.latency_ms:.0f} ms)")
        for item in resp.items:
            print(f"  {item.shot_id}  score={item.score:.3f}  {item.video_id}")

    sim = search.similarity_query("00001_0000", limit=5, offset=0)
    print(f"\nSimilar to 00001_0000 ({sim.latency_ms:.0f} ms):")
    for item in sim.items:
        print(f"  {item.shot_id}  score={item.score:.3f}")

    print("\n=== Done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
