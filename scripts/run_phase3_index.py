"""Run Phase 3: CLIP embeddings + FAISS index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.build_index import build_faiss_index  # noqa: E402
from pipeline.config import load_config  # noqa: E402
from pipeline.db.store import MetadataStore  # noqa: E402
from pipeline.embeddings import build_embeddings  # noqa: E402
from pipeline.inventory import list_video_ids  # noqa: E402


def select_video_ids(
    all_ids: list[str],
    video_id: str | None,
    from_id: str | None,
    to_id: str | None,
) -> list[str] | None:
    if not video_id and not from_id and not to_id:
        return None
    if video_id:
        return [video_id]
    ids = all_ids
    if from_id:
        ids = [v for v in ids if v >= from_id]
    if to_id:
        ids = [v for v in ids if v <= to_id]
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description="IVADL Phase 3 index pipeline")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config.yaml")
    parser.add_argument("--video-id", type=str, help="Limit embedding to one video")
    parser.add_argument("--from", dest="from_id", type=str)
    parser.add_argument("--to", dest="to_id", type=str)
    parser.add_argument("--embeddings-only", action="store_true")
    parser.add_argument("--index-only", action="store_true")
    parser.add_argument("--force", action="store_true", help="Rebuild even if unchanged")
    args = parser.parse_args()

    config = load_config(args.config)
    store = MetadataStore(config.output.db_path, config.repo_root)

    all_ids = list_video_ids(config.dataset.videos_dir)
    video_ids = select_video_ids(all_ids, args.video_id, args.from_id, args.to_id)

    summary: dict = {}

    if not args.index_only:
        print("=== Building CLIP embeddings ===", flush=True)
        emb = build_embeddings(
            config, store, video_ids=video_ids,
            skip_if_unchanged=not args.force,
        )
        summary["embeddings"] = {
            "vector_count": emb.vector_count,
            "excluded": len(emb.excluded_shots),
        }
        print(json.dumps(summary["embeddings"], indent=2), flush=True)

    if not args.embeddings_only:
        print("=== Building FAISS index ===", flush=True)
        idx = build_faiss_index(config)
        summary["index"] = {
            "vector_count": idx.vector_count,
            "path": str(idx.index_path),
        }
        print(json.dumps(summary["index"], indent=2), flush=True)

    print("\n=== Phase 3 index complete ===", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
