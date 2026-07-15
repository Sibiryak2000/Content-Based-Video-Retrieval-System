"""Verify Phase 3 FAISS index artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.build_index import read_faiss_index  # noqa: E402

PROCESSED = REPO / "data" / "processed"


def main() -> int:
    print("=== Phase 3 index verification ===")
    failed = 0
    for name in ("faiss.index", "faiss_id_map.json", "embeddings.npy", "embedding_manifest.json"):
        if not (PROCESSED / name).is_file():
            print(f"FAIL missing {name}")
            failed += 1
        else:
            print(f"OK   {name}")
    if failed:
        return 1

    manifest = json.loads((PROCESSED / "embedding_manifest.json").read_text(encoding="utf-8"))
    id_data = json.loads((PROCESSED / "faiss_id_map.json").read_text(encoding="utf-8"))
    vectors = np.load(PROCESSED / "embeddings.npy")
    index = read_faiss_index(PROCESSED / "faiss.index")
    shot_ids = id_data["shot_ids"]
    checks = [
        len(shot_ids) == manifest.get("vector_count", len(shot_ids)),
        vectors.shape[0] == len(shot_ids),
        index.ntotal == len(shot_ids),
    ]
    for ok in checks:
        if not ok:
            failed += 1
    print(f"{'OK' if all(checks) else 'FAIL'} {len(shot_ids)} vectors")
    print("=== Done ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
