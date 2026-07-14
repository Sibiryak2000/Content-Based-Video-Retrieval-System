"""Batch-encode keyframe JPEGs with CLIP ViT-B/32."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from pipeline.config import PipelineConfig, load_config
from pipeline.db.store import MetadataStore
from pipeline.embedding_spec import DEFAULT_EMBEDDING_CONFIG
from pipeline.preprocessing import is_placeholder_keyframe, validate_keyframe_readable


@dataclass
class EmbeddingBuildResult:
    vector_count: int
    excluded_shots: list[str]
    embeddings_path: Path
    id_map_path: Path
    manifest_path: Path


def _load_clip(device: str) -> tuple[CLIPModel, CLIPProcessor]:
    model_name = DEFAULT_EMBEDDING_CONFIG.image_model.value
    processor = CLIPProcessor.from_pretrained(model_name)
    model = CLIPModel.from_pretrained(model_name)
    model.eval()
    model.to(device)
    return model, processor


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (vectors / norms).astype(np.float32)


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


def _encode_image_batch(
    model: CLIPModel,
    processor: CLIPProcessor,
    paths: list[Path],
    device: str,
) -> np.ndarray:
    images = [Image.open(p).convert("RGB") for p in paths]
    inputs = processor(images=images, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        feats = _as_tensor(model.get_image_features(**inputs))
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy().astype(np.float32)


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


def collect_indexable_shots(
    store: MetadataStore,
    config: PipelineConfig,
    video_ids: list[str] | None = None,
) -> tuple[list[str], list[Path], list[str]]:
    """Return (shot_ids, keyframe_paths, excluded_shot_ids)."""
    shot_ids: list[str] = []
    paths: list[Path] = []
    excluded: list[str] = []

    if video_ids:
        for vid in video_ids:
            for shot in store.list_shots_for_video(vid):
                _maybe_add(shot.shot_id, shot.keyframe_path, config, shot_ids, paths, excluded)
    else:
        offset = 0
        batch = 500
        while True:
            rows = store.list_shots(limit=batch, offset=offset)
            if not rows:
                break
            for shot in rows:
                _maybe_add(shot.shot_id, shot.keyframe_path, config, shot_ids, paths, excluded)
            offset += batch

    return shot_ids, paths, excluded


def _maybe_add(
    shot_id: str,
    keyframe_rel: str | None,
    config: PipelineConfig,
    shot_ids: list[str],
    paths: list[Path],
    excluded: list[str],
) -> None:
    if not keyframe_rel:
        excluded.append(shot_id)
        return
    path = config.repo_root / keyframe_rel
    if not path.is_file():
        excluded.append(shot_id)
        return
    if not validate_keyframe_readable(path):
        excluded.append(shot_id)
        return
    if is_placeholder_keyframe(path):
        excluded.append(shot_id)
        return
    shot_ids.append(shot_id)
    paths.append(path)


def build_embeddings(
    config: PipelineConfig,
    store: MetadataStore,
    video_ids: list[str] | None = None,
    *,
    skip_if_unchanged: bool = True,
) -> EmbeddingBuildResult:
    shot_ids, paths, excluded = collect_indexable_shots(store, config, video_ids)
    if not shot_ids:
        raise RuntimeError("No indexable keyframes found")

    manifest_path = config.output.embedding_manifest
    if skip_if_unchanged and _embeddings_up_to_date(config, shot_ids, excluded):
        return EmbeddingBuildResult(
            vector_count=len(shot_ids),
            excluded_shots=excluded,
            embeddings_path=config.output.embeddings_path,
            id_map_path=config.output.faiss_id_map,
            manifest_path=manifest_path,
        )

    device = config.embedding.device
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    model, processor = _load_clip(device)
    batch_size = config.embedding.batch_size
    vectors: list[np.ndarray] = []

    for i in range(0, len(paths), batch_size):
        batch_paths = paths[i : i + batch_size]
        vectors.append(_encode_image_batch(model, processor, batch_paths, device))
        print(f"  encoded {min(i + batch_size, len(paths))}/{len(paths)}", flush=True)

    matrix = _normalize(np.vstack(vectors))
    _write_atomic(config.output.embeddings_path, matrix)
    _write_json_atomic(
        config.output.faiss_id_map,
        {"shot_ids": shot_ids},
    )
    manifest = {
        "model": DEFAULT_EMBEDDING_CONFIG.image_model.value,
        "embedding_dim": DEFAULT_EMBEDDING_CONFIG.embedding_dim,
        "similarity_metric": DEFAULT_EMBEDDING_CONFIG.similarity_metric.value,
        "vector_count": len(shot_ids),
        "excluded_shots": excluded,
        "excluded_count": len(excluded),
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json_atomic(manifest_path, manifest)

    return EmbeddingBuildResult(
        vector_count=len(shot_ids),
        excluded_shots=excluded,
        embeddings_path=config.output.embeddings_path,
        id_map_path=config.output.faiss_id_map,
        manifest_path=manifest_path,
    )


def _embeddings_up_to_date(
    config: PipelineConfig,
    shot_ids: list[str],
    excluded: list[str],
) -> bool:
    emb = config.output.embeddings_path
    id_map = config.output.faiss_id_map
    manifest = config.output.embedding_manifest
    if not (emb.is_file() and id_map.is_file() and manifest.is_file()):
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        stored_ids = json.loads(id_map.read_text(encoding="utf-8"))["shot_ids"]
        return (
            stored_ids == shot_ids
            and data.get("excluded_shots") == excluded
            and data.get("vector_count") == len(shot_ids)
        )
    except (json.JSONDecodeError, KeyError, OSError):
        return False


def _write_atomic(path: Path, matrix: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npy")
    np.save(tmp, matrix)
    tmp.replace(path)


def _write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def main(config_path: Path | None = None, video_ids: list[str] | None = None) -> EmbeddingBuildResult:
    config = load_config(config_path)
    store = MetadataStore(config.output.db_path, config.repo_root)
    return build_embeddings(config, store, video_ids=video_ids)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build CLIP embeddings for keyframes")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--video-id", action="append", dest="video_ids")
    args = parser.parse_args()
    result = main(args.config, video_ids=args.video_ids)
    print(json.dumps({"vector_count": result.vector_count, "excluded": len(result.excluded_shots)}, indent=2))
