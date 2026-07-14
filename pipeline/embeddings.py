"""CLIP text/image encoding for FAISS search (Phase 3/4)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from pipeline.embedding_spec import DEFAULT_EMBEDDING_CONFIG


def _load_clip(device: str) -> tuple[CLIPModel, CLIPProcessor]:
    model_name = DEFAULT_EMBEDDING_CONFIG.image_model.value
    processor = CLIPProcessor.from_pretrained(model_name)
    model = CLIPModel.from_pretrained(model_name)
    model.eval()
    model.to(device)
    return model, processor


def _as_tensor(feats: torch.Tensor | object) -> torch.Tensor:
    if isinstance(feats, torch.Tensor):
        return feats
    if hasattr(feats, "pooler_output") and feats.pooler_output is not None:
        return feats.pooler_output
    if hasattr(feats, "image_embeds"):
        return feats.image_embeds
    if hasattr(feats, "text_embeds"):
        return feats.text_embeds
    raise TypeError(f"Unexpected CLIP feature type: {type(feats)}")


def encode_text_query(
    model: CLIPModel,
    processor: CLIPProcessor,
    query: str,
    device: str = "cpu",
) -> np.ndarray:
    inputs = processor(text=[query], return_tensors="pt", padding=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        feats = _as_tensor(model.get_text_features(**inputs))
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy().astype(np.float32).reshape(-1)
