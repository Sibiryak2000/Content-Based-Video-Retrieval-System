"""A single result tile in the video grid.

Shows a keyframe thumbnail (or a generated placeholder) and a caption. Clicking
the tile opens a small action menu with Play and Submit to DRES.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QPolygonF, QAction
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
)

from models.result_item import ResultItem

_THUMB_W = 120
_THUMB_H = 75

_PALETTE = [
    "#1B7BB8", "#0B2545", "#1E7F4F", "#8A4FBE", "#B8551B",
    "#2E7D8A", "#B83A63", "#4F5D2E", "#3A4FB8", "#7A7A20",
]


def _placeholder_pixmap(item: ResultItem) -> QPixmap:
    """Generate a colored placeholder thumbnail with a play glyph."""
    pm = QPixmap(_THUMB_W, _THUMB_H)
    color = QColor(_PALETTE[hash(item.display_title) % len(_PALETTE)])
    pm.fill(color)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)

    # central play triangle
    painter.setBrush(QColor(255, 255, 255, 210))
    painter.setPen(Qt.NoPen)
    cx, cy, s = _THUMB_W / 2, _THUMB_H / 2 - 5, 13
    triangle = QPolygonF([
        QPointF(cx - s * 0.5, cy - s),
        QPointF(cx - s * 0.5, cy + s),
        QPointF(cx + s, cy),
    ])
    painter.drawPolygon(triangle)

    # caption
    painter.setPen(QColor("white"))
    f = QFont("Segoe UI", 7)
    painter.setFont(f)
    painter.drawText(
        pm.rect().adjusted(8, 0, -8, -10),
        Qt.AlignHCenter | Qt.AlignBottom,
        item.display_title,
    )
    painter.end()
    return pm


class VideoTile(QFrame):
    playRequested = Signal(object)    # emits ResultItem
    submitRequested = Signal(object)  # emits ResultItem

    def __init__(self, item: ResultItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("VideoTile")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
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
        self.thumb.setScaledContents(True)
        self.thumb.setFixedSize(_THUMB_W, _THUMB_H)
        self._set_thumbnail()
        layout.addWidget(self.thumb)

        caption = QLabel(
            f"{item.video_id} · frames {item.start_frame}–{item.end_frame}"
        )
        caption.setStyleSheet("color: #cdd8e3; font-size: 10px; padding: 1px;")
        caption.setWordWrap(True)
        caption.setAlignment(Qt.AlignLeft)
        layout.addWidget(caption)

    def _set_thumbnail(self):
        path = self.item.keyframe_path
        if path and os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                self.thumb.setPixmap(pm)
                return
        # Broken or missing asset — colored placeholder (no crash)
        self.thumb.setPixmap(_placeholder_pixmap(self.item))
        if path:
            self.thumb.setToolTip(f"Keyframe missing:\n{path}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._show_action_menu(event.globalPosition().toPoint())
        super().mousePressEvent(event)

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

        submit_action = QAction("\u21E9  Submit to DRES", self)
        submit_action.triggered.connect(lambda: self.submitRequested.emit(self.item))
        menu.addAction(submit_action)

        menu.exec(global_pos)
