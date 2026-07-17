"""R1 — Visual Question Answering (VQA) inference for retrieved shots.

Phase 3: given a natural-language question and a candidate shot's keyframe,
produce a short free-text answer using a pretrained VQA model (BLIP) — no
training required, consistent with the assignment's "inference only" scope.
Used by services/vqa_service.py (R3) to fill ResultItem.text before the
shot is submitted to DRES.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch
from PIL import Image
from transformers import BlipForQuestionAnswering, BlipProcessor

_MODEL_ID = "Salesforce/blip-vqa-base"

_model: BlipForQuestionAnswering | None = None
_processor: BlipProcessor | None = None
_device = "cpu"


@dataclass
class VqaAnswer:
    question: str
    answer: str
    shot_id: str


def _ensure_loaded(device: str = "cpu") -> None:
    global _model, _processor, _device
    if _model is None:
        _processor = BlipProcessor.from_pretrained(_MODEL_ID)
        _model = BlipForQuestionAnswering.from_pretrained(_MODEL_ID)
        _model.eval()
        _model.to(device)
        _device = device


def answer_question(image_path: str | Path, question: str, device: str = "cpu") -> str:
    """Generate a short free-text answer for `question` about the given image."""
    _ensure_loaded(device)
    img = Image.open(image_path).convert("RGB")
    inputs = _processor(images=img, text=question, return_tensors="pt").to(_device)
    with torch.no_grad():
        out_ids = _model.generate(**inputs, max_new_tokens=16)
    return _processor.decode(out_ids[0], skip_special_tokens=True).strip()


def answer_for_shot(keyframe_path: str | Path, shot_id: str, question: str, device: str = "cpu") -> VqaAnswer:
    return VqaAnswer(question=question, answer=answer_question(keyframe_path, question, device), shot_id=shot_id)
