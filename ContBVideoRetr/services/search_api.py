"""R3 — internal search-service API contract."""

from __future__ import annotations

import time
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
    mode: str = "browse"


class SearchService(Protocol):
    @property
    def source_label(self) -> str: ...

    def text_query(self, query: str, limit: int, offset: int) -> SearchResponse: ...
    def similarity_query(self, shot_id: str, limit: int, offset: int) -> SearchResponse: ...
    def list_all(self, limit: int, offset: int) -> SearchResponse: ...


class BrowseOnlySearchService:
    def __init__(self, catalog: CatalogClient | None = None):
        self._catalog = catalog or create_catalog_client()

    @property
    def source_label(self) -> str:
        return self._catalog.source_label

    def text_query(self, query: str, limit: int = 48, offset: int = 0) -> SearchResponse:
        t0 = time.perf_counter()
        items = self._catalog.list_shots(limit=limit, offset=offset, query=query)
        total = self._catalog.count_shots(query=query)
        mode = "filter" if query.strip() else "browse"
        return SearchResponse(
            items=items, total=total, page_size=limit, offset=offset,
            query=query, latency_ms=(time.perf_counter() - t0) * 1000, mode=mode,
        )

    def list_all(self, limit: int = 48, offset: int = 0) -> SearchResponse:
        return self.text_query("", limit, offset)

    def similarity_query(self, shot_id: str, limit: int = 48, offset: int = 0) -> SearchResponse:
        raise NotImplementedError(
            "Similarity search requires the FAISS index."
        )


def create_search_service() -> SearchService:
    from services.faiss_search import FaissSearchService, faiss_index_available

    if faiss_index_available():
        return FaissSearchService()
    return BrowseOnlySearchService()
