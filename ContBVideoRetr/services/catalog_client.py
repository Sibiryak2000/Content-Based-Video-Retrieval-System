"""Catalog access for the GUI — reads processed shots from metadata.db."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Protocol

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.config import load_config  # noqa: E402
from pipeline.db.store import MetadataStore  # noqa: E402

from mock.mock_data import get_mock_results  # noqa: E402
from models.result_item import ResultItem  # noqa: E402


class CatalogClient(Protocol):
    def list_shots(self, limit: int, offset: int, query: str = "") -> list[ResultItem]: ...
    def count_shots(self, query: str = "") -> int: ...
    @property
    def is_available(self) -> bool: ...
    @property
    def source_label(self) -> str: ...


def _dict_to_result_item(d: dict) -> ResultItem:
    return ResultItem(
        video_id=d["video_id"],
        shot_id=d.get("shot_id", ""),
        title=d.get("title", d["video_id"]),
        keyframe_path=d.get("keyframe_path"),
        proxy_path=d.get("proxy_path"),
        start_frame=int(d.get("start_frame", 0)),
        end_frame=int(d.get("end_frame", 0)),
        fps=float(d.get("fps", 25.0)),
        score=float(d.get("score", 0.0)),
        text=d.get("text"),
    )


class SqliteCatalogClient:
    def __init__(self, config_path: Path | None = None):
        self._config = load_config(config_path or (REPO_ROOT / "config.yaml"))
        self._store = MetadataStore(self._config.output.db_path, self._config.repo_root)

    @property
    def is_available(self) -> bool:
        return self._config.output.db_path.is_file()

    @property
    def source_label(self) -> str:
        return "catalog (metadata.db)"

    def list_shots(self, limit: int, offset: int, query: str = "") -> list[ResultItem]:
        if not self.is_available:
            return []
        rows = self._store.list_shots(limit=limit, offset=offset, query=query)
        return [_dict_to_result_item(self._store.to_result_item(r)) for r in rows]

    def count_shots(self, query: str = "") -> int:
        if not self.is_available:
            return 0
        return self._store.count_shots(query=query)


class MockCatalogClient:
    @property
    def is_available(self) -> bool:
        return True

    @property
    def source_label(self) -> str:
        return "mock fallback"

    def list_shots(self, limit: int, offset: int, query: str = "") -> list[ResultItem]:
        items = get_mock_results(query)
        return items[offset: offset + limit]

    def count_shots(self, query: str = "") -> int:
        return len(get_mock_results(query))


def create_catalog_client(config_path: Path | None = None) -> CatalogClient:
    client = SqliteCatalogClient(config_path)
    if client.is_available and client.count_shots() > 0:
        return client
    return MockCatalogClient()
