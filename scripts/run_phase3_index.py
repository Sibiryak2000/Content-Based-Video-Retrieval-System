"""Build CLIP embeddings + FAISS index from Phase 2 catalog."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.build_index import build_flat_index, write_faiss_index  # noqa: E402
from pipeline.config import load_config  # noqa: E402
from pipeline.db.store import MetadataStore  # noqa: E402
from pipeline.embedding_spec import DEFAULT_EMBEDDING_CONFIG, DEFAULT_KEYFRAME_POLICY  # noqa: E402
from pipeline.embeddings import _load_clip, encode_image_path  # noqa: E402


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def build_index(config_path: Path, force: bool = False) -> dict:
    config = load_config(config_path)
    processed = config.output.root
    store = MetadataStore(config.output.db_path, config.repo_root)

    index_path = processed / "faiss.index"
    if index_path.is_file() and not force:
        manifest = json.loads((processed / "embedding_manifest.json").read_text(encoding="utf-8"))
        return {"skipped": True, "vector_count": manifest.get("vector_count", 0)}

    excluded: set[str] = set()
    manifest_path = processed / "embedding_manifest.json"
    if manifest_path.is_file():
        excluded = set(json.loads(manifest_path.read_text(encoding="utf-8")).get("excluded_shots", []))

    device = "cpu"
    model, processor = _load_clip(device)

    shot_ids: list[str] = []
    vectors: list[np.ndarray] = []

    with store.connect() as conn:
        rows = conn.execute(
            """
            SELECT s.shot_id, s.keyframe_path
            FROM shots s
            JOIN videos v ON s.video_id = v.video_id
            ORDER BY s.video_id, s.shot_index
            """
        ).fetchall()

    for i, row in enumerate(rows, start=1):
        sid = row["shot_id"]
        kf = row["keyframe_path"]
        if sid in excluded:
            continue
        kf_path = store.resolve_path(kf, config.repo_root)
        if not kf_path or not Path(kf_path).is_file():
            excluded.add(sid)
            continue
        try:
            vec = encode_image_path(model, processor, kf_path, device).numpy()
            shot_ids.append(sid)
            vectors.append(vec)
        except Exception:
            excluded.add(sid)
        if i % 500 == 0:
            print(f"  encoded {len(shot_ids)} shots...", flush=True)

    arr = np.stack(vectors).astype(np.float32)
    index = build_flat_index(arr)
    write_faiss_index(index, index_path)
    np.save(processed / "embeddings.npy", arr)
    (processed / "faiss_id_map.json").write_text(
        json.dumps({"shot_ids": shot_ids}, indent=2), encoding="utf-8"
    )

    manifest = {
        "model": DEFAULT_EMBEDDING_CONFIG.image_model.value,
        "embedding_dim": DEFAULT_EMBEDDING_CONFIG.embedding_dim,
        "similarity_metric": DEFAULT_EMBEDDING_CONFIG.similarity_metric.value,
        "vector_count": len(shot_ids),
        "excluded_shots": sorted(excluded),
        "keyframe_policy": DEFAULT_KEYFRAME_POLICY.strategy,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "config_hash": config_path.read_bytes().__hash__(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    store.log_run(config_path, notes=f"phase3_index vectors={len(shot_ids)}")
    return {"vector_count": len(shot_ids), "excluded": len(excluded)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FAISS index from keyframes")
    parser.add_argument("--config", type=Path, default=REPO / "config.yaml")
    parser.add_argument("--force", action="store_true", help="Rebuild even if index exists")
    args = parser.parse_args()
    print("=== Building CLIP embeddings + FAISS index ===")
    result = build_index(args.config, force=args.force)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
