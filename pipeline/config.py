"""Load and resolve pipeline configuration paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class DatasetConfig:
    videos_dir: Path
    scenes_zip: Path
    scenes_prefix: str


@dataclass
class OutputConfig:
    root: Path
    proxies_dir: Path
    keyframes_dir: Path
    db_path: Path
    inventory_report: Path
    embeddings_path: Path
    faiss_index: Path
    faiss_id_map: Path
    embedding_manifest: Path


@dataclass
class EmbeddingRunConfig:
    batch_size: int = 32
    device: str = "cpu"


@dataclass
class PrototypeConfig:
    sample_video_ids: List[str] = field(default_factory=list)
    proxy_height: int = 270
    keyframe_strategy: str = "mid_frame"


@dataclass
class GuiConfig:
    page_size: int = 48


@dataclass
class PipelineConfig:
    dataset: DatasetConfig
    output: OutputConfig
    prototype: PrototypeConfig
    embedding: EmbeddingRunConfig = field(default_factory=EmbeddingRunConfig)
    gui: GuiConfig = field(default_factory=GuiConfig)
    repo_root: Path = REPO_ROOT

    def ensure_output_dirs(self) -> None:
        self.output.root.mkdir(parents=True, exist_ok=True)
        self.output.proxies_dir.mkdir(parents=True, exist_ok=True)
        self.output.keyframes_dir.mkdir(parents=True, exist_ok=True)


def _resolve(path_str: str, repo_root: Path) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def load_config(config_path: Path | None = None) -> PipelineConfig:
    config_path = config_path or (REPO_ROOT / "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    repo_root = config_path.resolve().parent
    ds = raw["dataset"]
    out = raw["output"]
    proto = raw.get("prototype", {})
    gui = raw.get("gui", {})
    emb = raw.get("embedding", {})

    return PipelineConfig(
        dataset=DatasetConfig(
            videos_dir=_resolve(ds["videos_dir"], repo_root),
            scenes_zip=_resolve(ds["scenes_zip"], repo_root),
            scenes_prefix=ds["scenes_prefix"],
        ),
        output=OutputConfig(
            root=_resolve(out["root"], repo_root),
            proxies_dir=_resolve(out["proxies_dir"], repo_root),
            keyframes_dir=_resolve(out["keyframes_dir"], repo_root),
            db_path=_resolve(out["db_path"], repo_root),
            inventory_report=_resolve(out["inventory_report"], repo_root),
            embeddings_path=_resolve(out["embeddings_path"], repo_root),
            faiss_index=_resolve(out["faiss_index"], repo_root),
            faiss_id_map=_resolve(out["faiss_id_map"], repo_root),
            embedding_manifest=_resolve(out["embedding_manifest"], repo_root),
        ),
        prototype=PrototypeConfig(
            sample_video_ids=list(proto.get("sample_video_ids", [])),
            proxy_height=int(proto.get("proxy_height", 270)),
            keyframe_strategy=str(proto.get("keyframe_strategy", "mid_frame")),
        ),
        embedding=EmbeddingRunConfig(
            batch_size=int(emb.get("batch_size", 32)),
            device=str(emb.get("device", "cpu")),
        ),
        gui=GuiConfig(page_size=int(gui.get("page_size", 48))),
        repo_root=repo_root,
    )
