"""A single result tile in the video grid."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal, QPointF, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QPolygonF, QAction
from PySide6.QtWidgets import QFrame, QLabel, QMenu, QSizePolicy, QVBoxLayout

from models.result_item import ResultItem

_THUMB_ASPECT = 75 / 120  # height / width
_MIN_THUMB_W = 72

_PALETTE = [
    "#1B7BB8", "#0B2545", "#1E7F4F", "#8A4FBE", "#B8551B",
    "#2E7D8A", "#B83A63", "#4F5D2E", "#3A4FB8", "#7A7A20",
]


def _placeholder_pixmap(item: ResultItem, width: int, height: int) -> QPixmap:
    pm = QPixmap(max(width, 1), max(height, 1))
    color = QColor(_PALETTE[hash(item.display_title) % len(_PALETTE)])
    pm.fill(color)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(255, 255, 255, 210))
    painter.setPen(Qt.NoPen)
    cx, cy = width / 2, height / 2 - 5
    s = max(8, min(width, height) * 0.12)
    triangle = QPolygonF([
        QPointF(cx - s * 0.5, cy - s),
        QPointF(cx - s * 0.5, cy + s),
        QPointF(cx + s, cy),
    ])
    painter.drawPolygon(triangle)
    painter.setPen(QColor("white"))
    painter.setFont(QFont("Segoe UI", max(6, int(width * 0.06))))
    painter.drawText(
        pm.rect().adjusted(4, 0, -4, -4),
        Qt.AlignHCenter | Qt.AlignBottom,
        item.display_title,
    )
    painter.end()
    return pm


class VideoTile(QFrame):
    playRequested = Signal(object)
    submitRequested = Signal(object)
    similarityRequested = Signal(object)
    doubleClicked = Signal(object)

    def __init__(self, item: ResultItem, rank: int | None = None, parent=None):
        super().__init__(parent)
        self.item = item
        self._rank = rank
        self._source_pixmap: QPixmap | None = None
        self._using_placeholder = False
        self.setObjectName("VideoTile")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(_MIN_THUMB_W)
        self.setStyleSheet(
            "#VideoTile { background: #16202b; border: 1px solid #26313d;"
            " border-radius: 6px; }"
            "#VideoTile:hover { border: 1px solid #1B7BB8; background: #1b2733; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.thumb = QLabel()
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._load_thumbnail_source()
        layout.addWidget(self.thumb)

        cap_parts = [item.video_id, f"frames {item.start_frame}–{item.end_frame}"]
        if item.score > 0:
            cap_parts.append(f"score {item.score:.2f}")
        if rank is not None:
            cap_parts.insert(0, f"#{rank}")
        self.caption = QLabel(" · ".join(cap_parts))
        self.caption.setStyleSheet("color: #cdd8e3; font-size: 10px; padding: 1px;")
        self.caption.setWordWrap(True)
        layout.addWidget(self.caption)

        self._update_thumb_size()

    def _thumb_dimensions(self) -> tuple[int, int]:
        w = max(self.width() - 8, _MIN_THUMB_W)
        h = max(int(w * _THUMB_ASPECT), 45)
        return w, h

    def _load_thumbnail_source(self) -> None:
        path = self.item.keyframe_path
        self._using_placeholder = True
        self._source_pixmap = None
        if path and os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                self._source_pixmap = pm
                self._using_placeholder = False
                return
        if path:
            self.thumb.setToolTip(f"Keyframe missing:\n{path}")

    def _update_thumb_size(self) -> None:
        w, h = self._thumb_dimensions()
        self.thumb.setFixedHeight(h)
        if self._source_pixmap is not None:
            scaled = self._source_pixmap.scaled(
                QSize(w, h), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.thumb.setPixmap(scaled)
        else:
            self.thumb.setPixmap(_placeholder_pixmap(self.item, w, h))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_thumb_size()

    def sizeHint(self) -> QSize:
        w, h = self._thumb_dimensions()
        return QSize(w + 8, h + self.caption.sizeHint().height() + 14)

    def minimumSizeHint(self) -> QSize:
        return QSize(_MIN_THUMB_W, int(_MIN_THUMB_W * _THUMB_ASPECT) + 24)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._show_action_menu(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit(self.item)
        super().mouseDoubleClickEvent(event)

    def _show_action_menu(self, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1b2733; color: #e6edf3; border: 1px solid #2f3b48;"
            " border-radius: 6px; padding: 4px; }"
            "QMenu::item { padding: 8px 22px; border-radius: 4px; }"
            "QMenu::item:selected { background: #1B7BB8; }"
        )
        play_action = QAction("\u25B6  Play", self)
        play_action.triggered.connect(lambda: self.playRequested.emit(self.item))
        menu.addAction(play_action)

        similar_action = QAction("\u2248  More like this", self)
        similar_action.triggered.connect(lambda: self.similarityRequested.emit(self.item))
        menu.addAction(similar_action)

        submit_action = QAction("\u21E9  Submit to DRES", self)
        submit_action.triggered.connect(lambda: self.submitRequested.emit(self.item))
        menu.addAction(submit_action)

        similar_action = QAction("\u2248  More like this", self)
        similar_action.triggered.connect(lambda: self.similarityRequested.emit(self.item))
        menu.addAction(similar_action)

        menu.exec(global_pos)
