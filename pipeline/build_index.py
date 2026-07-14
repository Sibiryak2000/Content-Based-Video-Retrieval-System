"""Build a FAISS IndexFlatIP over L2-normalized CLIP embeddings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np

from pipeline.config import PipelineConfig, load_config
from pipeline.embedding_spec import DEFAULT_EMBEDDING_CONFIG


def _write_index_bytes(path: Path, index: faiss.Index) -> None:
    """Write FAISS index via bytes (avoids Cyrillic path issues on Windows)."""
    data = faiss.serialize_index(index)
    if isinstance(data, np.ndarray):
        path.write_bytes(data.tobytes())
    else:
        path.write_bytes(bytes(data))


def read_faiss_index(path: Path) -> faiss.Index:
    """Load FAISS index from disk (Cyrillic-path safe on Windows)."""
    raw = path.read_bytes()
    return faiss.deserialize_index(np.frombuffer(raw, dtype=np.uint8))


@dataclass
class IndexBuildResult:
    vector_count: int
    index_path: Path
    id_map_path: Path


def build_faiss_index(config: PipelineConfig) -> IndexBuildResult:
    emb_path = config.output.embeddings_path
    id_map_path = config.output.faiss_id_map
    index_path = config.output.faiss_index

    if not emb_path.is_file():
        raise FileNotFoundError(f"Missing embeddings: {emb_path}")
    if not id_map_path.is_file():
        raise FileNotFoundError(f"Missing id map: {id_map_path}")

    vectors = np.load(emb_path).astype(np.float32)
    id_data = json.loads(id_map_path.read_text(encoding="utf-8"))
    shot_ids: list[str] = id_data["shot_ids"]

    if vectors.shape[0] != len(shot_ids):
        raise ValueError(
            f"Row count mismatch: embeddings {vectors.shape[0]} vs id_map {len(shot_ids)}"
        )

    dim = DEFAULT_EMBEDDING_CONFIG.embedding_dim
    if vectors.shape[1] != dim:
        raise ValueError(f"Expected dim {dim}, got {vectors.shape[1]}")

    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = index_path.with_suffix(".tmp.index")
    _write_index_bytes(tmp, index)
    tmp.replace(index_path)

    manifest_path = config.output.embedding_manifest
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {}
    manifest.update({
        "faiss_index": str(index_path),
        "index_built_at": datetime.now(timezone.utc).isoformat(),
        "index_vector_count": len(shot_ids),
    })
    tmp_manifest = manifest_path.with_suffix(".tmp.json")
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    tmp_manifest.replace(manifest_path)

    return IndexBuildResult(
        vector_count=len(shot_ids),
        index_path=index_path,
        id_map_path=id_map_path,
    )


def main(config_path: Path | None = None) -> IndexBuildResult:
    config = load_config(config_path)
    return build_faiss_index(config)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build FAISS index from embeddings")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    result = main(args.config)
    print(json.dumps({"vector_count": result.vector_count, "index": str(result.index_path)}, indent=2))
