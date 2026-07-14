"""FAISS-backed semantic search service (R3 implementation for Phase 3)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.build_index import read_faiss_index  # noqa: E402
from pipeline.config import PipelineConfig, load_config  # noqa: E402
from pipeline.db.store import MetadataStore  # noqa: E402
from pipeline.embeddings import _load_clip, encode_text_query  # noqa: E402

from models.result_item import ResultItem  # noqa: E402
from services.catalog_client import _dict_to_result_item  # noqa: E402
from services.search_api import SearchResponse  # noqa: E402


class FaissSearchService:
    def __init__(self, config: PipelineConfig | None = None):
        self._config = config or load_config(REPO_ROOT / "config.yaml")
        self._store = MetadataStore(
            self._config.output.db_path, self._config.repo_root
        )
        self._index = read_faiss_index(self._config.output.faiss_index)
        id_data = json.loads(
            self._config.output.faiss_id_map.read_text(encoding="utf-8")
        )
        self._shot_ids: list[str] = id_data["shot_ids"]
        self._id_to_row = {sid: i for i, sid in enumerate(self._shot_ids)}
        self._vectors = np.load(self._config.output.embeddings_path).astype(np.float32)
        self._clip_model = None
        self._clip_processor = None
        self._device = self._config.embedding.device

    @property
    def source_label(self) -> str:
        return "semantic search (FAISS + CLIP)"

    def _ensure_clip(self) -> None:
        if self._clip_model is None:
            import torch

            device = self._device
            if device == "cuda" and not torch.cuda.is_available():
                device = "cpu"
            self._device = device
            self._clip_model, self._clip_processor = _load_clip(device)

    def list_all(self, limit: int = 48, offset: int = 0) -> SearchResponse:
        from services.search_api import BrowseOnlySearchService

        return BrowseOnlySearchService().list_all(limit, offset)

    def text_query(self, query: str, limit: int = 48, offset: int = 0) -> SearchResponse:
        q = query.strip()
        if not q:
            return self.list_all(limit, offset)

        t0 = time.perf_counter()
        self._ensure_clip()
        text_vec = encode_text_query(
            self._clip_model, self._clip_processor, q, self._device
        ).reshape(1, -1).astype(np.float32)

        k = min(offset + limit, len(self._shot_ids))
        scores, indices = self._index.search(text_vec, k)
        hits = [(int(indices[0][i]), float(scores[0][i])) for i in range(k)]
        page_hits = hits[offset : offset + limit]

        shot_ids = [self._shot_ids[row] for row, _ in page_hits]
        score_map = {self._shot_ids[row]: score for row, score in page_hits}
        items = self._hydrate(shot_ids, score_map)

        return SearchResponse(
            items=items,
            total=len(self._shot_ids),
            page_size=limit,
            offset=offset,
            query=q,
            latency_ms=(time.perf_counter() - t0) * 1000,
            mode="semantic",
        )

    def similarity_query(
        self, shot_id: str, limit: int = 48, offset: int = 0
    ) -> SearchResponse:
        t0 = time.perf_counter()
        row = self._id_to_row.get(shot_id)
        if row is None:
            return SearchResponse(
                items=[], total=0, page_size=limit, offset=offset,
                query=f"similar:{shot_id}", latency_ms=0.0, mode="similarity",
            )

        vec = self._vectors[row : row + 1]
        fetch_k = min(offset + limit + 5, len(self._shot_ids))
        scores, indices = self._index.search(vec, fetch_k)

        hits: list[tuple[int, float]] = []
        for i in range(fetch_k):
            idx = int(indices[0][i])
            if self._shot_ids[idx] == shot_id:
                continue
            hits.append((idx, float(scores[0][i])))

        page_hits = hits[offset : offset + limit]
        shot_ids = [self._shot_ids[row] for row, _ in page_hits]
        score_map = {self._shot_ids[row]: score for row, score in page_hits}
        items = self._hydrate(shot_ids, score_map)

        return SearchResponse(
            items=items,
            total=max(len(self._shot_ids) - 1, 0),
            page_size=limit,
            offset=offset,
            query=f"similar:{shot_id}",
            latency_ms=(time.perf_counter() - t0) * 1000,
            mode="similarity",
        )

    def _hydrate(
        self, shot_ids: list[str], score_map: dict[str, float]
    ) -> list[ResultItem]:
        shots = self._store.get_shots_by_ids(shot_ids)
        items: list[ResultItem] = []
        for shot in shots:
            d = self._store.to_result_item(
                shot, score=score_map.get(shot.shot_id, 0.0)
            )
            items.append(_dict_to_result_item(d))
        return items


def faiss_index_available(config: PipelineConfig | None = None) -> bool:
    cfg = config or load_config(REPO_ROOT / "config.yaml")
    return (
        cfg.output.faiss_index.is_file()
        and cfg.output.faiss_id_map.is_file()
        and cfg.output.embeddings_path.is_file()
    )
