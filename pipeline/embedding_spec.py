"""R1 — model/embedding architecture spec (Phase 1-2).

Defines which vision-language model(s) will be used in Phase 3, the
similarity metric, and the image preprocessing contract that keyframes
must satisfy. Does NOT run inference yet (that's Phase 3) — this module
is the shared contract R2's keyframes already conform to and R1 will
consume when building embeddings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class ModelName(str, Enum):
    CLIP_VIT_B32 = "openai/clip-vit-base-patch32"
    CLIP_VIT_L14 = "openai/clip-vit-large-patch14"
    SIGLIP_BASE = "google/siglip-base-patch16-224"


class SimilarityMetric(str, Enum):
    COSINE = "cosine"
    DOT = "dot_product"


@dataclass(frozen=True)
class EmbeddingConfig:
    """Locked-in Phase 1 decision, consumed by R1's Phase 3 encoder module
    and by R2's FAISS index builder."""

    text_model: ModelName = ModelName.CLIP_VIT_B32
    image_model: ModelName = ModelName.CLIP_VIT_B32
    embedding_dim: int = 512          # CLIP ViT-B/32 output dim
    similarity_metric: SimilarityMetric = SimilarityMetric.COSINE
    normalize_embeddings: bool = True  # required for cosine via dot product
    image_size: int = 224
    # CLIP's published preprocessing stats
    mean: tuple = (0.48145466, 0.4578275, 0.40821073)
    std: tuple = (0.26862954, 0.26130258, 0.27577711)


@dataclass(frozen=True)
class KeyframePolicy:
    """Policy R1 hands to R2's keyframes.py. Phase 1-2 uses `mid_frame`
    (already implemented). `multi_frame` is reserved for Phase 3 if a
    shot's visual variance is high (e.g. fast pans, cuts inside a shot)."""

    strategy: str = "mid_frame"          # matches config.yaml prototype.keyframe_strategy
    max_frames_per_shot: int = 1
    min_shot_length_for_multiframe: int = 75  # ~3s at 25fps


DEFAULT_EMBEDDING_CONFIG = EmbeddingConfig()
DEFAULT_KEYFRAME_POLICY = KeyframePolicy()


def describe() -> str:
    cfg = DEFAULT_EMBEDDING_CONFIG
    return (
        f"Image/Text model: {cfg.image_model.value} | "
        f"dim={cfg.embedding_dim} | metric={cfg.similarity_metric.value} | "
        f"keyframe policy={DEFAULT_KEYFRAME_POLICY.strategy}"
    )
