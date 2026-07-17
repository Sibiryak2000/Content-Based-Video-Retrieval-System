"""R3 — VQA-aware retrieval service (Phase 3-4).

Decorates the existing FAISS text search (services/faiss_search.py) with
R1's BLIP VQA answerer, so a question-style query returns ranked shots
*and* a short free-text answer per shot in ResultItem.text — ready to go
straight into DresSubmitPayload.text on submit.

Implements the full SearchService protocol (text_query/list_all/
similarity_query) so it's a drop-in replacement for create_search_service()
in the GUI — SearchWorker needs no changes.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.query_router import QueryMode, build_request  # noqa: E402
from pipeline.vqa import answer_question  # noqa: E402
from services.search_api import SearchResponse, SearchService  # noqa: E402

logger = logging.getLogger(__name__)

VQA_ANSWER_TOP_K = 3  # BLIP is slow on CPU (~1-2s/image); only answer top candidates


class VqaSearchService:
    """Decorates any SearchService with VQA answer generation.

    Drop-in replacement for the plain SearchService: text_query() itself
    auto-detects KIS vs VQA phrasing (Phase 3 requirement — a single search
    bar serving both query types) and only pays the BLIP inference cost
    when a question is actually detected.
    """

    def __init__(self, base_service: SearchService, device: str = "cpu"):
        self._base = base_service
        self._device = device

    @property
    def source_label(self) -> str:
        return f"{self._base.source_label} + VQA (BLIP)"

    def answer_query(self, query: str, limit: int = 48, offset: int = 0) -> SearchResponse:
        """Run retrieval, then attach a short answer to the top candidates."""
        request = build_request(query, explicit_mode=QueryMode.VQA)
        response = self._base.text_query(request.raw_query, limit, offset)
        for item in response.items[:VQA_ANSWER_TOP_K]:
            if not item.keyframe_path:
                continue
            try:
                item.text = answer_question(item.keyframe_path, request.question, self._device)
            except Exception as exc:  # pretrained-model inference must never crash the GUI
                logger.warning("VQA answer failed for %s: %s", item.shot_id, exc)
        return response

    def text_query(self, query: str, limit: int = 48, offset: int = 0) -> SearchResponse:
        """SearchService-protocol entry point: auto-routes KIS vs VQA."""
        if not query.strip():
            return self._base.text_query(query, limit, offset)
        if build_request(query).mode == QueryMode.VQA:
            return self.answer_query(query, limit, offset)
        return self._base.text_query(query, limit, offset)

    def list_all(self, limit: int = 48, offset: int = 0) -> SearchResponse:
        return self._base.list_all(limit, offset)

    def similarity_query(self, shot_id: str, limit: int = 48, offset: int = 0) -> SearchResponse:
        return self._base.similarity_query(shot_id, limit, offset)

    # Kept for explicit callers (e.g. verify_vqa.py) that want VQA mode
    # regardless of query phrasing.
    def route_query(self, query: str, limit: int = 48, offset: int = 0) -> SearchResponse:
        if build_request(query).mode == QueryMode.VQA:
            return self.answer_query(query, limit, offset)
        return self._base.text_query(query, limit, offset)


def create_vqa_service(base_service: SearchService | None = None) -> VqaSearchService:
    from services.search_api import create_search_service

    return VqaSearchService(base_service or create_search_service())
