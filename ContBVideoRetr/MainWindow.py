"""Main application window for the Content-Based Video Retrieval GUI shell.

Layout:
  * Search bar across the top.
  * A large scrollable grid (4 columns) of video result tiles below.
Clicking a tile shows a small action menu (Play / Submit to DRES); Play opens
the clip fullscreen.
"""

from __future__ import annotations

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

from mock.mock_data import get_mock_results
from models.result_item import ResultItem
from services.dres_client import DEFAULT_EVALUATION_ID, MockDresClient
from widgets.video_player import FullScreenPlayer
from widgets.video_tile import VideoTile

COLUMNS = 4


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Content-Based Video Retrieval")
        self.resize(1280, 820)
        self.setStyleSheet("QMainWindow { background: #0f171f; }")

        self._player = None  # keep a reference so it is not garbage-collected
        self._dres = MockDresClient()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addLayout(self._build_search_bar())
        root.addWidget(self._build_results_area(), stretch=1)

        self.show_results(get_mock_results())

    # ----------------------------------------------------------------- UI --
    def _build_search_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search video content…  (e.g. \"person riding a bicycle\")")
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
        clear_btn.setToolTip("Remove all search filters and show the full result set")
        clear_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #9fb0c0; border: 1px solid #2f3b48;"
            " border-radius: 8px; padding: 10px 16px; font-size: 14px; }"
            "QPushButton:hover { color: #e6edf3; border: 1px solid #1B7BB8; background: #1b2733; }"
            "QPushButton:pressed { background: #16202b; }"
        )
        clear_btn.clicked.connect(self._clear_filters)
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

    def _build_results_area(self) -> QScrollArea:
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; }"
            "QScrollBar:vertical { background: #0f171f; width: 12px; margin: 0; }"
            "QScrollBar::handle:vertical { background: #2f3b48; border-radius: 6px; min-height: 30px; }"
            "QScrollBar::handle:vertical:hover { background: #3d4b5a; }"
            "QScrollBar::add-line, QScrollBar::sub-line { height: 0; }"
        )

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(container)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(12)
        self.grid.setAlignment(Qt.AlignTop)
        for c in range(COLUMNS):
            self.grid.setColumnStretch(c, 1)

        self.scroll.setWidget(container)
        return self.scroll

    # ------------------------------------------------------------- logic --
    def _on_search(self):
        query = self.search_input.text()
        self.show_results(get_mock_results(query))

    def _clear_filters(self):
        self.search_input.clear()
        self.show_results(get_mock_results())
        self.search_input.setFocus()

    def show_results(self, items):
        self._clear_grid()
        for i, item in enumerate(items):
            tile = VideoTile(item)
            tile.playRequested.connect(self.open_player)
            tile.submitRequested.connect(self.submit_to_dres)
            row, col = divmod(i, COLUMNS)
            self.grid.addWidget(tile, row, col)

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
            f"Collection: <code>IVADL</code><br>"
            f"Start: <code>{item.start_ms} ms</code> &nbsp; End: <code>{item.end_ms} ms</code><br><br>"
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
