"""CLIP text/image encoding for semantic search."""

from __future__ import annotations

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from pipeline.embedding_spec import DEFAULT_EMBEDDING_CONFIG
from pipeline.preprocessing import preprocess_keyframe_pil


def _as_tensor(features) -> torch.Tensor:
    if isinstance(features, torch.Tensor):
        return features
    if hasattr(features, "pooler_output") and features.pooler_output is not None:
        return features.pooler_output
    if hasattr(features, "last_hidden_state"):
        return features.last_hidden_state[:, 0, :]
    raise TypeError(f"Unexpected CLIP feature type: {type(features)}")


def _load_clip(device: str = "cpu") -> tuple[CLIPModel, CLIPProcessor]:
    model_id = DEFAULT_EMBEDDING_CONFIG.image_model.value
    model = CLIPModel.from_pretrained(model_id)
    processor = CLIPProcessor.from_pretrained(model_id)
    model.eval()
    model.to(device)
    return model, processor


def encode_text_query(
    model: CLIPModel,
    processor: CLIPProcessor,
    text: str,
    device: str = "cpu",
) -> torch.Tensor:
    inputs = processor(text=[text], return_tensors="pt", padding=True, truncation=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        feats = _as_tensor(model.get_text_features(**inputs))
    if DEFAULT_EMBEDDING_CONFIG.normalize_embeddings:
        feats = feats / feats.norm(dim=-1, keepdim=True).clamp(min=1e-8)
    return feats.squeeze(0).cpu()


def encode_image_path(
    model: CLIPModel,
    processor: CLIPProcessor,
    image_path: str,
    device: str = "cpu",
) -> torch.Tensor:
    img = preprocess_keyframe_pil(Image.open(image_path).convert("RGB"))
    inputs = processor(images=img, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        feats = _as_tensor(model.get_image_features(**inputs))
    if DEFAULT_EMBEDDING_CONFIG.normalize_embeddings:
        feats = feats / feats.norm(dim=-1, keepdim=True).clamp(min=1e-8)
    return feats.squeeze(0).cpu()
