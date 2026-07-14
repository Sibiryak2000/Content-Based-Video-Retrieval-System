"""R1 — image preprocessing contract for keyframes before embedding.

R2's keyframes.py writes raw JPEGs at native shot resolution; this module
defines the *only* place where model-specific resizing/normalization
happens, so R2's outputs stay model-agnostic (per data_pipeline contract).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.embedding_spec import DEFAULT_EMBEDDING_CONFIG


def load_and_preprocess(jpeg_path: Path) -> np.ndarray:
    """Load a keyframe JPEG and return a CHW float32 array normalized
    per the CLIP preprocessing stats. Ready for Phase 3 encoder input."""
    cfg = DEFAULT_EMBEDDING_CONFIG
    img = Image.open(jpeg_path).convert("RGB")
    img = img.resize((cfg.image_size, cfg.image_size), Image.BICUBIC)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    mean = np.array(cfg.mean, dtype=np.float32)
    std = np.array(cfg.std, dtype=np.float32)
    arr = (arr - mean) / std
    return arr.transpose(2, 0, 1)  # HWC -> CHW


def validate_keyframe_readable(jpeg_path: Path) -> bool:
    """R1 sanity check used in the Phase 2 review of R2's outputs."""
    try:
        with Image.open(jpeg_path) as img:
            img.verify()
        return True
    except Exception:
        return False


def is_placeholder_keyframe(jpeg_path: Path) -> bool:
    """Detect gray placeholder JPEGs written for corrupt video segments."""
    try:
        arr = np.asarray(Image.open(jpeg_path).convert("RGB"), dtype=np.float32)
    except Exception:
        return True
    if arr.std() < 5.0 and arr.mean() < 60.0:
        return True
    return False
