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
    img = preprocess_keyframe_pil(Image.open(jpeg_path).convert("RGB"))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    mean = np.array(cfg.mean, dtype=np.float32)
    std = np.array(cfg.std, dtype=np.float32)
    arr = (arr - mean) / std
    return arr.transpose(2, 0, 1)


def preprocess_keyframe_pil(img: Image.Image) -> Image.Image:
    """Resize PIL image to model input size (CLIP 224x224)."""
    cfg = DEFAULT_EMBEDDING_CONFIG
    return img.resize((cfg.image_size, cfg.image_size), Image.BICUBIC)


def validate_keyframe_readable(jpeg_path: Path) -> bool:
    """R1 sanity check used in the Phase 2 review of R2's outputs."""
    try:
        with Image.open(jpeg_path) as img:
            img.verify()
        return True
    except Exception:
        return False
