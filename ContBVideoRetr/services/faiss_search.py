"""FAISS-backed semantic search (loads existing Phase 3 index artifacts)."""

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
from pipeline.db.store import MetadataStore  # noqa: E402
from pipeline.embeddings import _load_clip, encode_text_query  # noqa: E402
from pipeline.reranker import RankedCandidate, rerank_candidates  # noqa: E402

from models.result_item import ResultItem  # noqa: E402
from services.catalog_client import _dict_to_result_item  # noqa: E402
from services.search_api import SearchResponse  # noqa: E402

PROCESSED = REPO_ROOT / "data" / "processed"


class FaissSearchService:
    def __init__(self):
        self._store = MetadataStore(PROCESSED / "metadata.db", REPO_ROOT)
        self._index = read_faiss_index(PROCESSED / "faiss.index")
        id_data = json.loads((PROCESSED / "faiss_id_map.json").read_text(encoding="utf-8"))
        self._shot_ids: list[str] = id_data["shot_ids"]
        self._id_to_row = {sid: i for i, sid in enumerate(self._shot_ids)}
        self._vectors = np.load(PROCESSED / "embeddings.npy").astype(np.float32)
        self._clip_model = None
        self._clip_processor = None
        self._device = "cpu"

    @property
    def source_label(self) -> str:
        return "semantic search (FAISS + CLIP)"

    @property
    def vector_count(self) -> int:
        return len(self._shot_ids)

    def index_status_label(self) -> str:
        manifest_path = PROCESSED / "embedding_manifest.json"
        model_short = "CLIP ViT-B/32"
        if manifest_path.is_file():
            raw = json.loads(manifest_path.read_text(encoding="utf-8")).get("model", "")
            if "clip-vit-base-patch32" in raw.lower():
                model_short = "CLIP ViT-B/32"
            elif raw:
                model_short = raw.rsplit("/", 1)[-1]
        return f"Index: {len(self._shot_ids):,} vectors · {model_short}"

    def _ensure_clip(self) -> None:
        if self._clip_model is None:
            device = self._device
            if device == "cuda" and not __import__("torch").cuda.is_available():
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

        if q.isdigit():
            return self._numeric_hybrid_query(q, limit, offset)

        t0 = time.perf_counter()
        self._ensure_clip()
        text_vec = encode_text_query(
            self._clip_model, self._clip_processor, q, self._device
        ).numpy().reshape(1, -1).astype(np.float32)

        k = min(offset + limit, len(self._shot_ids))
        scores, indices = self._index.search(text_vec, k)
        hits = [(int(indices[0][i]), float(scores[0][i])) for i in range(k)]
        page_hits = hits[offset : offset + limit]

        shot_ids = [self._shot_ids[row] for row, _ in page_hits]
        score_map = {self._shot_ids[row]: score for row, score in page_hits}
        items = self._hydrate_ranked(q, shot_ids, score_map)

        return SearchResponse(
            items=items, total=len(self._shot_ids), page_size=limit, offset=offset,
            query=q, latency_ms=(time.perf_counter() - t0) * 1000, mode="semantic",
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
        shot_ids = [self._shot_ids[r] for r, _ in page_hits]
        score_map = {self._shot_ids[r]: s for r, s in page_hits}
        items = self._hydrate(shot_ids, score_map)

        return SearchResponse(
            items=items, total=max(len(self._shot_ids) - 1, 0),
            page_size=limit, offset=offset, query=f"similar:{shot_id}",
            latency_ms=(time.perf_counter() - t0) * 1000, mode="similarity",
        )

    def _numeric_hybrid_query(self, q: str, limit: int, offset: int) -> SearchResponse:
        """Numeric query (e.g. "00058"): exact/prefix video_id catalog matches
        first, then fill remaining page slots with CLIP semantic matches
        (in case the digits are meaningful visual content, e.g. a number
        printed on a jersey or sign) — excluding shots already shown."""
        from services.search_api import BrowseOnlySearchService

        t0 = time.perf_counter()
        catalog_svc = BrowseOnlySearchService()

        catalog_resp = catalog_svc.text_query(q, limit=offset + limit, offset=0)
        catalog_items = catalog_resp.items
        catalog_total = catalog_resp.total
        shown_ids = {it.shot_id for it in catalog_items}

        remaining = max(0, (offset + limit) - len(catalog_items))
        semantic_items: list[ResultItem] = []
        if remaining > 0:
            self._ensure_clip()
            text_vec = encode_text_query(
                self._clip_model, self._clip_processor, q, self._device
            ).numpy().reshape(1, -1).astype(np.float32)

            fetch_k = min(remaining + len(shown_ids) + 20, len(self._shot_ids))
            scores, indices = self._index.search(text_vec, fetch_k)
            hits = [
                (int(indices[0][i]), float(scores[0][i]))
                for i in range(fetch_k)
                if self._shot_ids[int(indices[0][i])] not in shown_ids
            ]
            picked = hits[:remaining]
            shot_ids = [self._shot_ids[row] for row, _ in picked]
            score_map = {self._shot_ids[row]: score for row, score in picked}
            semantic_items = self._hydrate(shot_ids, score_map)

        combined = catalog_items + semantic_items
        page_items = combined[offset: offset + limit]

        # Only label this page "hybrid" if semantic fallback actually
        # contributed results to it; pure catalog matches should read
        # as a plain filter, matching what really happened.
        page_used_semantic = any(it in semantic_items for it in page_items)
        mode = "hybrid" if page_used_semantic else "filter"

        return SearchResponse(
            items=page_items,
            total=catalog_total + len(self._shot_ids) if semantic_items or page_used_semantic else catalog_total,
            page_size=limit, offset=offset, query=q,
            latency_ms=(time.perf_counter() - t0) * 1000,
            mode=mode,
        )

    def _hydrate(
        self, shot_ids: list[str], score_map: dict[str, float]
    ) -> list[ResultItem]:
        shots = self._store.get_shots_by_ids(shot_ids)
        return [
            _dict_to_result_item(
                self._store.to_result_item(s, score=score_map.get(s.shot_id, 0.0))
            )
            for s in shots
        ]

    def _hydrate_ranked(self, query: str, shot_ids: list[str], score_map: dict[str, float]) -> list[ResultItem]:
        """Like _hydrate, but applies R1's lexical-overlap re-ranking (Phase 4)
        on top of the raw CLIP similarity before returning results."""
        shots = self._store.get_shots_by_ids(shot_ids)
        candidates = [
            RankedCandidate(
                shot_id=s.shot_id,
                clip_score=score_map.get(s.shot_id, 0.0),
                description=s.vimeo_description,
            )
            for s in shots
        ]
        ranked = rerank_candidates(query, candidates)
        by_id = {s.shot_id: s for s in shots}
        return [
            _dict_to_result_item(self._store.to_result_item(by_id[c.shot_id], score=c.clip_score))
            for c in ranked
        ]


def faiss_index_available() -> bool:
    return all(
        (PROCESSED / name).is_file()
        for name in ("faiss.index", "faiss_id_map.json", "embeddings.npy", "metadata.db")
    )


def index_status_label() -> str:
    if not faiss_index_available():
        return "Index: unavailable (browse-only)"
    try:
        return FaissSearchService().index_status_label()
    except Exception:
        return "Index: error loading artifacts"
