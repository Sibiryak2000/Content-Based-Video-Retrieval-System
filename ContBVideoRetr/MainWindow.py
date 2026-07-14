"""Main application window for the Content-Based Video Retrieval GUI."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.config import load_config  # noqa: E402

from models.result_item import ResultItem
from services.dres_client import DEFAULT_EVALUATION_ID, MockDresClient
from services.search_api import SearchService, create_search_service
from widgets.video_player import FullScreenPlayer
from widgets.video_tile import VideoTile

COLUMNS = 8


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Content-Based Video Retrieval")
        self.resize(1280, 820)
        self.setStyleSheet("QMainWindow { background: #0f171f; }")

        self._config = load_config(REPO_ROOT / "config.yaml")
        self._search: SearchService = create_search_service()
        self._page_size = self._config.gui.page_size
        self._page_offset = 0
        self._query = ""
        self._similarity_shot_id: str | None = None
        self._last_latency_ms = 0.0
        self._last_mode = "browse"
        self._player = None
        self._dres = MockDresClient()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addLayout(self._build_search_bar())
        root.addLayout(self._build_pagination_bar())
        root.addWidget(self._build_results_area(), stretch=1)

        self._refresh_results()

    def _build_search_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Natural-language search (e.g. \"person walking on beach\") — leave empty to browse"
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet(
            "QLineEdit { background: #1b2733; color: #e6edf3; border: 1px solid #2f3b48;"
            " border-radius: 8px; padding: 10px 14px; font-size: 15px; }"
            "QLineEdit:focus { border: 1px solid #1B7BB8; }"
        )
        self.search_input.returnPressed.connect(self._on_search)
        bar.addWidget(self.search_input, stretch=1)

        search_btn = QPushButton("Search")
        search_btn.setCursor(Qt.PointingHandCursor)
        search_btn.setStyleSheet(
            "QPushButton { background: #1B7BB8; color: white; border: none;"
            " border-radius: 8px; padding: 10px 22px; font-size: 14px; font-weight: 600; }"
            "QPushButton:hover { background: #2189c9; }"
            "QPushButton:pressed { background: #156493; }"
        )
        search_btn.clicked.connect(self._on_search)
        bar.addWidget(search_btn)

        clear_btn = QPushButton("Clear filters")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_filters)
        clear_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #9fb0c0; border: 1px solid #2f3b48;"
            " border-radius: 8px; padding: 10px 16px; font-size: 14px; }"
            "QPushButton:hover { color: #e6edf3; border: 1px solid #1B7BB8; background: #1b2733; }"
        )
        bar.addWidget(clear_btn)

        task_label = QLabel("DRES task:")
        task_label.setStyleSheet("color: #9fb0c0; font-size: 13px; padding-left: 8px;")
        bar.addWidget(task_label)

        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("task name")
        self.task_input.setText("mock_task_01")
        self.task_input.setFixedWidth(140)
        self.task_input.setStyleSheet(
            "QLineEdit { background: #1b2733; color: #e6edf3; border: 1px solid #2f3b48;"
            " border-radius: 8px; padding: 8px 10px; font-size: 13px; }"
        )
        bar.addWidget(self.task_input)
        return bar

    def _build_pagination_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #9fb0c0; font-size: 13px;")
        bar.addWidget(self.status_label, stretch=1)

        btn_style = (
            "QPushButton { background: #1b2733; color: #e6edf3; border: 1px solid #2f3b48;"
            " border-radius: 8px; padding: 8px 16px; }"
            "QPushButton:hover { border: 1px solid #1B7BB8; }"
            "QPushButton:disabled { color: #5a6b7b; }"
        )
        self.prev_btn = QPushButton("Previous")
        self.prev_btn.setStyleSheet(btn_style)
        self.prev_btn.clicked.connect(self._prev_page)
        bar.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.setStyleSheet(btn_style)
        self.next_btn.clicked.connect(self._next_page)
        bar.addWidget(self.next_btn)
        return bar

    def _build_results_area(self) -> QScrollArea:
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; }"
            "QScrollBar:vertical { background: #0f171f; width: 12px; }"
            "QScrollBar::handle:vertical { background: #2f3b48; border-radius: 6px; min-height: 30px; }"
        )

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(container)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(8)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll.setWidget(container)
        return self.scroll

    def _on_search(self):
        self._query = self.search_input.text().strip()
        self._similarity_shot_id = None
        self._page_offset = 0
        self._refresh_results()

    def _clear_filters(self):
        self.search_input.clear()
        self._query = ""
        self._similarity_shot_id = None
        self._page_offset = 0
        self._refresh_results()
        self.search_input.setFocus()

    def _prev_page(self):
        if self._page_offset <= 0:
            return
        self._page_offset = max(0, self._page_offset - self._page_size)
        self._refresh_results()

    def _next_page(self):
        resp = self._fetch_page()
        if self._page_offset + self._page_size >= resp.total:
            return
        self._page_offset += self._page_size
        self._refresh_results()

    def _fetch_page(self):
        if self._similarity_shot_id:
            return self._search.similarity_query(
                self._similarity_shot_id, self._page_size, self._page_offset
            )
        return self._search.text_query(
            self._query, self._page_size, self._page_offset
        )

    def _refresh_results(self):
        resp = self._fetch_page()
        self._last_latency_ms = resp.latency_ms
        self._last_mode = resp.mode
        self.show_results(resp.items)

        total = resp.total
        if total == 0:
            self.status_label.setText("No shots found.")
        else:
            start = self._page_offset + 1
            end = min(self._page_offset + len(resp.items), total)
            source = self._search.source_label
            mode = self._last_mode
            if self._similarity_shot_id:
                mode = f"similar to {self._similarity_shot_id}"
            elif self._query:
                mode = "semantic" if "FAISS" in source else "filter"
            latency = (
                f"  ·  {self._last_latency_ms:.0f} ms"
                if self._last_latency_ms > 0 and (self._query or self._similarity_shot_id)
                else ""
            )
            self.status_label.setText(
                f"Showing {start}–{end} of {total}  ·  {mode}  ·  {source}{latency}"
            )

        self.prev_btn.setEnabled(self._page_offset > 0)
        self.next_btn.setEnabled(self._page_offset + self._page_size < total)

    def show_results(self, items):
        self._clear_grid()
        for i, item in enumerate(items):
            tile = VideoTile(item)
            tile.playRequested.connect(self.open_player)
            tile.submitRequested.connect(self.submit_to_dres)
            tile.similarityRequested.connect(self._on_similarity)
            row, col = divmod(i, COLUMNS)
            self.grid.addWidget(tile, row, col)

    def _on_similarity(self, item: ResultItem):
        self._similarity_shot_id = item.shot_id
        self._query = ""
        self.search_input.clear()
        self._page_offset = 0
        self._refresh_results()

    def _clear_grid(self):
        while self.grid.count():
            child = self.grid.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def open_player(self, item: ResultItem):
        self._player = FullScreenPlayer(item)
        self._player.showFullScreen()

    def submit_to_dres(self, item: ResultItem):
        task_name = self.task_input.text().strip()
        if not task_name:
            QMessageBox.warning(self, "DRES Submit", "Enter a DRES task name first.")
            return

        msg = (
            f"<b>Submit this segment to DRES?</b><br><br>"
            f"Evaluation: <code>{DEFAULT_EVALUATION_ID}</code><br>"
            f"Task: <code>{task_name}</code><br>"
            f"Video ID: <code>{item.video_id}</code><br>"
            f"Shot: <code>{item.shot_id}</code><br>"
            f"Collection: <code>IVADL</code><br>"
            f"Start: <code>{item.start_ms} ms</code> &nbsp; End: <code>{item.end_ms} ms</code><br>"
            f"FPS: <code>{item.fps:.3f}</code><br><br>"
            f"<i>Wrong submissions cost 100 points each. Submit only if you are sure.</i>"
        )
        box = QMessageBox(self)
        box.setWindowTitle("Confirm DRES submission")
        box.setIcon(QMessageBox.Warning)
        box.setTextFormat(Qt.RichText)
        box.setText(msg)
        box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        box.button(QMessageBox.Ok).setText("Submit")
        if box.exec() != QMessageBox.Ok:
            return

        result = self._dres.submit(item, task_name)
        if result.ok:
            QMessageBox.information(self, "DRES Submit", result.message)
        else:
            QMessageBox.critical(self, "DRES Submit", result.message)
