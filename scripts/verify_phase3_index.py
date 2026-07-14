"""Validate Phase 3 FAISS index and embedding artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.build_index import read_faiss_index  # noqa: E402

from pipeline.config import load_config  # noqa: E402
from pipeline.db.store import MetadataStore  # noqa: E402
from pipeline.embedding_spec import DEFAULT_EMBEDDING_CONFIG  # noqa: E402


def main() -> int:
    config = load_config(REPO_ROOT / "config.yaml")
    store = MetadataStore(config.output.db_path, config.repo_root)

    emb_path = config.output.embeddings_path
    id_map_path = config.output.faiss_id_map
    index_path = config.output.faiss_index
    manifest_path = config.output.embedding_manifest

    failed = 0
    print("=== Phase 3 index verification ===")

    for p in (emb_path, id_map_path, index_path, manifest_path):
        if not p.is_file():
            print(f"FAIL missing: {p}")
            failed += 1
            return 1

    vectors = np.load(emb_path)
    id_data = json.loads(id_map_path.read_text(encoding="utf-8"))
    shot_ids: list[str] = id_data["shot_ids"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    index = read_faiss_index(index_path)

    print(f"Vectors:     {vectors.shape[0]} x {vectors.shape[1]}")
    print(f"Id map:      {len(shot_ids)}")
    print(f"FAISS ntotal:{index.ntotal}")
    print(f"Excluded:    {manifest.get('excluded_count', '?')}")

    if vectors.shape[0] != len(shot_ids):
        print("FAIL row count mismatch embeddings vs id_map")
        failed += 1
    if index.ntotal != len(shot_ids):
        print("FAIL FAISS ntotal mismatch")
        failed += 1
    if vectors.shape[1] != DEFAULT_EMBEDDING_CONFIG.embedding_dim:
        print("FAIL embedding dim mismatch")
        failed += 1

    missing_db = [sid for sid in shot_ids if not store.get_shots_by_ids([sid])]
    if missing_db:
        print(f"FAIL {len(missing_db)} shot_ids not in metadata.db")
        failed += 1
    else:
        print("OK all shot_ids exist in metadata.db")

    # Self-similarity spot check
    if shot_ids:
        test_id = shot_ids[0]
        row = 0
        vec = vectors[row : row + 1]
        scores, indices = index.search(vec, 3)
        top_id = shot_ids[int(indices[0][0])]
        top_score = float(scores[0][0])
        if top_id == test_id and top_score > 0.99:
            print(f"OK self-similarity {test_id} score={top_score:.4f}")
        else:
            print(f"FAIL self-similarity expected {test_id}, got {top_id} score={top_score:.4f}")
            failed += 1

    print("=== Done ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
