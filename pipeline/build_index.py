"""FAISS index I/O (Windows-safe path handling)."""

from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np


def read_faiss_index(path: Path) -> faiss.Index:
    data = path.read_bytes()
    return faiss.deserialize_index(np.frombuffer(data, dtype=np.uint8))


def write_faiss_index(index: faiss.Index, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(faiss.serialize_index(index).tobytes())


def build_flat_index(vectors: np.ndarray) -> faiss.Index:
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors.astype(np.float32))
    return index
