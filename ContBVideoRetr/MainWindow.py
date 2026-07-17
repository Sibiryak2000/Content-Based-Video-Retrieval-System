"""Main application window — Phase 5 competition-ready GUI."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from PySide6.QtCore import Qt, QSettings, QEvent
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
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
from services.dres_client import submission_confidence_warning
from services.dres_config import load_dres_settings
from services.dres_http_client import HttpDresClient, create_dres_client
from services.faiss_search import faiss_index_available, index_status_label
from services.search_api import SearchResponse, SearchService
from services.vqa_service import create_vqa_service
from widgets.video_player import FullScreenPlayer
from widgets.video_tile import VideoTile
from workers.search_worker import SearchWorker

MIN_TILE_WIDTH = 100
GOLDEN_PATH = REPO_ROOT / "data" / "eval" / "golden_queries.yaml"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Content-Based Video Retrieval")
        self.resize(760, 480)
        self.setStyleSheet("QMainWindow { background: #0f171f; }")

        self._settings = QSettings("IVADL", "ContBVideoRetr")
        self._config = load_config(REPO_ROOT / "config.yaml")
        self._dres_settings = load_dres_settings(REPO_ROOT / "config.yaml")
        self._search: SearchService = create_vqa_service()
        self._page_size = self._config.gui.page_size
        self._page_offset = 0
        self._query = ""
        self._similarity_shot_id: str | None = None
        self._last_items: list[ResultItem] = []
        self._last_total = 0
        self._last_mode = "browse"
        self._last_latency_ms = 0.0
        self._search_request_id = 0
        self._worker: SearchWorker | None = None
        self._progress: QProgressDialog | None = None
        self._player = None
        self._dres = create_dres_client()
        self._submitting = False
        self._last_show_rank = False
        self._last_rank_offset = 0
        self._grid_columns = 0

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        self._index_banner = QLabel()
        self._index_banner.setStyleSheet(
            "color: #f0c674; background: #2a2210; padding: 8px 12px; border-radius: 6px; font-size: 13px;"
        )
        if not faiss_index_available():
            self._index_banner.setText(
                "Semantic search unavailable — FAISS index missing. Browse/filter still works. "
                "Run: python scripts/rebuild_index.py"
            )
            root.addWidget(self._index_banner)

        root.addLayout(self._build_search_bar())
        root.addLayout(self._build_control_bar())
        root.addLayout(self._build_pagination_bar())
        root.addWidget(self._build_results_area(), stretch=1)

        self._restore_settings()
        self._populate_golden_queries()
        self._populate_evaluations()
        self._update_dres_status_label()
        self._refresh_results()

    def _input_style(self) -> str:
        return (
            "QLineEdit, QComboBox { background: #1b2733; color: #e6edf3; border: 1px solid #2f3b48;"
            " border-radius: 8px; padding: 8px 10px; font-size: 13px; }"
            "QLineEdit:focus, QComboBox:focus { border: 1px solid #1B7BB8; }"
        )

    def _build_search_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            'Natural-language search (e.g. "person walking") — leave empty to browse'
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet(
            "QLineEdit { background: #1b2733; color: #e6edf3; border: 1px solid #2f3b48;"
            " border-radius: 8px; padding: 10px 14px; font-size: 15px; }"
            "QLineEdit:focus { border: 1px solid #1B7BB8; }"
        )
        self.search_input.returnPressed.connect(self._on_search)
        bar.addWidget(self.search_input, stretch=1)

        self.search_btn = QPushButton("Search")
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.setStyleSheet(
            "QPushButton { background: #1B7BB8; color: white; border: none;"
            " border-radius: 8px; padding: 10px 22px; font-size: 14px; font-weight: 600; }"
            "QPushButton:hover { background: #2189c9; }"
            "QPushButton:disabled { background: #3a4a5a; }"
        )
        self.search_btn.clicked.connect(self._on_search)
        bar.addWidget(self.search_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_filters)
        clear_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #9fb0c0; border: 1px solid #2f3b48;"
            " border-radius: 8px; padding: 10px 16px; font-size: 14px; }"
            "QPushButton:hover { color: #e6edf3; border: 1px solid #1B7BB8; }"
        )
        bar.addWidget(clear_btn)
        return bar

    def _build_control_bar(self) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setSpacing(4)

        row1 = QHBoxLayout()
        row1.setSpacing(6)

        row1.addWidget(self._label("Task:"))
        self.task_type_combo = QComboBox()
        self.task_type_combo.addItems(["KIS Textual", "KIS Visual", "VQA"])
        self.task_type_combo.setFixedWidth(90)
        self.task_type_combo.setStyleSheet(self._input_style())
        self.task_type_combo.currentTextChanged.connect(self._on_task_type_changed)
        row1.addWidget(self.task_type_combo)

        row1.addWidget(self._label("DRES task:"))
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("task name")
        self.task_input.setFixedWidth(90)
        self.task_input.setStyleSheet(self._input_style())
        row1.addWidget(self.task_input)

        sync_task_btn = QPushButton("⟳ Task")
        sync_task_btn.setCursor(Qt.PointingHandCursor)
        sync_task_btn.setToolTip("Fetch the currently running DRES task name")
        sync_task_btn.clicked.connect(self._sync_task_name)
        sync_task_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #9fb0c0; border: 1px solid #2f3b48;"
            " border-radius: 6px; padding: 6px 10px; font-size: 12px; }"
            "QPushButton:hover { color: #e6edf3; border: 1px solid #1B7BB8; }"
        )
        row1.addWidget(sync_task_btn)

        row1.addWidget(self._label("VQA:"))
        self.vqa_input = QLineEdit()
        self.vqa_input.setPlaceholderText("answer")
        self.vqa_input.setFixedWidth(90)
        self.vqa_input.setStyleSheet(self._input_style())
        row1.addWidget(self.vqa_input)

        row1.addWidget(self._label("Eval:"))
        self.eval_combo = QComboBox()
        self.eval_combo.setMinimumWidth(100)
        self.eval_combo.setStyleSheet(self._input_style())
        row1.addWidget(self.eval_combo)
        self.eval_combo.currentIndexChanged.connect(lambda _: self._sync_task_name())

        row1.addWidget(self._label("Rehearsal:"))
        self.golden_combo = QComboBox()
        self.golden_combo.setMinimumWidth(120)
        self.golden_combo.setStyleSheet(self._input_style())
        self.golden_combo.currentIndexChanged.connect(self._on_golden_selected)
        row1.addWidget(self.golden_combo, stretch=1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.index_status = QLabel(index_status_label())
        self.index_status.setStyleSheet("color: #7a8a9a; font-size: 11px;")
        self.index_status.setWordWrap(True)
        row2.addWidget(self.index_status, stretch=1)

        self.dres_status = QLabel()
        self.dres_status.setStyleSheet("color: #9fb0c0; font-size: 11px;")
        row2.addWidget(self.dres_status)

        refresh_dres = QPushButton("Reconnect")
        refresh_dres.setCursor(Qt.PointingHandCursor)
        refresh_dres.clicked.connect(self._reconnect_dres)
        refresh_dres.setStyleSheet(
            "QPushButton { background: transparent; color: #9fb0c0; border: 1px solid #2f3b48;"
            " border-radius: 6px; padding: 4px 10px; font-size: 11px; }"
        )
        row2.addWidget(refresh_dres)

        wrap.addLayout(row1)
        wrap.addLayout(row2)
        return wrap

    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #9fb0c0; font-size: 13px;")
        return lbl

    def _update_dres_status_label(self) -> None:
        prefix = "DRES: connected" if self._dres.is_live else f"DRES: {self._dres.status_label}"
        self.dres_status.setText(prefix)

    def _reconnect_dres(self) -> None:
        self._dres = create_dres_client()
        self._update_dres_status_label()

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
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(container)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(8)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll.setWidget(container)
        self.scroll.viewport().installEventFilter(self)
        return self.scroll

    def eventFilter(self, obj, event) -> bool:
        if obj is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            cols = self._column_count()
            if cols != self._grid_columns and self._last_items:
                self._populate_grid(self._last_items, self._last_show_rank, self._last_rank_offset)
        return super().eventFilter(obj, event)

    def _column_count(self) -> int:
        width = self.scroll.viewport().width()
        spacing = self.grid.spacing()
        tile_slot = MIN_TILE_WIDTH + spacing
        return max(2, (width + spacing) // tile_slot)

    def _restore_settings(self) -> None:
        task = self._settings.value("dres_task", "mock_task_01")
        self.task_input.setText(str(task))
        eval_id = self._settings.value("evaluation_id", self._dres_settings.evaluation_id)
        self._saved_eval_id = str(eval_id)

    def _save_settings(self) -> None:
        self._settings.setValue("dres_task", self.task_input.text().strip())
        self._settings.setValue("evaluation_id", self._current_evaluation_id())

    def _populate_golden_queries(self) -> None:
        self.golden_combo.blockSignals(True)
        self.golden_combo.clear()
        self.golden_combo.addItem("— select golden query —", None)
        if GOLDEN_PATH.is_file():
            entries = yaml.safe_load(GOLDEN_PATH.read_text(encoding="utf-8")) or []
            for entry in entries:
                label = f"{entry.get('id', '?')} ({entry.get('type', '?')})"
                self.golden_combo.addItem(label, entry)
        self.golden_combo.blockSignals(False)

    def _populate_evaluations(self) -> None:
        self.eval_combo.blockSignals(True)
        self.eval_combo.clear()
        self._eval_map = {}
        default = self._dres_settings.evaluation_id
        if isinstance(self._dres, HttpDresClient):
            try:
                for ev in self._dres.list_evaluations():
                    label = f"{ev.name or ev.evaluation_id} ({ev.status})"
                    self.eval_combo.addItem(label, ev.evaluation_id)
                    self._eval_map[label] = ev.evaluation_id
            except Exception:
                pass
        if self.eval_combo.count() == 0:
            self.eval_combo.addItem(default, default)
        idx = self.eval_combo.findData(getattr(self, "_saved_eval_id", default))
        if idx >= 0:
            self.eval_combo.setCurrentIndex(idx)
        self.eval_combo.blockSignals(False)

    def _current_evaluation_id(self) -> str:
        data = self.eval_combo.currentData()
        return str(data) if data else self._dres_settings.evaluation_id

    def _sync_task_name(self) -> None:
        """Auto-fill the DRES task field with the currently running task's
        real name, so submit() always targets an actual active task run
        instead of an operator-typed guess."""
        if not hasattr(self._dres, "current_task_name"):
            return
        eval_id = self._current_evaluation_id()
        name = self._dres.current_task_name(eval_id)
        if name:
            self.task_input.setText(name)
            self.task_input.setStyleSheet(self._input_style())
        else:
            self.task_input.setStyleSheet(
                self._input_style() + "QLineEdit { border: 1px solid #e0684a; }"
            )

    def _on_task_type_changed(self, task_type: str) -> None:
        if task_type == "VQA":
            self.vqa_input.setFocus()
        self._auto_select_evaluation(task_type)

    def _auto_select_evaluation(self, task_type: str) -> None:
        """Auto-pick the DRES evaluation matching the current task type,
        using the explicit ID map in config.yaml (dres.evaluations) rather
        than guessing from the session's display name."""
        from services.dres_config import resolve_evaluation_id

        key_map = {
            "KIS Textual": "kis_textual",
            "KIS Visual": "kis_visual",
            "VQA": "vqa",
        }
        key = key_map.get(task_type)
        if not key:
            return
        target_id = resolve_evaluation_id(self._dres_settings, key)
        idx = self.eval_combo.findData(target_id)
        if idx >= 0:
            self.eval_combo.setCurrentIndex(idx)
        self._sync_task_name()

    def _on_golden_selected(self, index: int) -> None:
        entry = self.golden_combo.itemData(index)
        if not entry:
            return
        self.search_input.setText(entry.get("query", ""))
        if entry.get("type") == "VQA":
            self.task_type_combo.setCurrentText("VQA")
            ans = entry.get("expected_answer", "")
            if ans and ans != "manual check":
                self.vqa_input.setText(ans)
        else:
            self.task_type_combo.setCurrentText("KIS Textual")
        self._on_search()

    def _update_dres_status_label(self) -> None:
        prefix = "DRES: connected" if self._dres.is_live else f"DRES: {self._dres.status_label}"
        self.dres_status.setText(prefix)

    def _reconnect_dres(self) -> None:
        self._dres = create_dres_client()
        self._update_dres_status_label()
        self._populate_evaluations()

    def _on_search(self) -> None:
        self._query = self.search_input.text().strip()
        self._similarity_shot_id = None
        self._page_offset = 0
        self._start_search()

    def _clear_filters(self) -> None:
        self.search_input.clear()
        self._query = ""
        self._similarity_shot_id = None
        self._page_offset = 0
        self.golden_combo.setCurrentIndex(0)
        self._start_search()
        self.search_input.setFocus()

    def _start_search(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(500)

        self._search_request_id += 1
        req_id = self._search_request_id
        mode = "similarity" if self._similarity_shot_id else "text"

        self.search_btn.setEnabled(False)
        self._progress = QProgressDialog("Searching…", None, 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setMinimumDuration(200)
        self._progress.show()

        self._worker = SearchWorker(
            self._search,
            mode=mode,
            query=self._query,
            shot_id=self._similarity_shot_id or "",
            limit=self._page_size,
            offset=self._page_offset,
            request_id=req_id,
        )
        self._worker.finished_ok.connect(self._on_search_finished)
        self._worker.failed.connect(self._on_search_failed)
        self._worker.start()

    def _on_search_finished(self, resp: SearchResponse) -> None:
        if self._worker and self._worker.request_id != self._search_request_id:
            return
        self._close_progress()
        self.search_btn.setEnabled(True)
        self._last_latency_ms = resp.latency_ms
        self._last_mode = resp.mode
        self._last_items = resp.items
        self._last_total = resp.total
        self._apply_response(resp)

    def _on_search_failed(self, message: str) -> None:
        self._close_progress()
        self.search_btn.setEnabled(True)
        QMessageBox.critical(
            self, "Search failed",
            f"{message}\n\nCheck FAISS index and CLIP dependencies (torch, transformers).",
        )

    def _close_progress(self) -> None:
        if self._progress:
            self._progress.close()
            self._progress = None

    def _apply_response(self, resp: SearchResponse) -> None:
        show_rank = resp.mode in ("semantic", "similarity", "hybrid")
        self._last_show_rank = show_rank
        self._last_rank_offset = self._page_offset
        self._populate_grid(resp.items, show_rank, self._page_offset)

        total = resp.total
        if total == 0:
            self.status_label.setText("No shots found.")
        else:
            start = self._page_offset + 1
            end = min(self._page_offset + len(resp.items), total)
            mode = self._last_mode
            if self._similarity_shot_id:
                mode = f"similar to {self._similarity_shot_id}"
            latency = (
                f"  ·  {self._last_latency_ms:.0f} ms"
                if self._last_latency_ms > 0 and (self._query or self._similarity_shot_id)
                else ""
            )
            self.status_label.setText(
                f"Showing {start}-{end} of {total}  ·  {mode}  ·  "
                f"{self._search.source_label}{latency}"
            )
        self.prev_btn.setEnabled(self._page_offset > 0)
        self.next_btn.setEnabled(self._page_offset + self._page_size < self._last_total)

    def _refresh_results(self) -> None:
        self._start_search()

    def _prev_page(self) -> None:
        if self._page_offset <= 0:
            return
        self._page_offset = max(0, self._page_offset - self._page_size)
        self._start_search()

    def _next_page(self) -> None:
        if self._page_offset + self._page_size >= self._last_total:
            return
        self._page_offset += self._page_size
        self._start_search()

    def show_results(
        self,
        items: list[ResultItem],
        show_rank: bool = False,
        rank_offset: int = 0,
    ) -> None:
        self._last_items = items
        self._last_show_rank = show_rank
        self._last_rank_offset = rank_offset
        self._populate_grid(items, show_rank, rank_offset)

    def _populate_grid(
        self,
        items: list[ResultItem],
        show_rank: bool,
        rank_offset: int,
    ) -> None:
        cols = self._column_count()
        self._grid_columns = cols
        self._clear_grid()
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)
        for i, item in enumerate(items):
            rank = rank_offset + i + 1 if show_rank else None
            tile = VideoTile(item, rank=rank)
            tile.playRequested.connect(self.open_player)
            tile.submitRequested.connect(self.submit_to_dres)
            tile.similarityRequested.connect(self._on_similarity)
            tile.doubleClicked.connect(self.open_player)
            row, col = divmod(i, cols)
            self.grid.addWidget(tile, row, col)

    def _on_similarity(self, item: ResultItem) -> None:
        self._similarity_shot_id = item.shot_id
        self._query = ""
        self.search_input.clear()
        self._page_offset = 0
        self._start_search()

    def _clear_grid(self) -> None:
        while self.grid.count():
            child = self.grid.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def open_player(self, item: ResultItem) -> None:
        idx = next((i for i, it in enumerate(self._last_items) if it.shot_id == item.shot_id), 0)
        self._player = FullScreenPlayer(
            item,
            result_list=self._last_items,
            start_index=idx,
            submit_callback=self.submit_to_dres,
        )
        self._player.showFullScreen()

    def submit_to_dres(self, item: ResultItem) -> None:
        if self._submitting:
            return

        task_name = self.task_input.text().strip()
        if not task_name:
            QMessageBox.warning(self, "DRES Submit", "Enter a DRES task name first.")
            return

        vqa_text = self.vqa_input.text().strip() or None
        if self.task_type_combo.currentText() == "VQA" and not vqa_text:
            # Fall back to the auto-generated BLIP answer (Phase 3, R1/R3) if the
            # operator hasn't typed one manually.
            vqa_text = item.text
            if vqa_text:
                self.vqa_input.setText(vqa_text)
        if self.task_type_combo.currentText() == "VQA" and not vqa_text:
            QMessageBox.warning(self, "DRES Submit", "VQA tasks require an answer in the VQA field.")
            return

        submit_item = ResultItem(
            video_id=item.video_id,
            shot_id=item.shot_id,
            title=item.title,
            keyframe_path=item.keyframe_path,
            proxy_path=item.proxy_path,
            start_frame=item.start_frame,
            end_frame=item.end_frame,
            fps=item.fps,
            score=item.score,
            text=vqa_text,
        )

        eval_id = self._current_evaluation_id()
        mode = "live HTTP" if self._dres.is_live else self._dres.status_label
        msg = (
            f"<b>Submit this segment to DRES?</b><br><br>"
            f"Evaluation: <code>{eval_id}</code><br>"
            f"Task: <code>{task_name}</code> ({self.task_type_combo.currentText()})<br>"
            f"Video ID: <code>{submit_item.video_id}</code><br>"
            f"Shot: <code>{submit_item.shot_id}</code><br>"
            f"Collection: <code>IVADL</code><br>"
            f"Start: <code>{submit_item.start_ms} ms</code> &nbsp; "
            f"End: <code>{submit_item.end_ms} ms</code><br>"
            f"FPS: <code>{submit_item.fps:.3f}</code><br>"
        )
        if vqa_text:
            msg += f"VQA text: <code>{vqa_text}</code><br>"

        confidence_warning = submission_confidence_warning(item)
        if confidence_warning:
            msg += f"<br><b style='color:#e0684a'>⚠ {confidence_warning}</b><br>"

        msg += (
            f"DRES mode: <code>{mode}</code><br><br>"
            f"<i>Wrong submissions cost 100 points each. Submit only if you are sure.</i>"
        )

        box = QMessageBox(self)
        box.setWindowTitle("Confirm DRES submission")
        box.setIcon(QMessageBox.Warning)
        box.setTextFormat(Qt.RichText)
        box.setText(msg)
        copy_btn = box.addButton("Copy ms range", QMessageBox.ActionRole)
        box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        box.button(QMessageBox.Ok).setText("Submit")
        box.exec()
        if box.clickedButton() == copy_btn:
            QGuiApplication.clipboard().setText(
                f"{submit_item.video_id} {submit_item.start_ms}-{submit_item.end_ms}"
            )
            return
        if box.clickedButton() != box.button(QMessageBox.Ok):
            return

        self._submitting = True
        self._save_settings()
        try:
            result = self._dres.submit(submit_item, task_name, evaluation_id=eval_id)
        finally:
            self._submitting = False

        title = "DRES Submit"
        if result.ok:
            prefix = "Live DRES accepted" if self._dres.is_live else "Mock submission accepted"
            QMessageBox.information(self, title, f"{prefix}:\n{result.message}")
        else:
            QMessageBox.critical(self, title, result.message)
