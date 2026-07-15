"""Background search worker — keeps CLIP encode off the UI thread."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from services.search_api import SearchResponse, SearchService


class SearchWorker(QThread):
    finished_ok = Signal(object)  # SearchResponse
    failed = Signal(str)

    def __init__(
        self,
        service: SearchService,
        mode: str,
        query: str = "",
        shot_id: str = "",
        limit: int = 48,
        offset: int = 0,
        request_id: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self._service = service
        self._mode = mode
        self._query = query
        self._shot_id = shot_id
        self._limit = limit
        self._offset = offset
        self.request_id = request_id

    def run(self) -> None:
        try:
            if self._mode == "similarity":
                resp = self._service.similarity_query(
                    self._shot_id, self._limit, self._offset
                )
            elif self._query.strip():
                resp = self._service.text_query(self._query, self._limit, self._offset)
            else:
                resp = self._service.list_all(self._limit, self._offset)
            self.finished_ok.emit(resp)
        except Exception as exc:
            self.failed.emit(str(exc))
