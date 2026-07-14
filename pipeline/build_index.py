"""FAISS index I/O helpers (Cyrillic-path safe on Windows)."""

from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np


def read_faiss_index(path: Path) -> faiss.Index:
    raw = path.read_bytes()
    return faiss.deserialize_index(np.frombuffer(raw, dtype=np.uint8))
