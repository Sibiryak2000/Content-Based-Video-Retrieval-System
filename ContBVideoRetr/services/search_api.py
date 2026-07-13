"""R3 — internal search-service API contract (drafted Phase 1, browse-only
stub for Phase 2; real text/similarity search wired in Phase 3 once R1's
embeddings + R2's FAISS index exist).

This is the ONE interface the GUI (R4) is allowed to depend on — swapping
the backend behind it (browse-only now, FAISS-backed later) requires no
GUI changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from models.result_item import ResultItem
from services.catalog_client import CatalogClient, create_catalog_client


@dataclass
class SearchResponse:
    items: list[ResultItem]
    total: int
    page_size: int
    offset: int
    query: str
    latency_ms: float = 0.0


class SearchService(Protocol):
    def text_query(self, query: str, limit: int, offset: int) -> SearchResponse: ...
    def similarity_query(self, shot_id: str, limit: int) -> SearchResponse: ...
    def list_all(self, limit: int, offset: int) -> SearchResponse: ...


class BrowseOnlySearchService:
    """Phase 1-2 implementation: text_query degrades to a video_id/description
    prefix filter on the catalog (no semantic search yet). similarity_query
    is not yet available and raises NotImplementedError until Phase 3."""

    def __init__(self, catalog: CatalogClient | None = None):
        self._catalog = catalog or create_catalog_client()

    def text_query(self, query: str, limit: int = 48, offset: int = 0) -> SearchResponse:
        import time
        t0 = time.perf_counter()
        items = self._catalog.list_shots(limit=limit, offset=offset, query=query)
        total = self._catalog.count_shots(query=query)
        return SearchResponse(
            items=items, total=total, page_size=limit, offset=offset,
            query=query, latency_ms=(time.perf_counter() - t0) * 1000,
        )

    def list_all(self, limit: int = 48, offset: int = 0) -> SearchResponse:
        return self.text_query("", limit, offset)

    def similarity_query(self, shot_id: str, limit: int = 48) -> SearchResponse:
        raise NotImplementedError(
            "Similarity search requires the FAISS index — deferred to Phase 3."
        )


def create_search_service() -> SearchService:
    return BrowseOnlySearchService()
