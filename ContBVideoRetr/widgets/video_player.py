"""Fullscreen video player with shot-range playback."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QLabel, QStackedLayout, QWidget

from models.result_item import ResultItem


class FullScreenPlayer(QWidget):
    def __init__(self, item: ResultItem, parent=None):
        super().__init__(parent)
        self.item = item
        self._seek_pending = True
        self.setWindowTitle(f"Playing — {item.display_title}")
        self.setStyleSheet("background: black;")

        layout = QStackedLayout(self)
        layout.setStackingMode(QStackedLayout.StackAll)
        layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget(self)
        layout.addWidget(self.video_widget)

        self.overlay = QLabel(self)
        self.overlay.setAlignment(Qt.AlignCenter)
        self.overlay.setStyleSheet("color: #9fb0c0; font-size: 18px;")
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.overlay)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_widget)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.positionChanged.connect(self._on_position_changed)

        QShortcut(QKeySequence(Qt.Key_Escape), self, self.close)
        QShortcut(QKeySequence(Qt.Key_Space), self, self._toggle)

        self._load()

    def _info_overlay(self) -> str:
        it = self.item
        return (
            f"{it.video_id} · {it.shot_id}\n"
            f"frames {it.start_frame}–{it.end_frame}  "
            f"({it.start_ms}–{it.end_ms} ms @ {it.fps:.3f} fps)\n\n"
            f"Space: pause/play   Esc: close"
        )

    def _load(self):
        path = self.item.proxy_path
        if path and os.path.isfile(path):
            self.overlay.setText(self._info_overlay())
            self.player.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
        else:
            self.overlay.setText(
                f"\u25B6  {self.item.display_title}\n\n"
                "No proxy video file available.\n"
                "Run the R2 pipeline to generate proxies.\n\n"
                "(Press Esc to go back)"
            )

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self._seek_pending:
            self._seek_pending = False
            self.player.setPosition(self.item.start_ms)
            self.player.play()

    def _on_position_changed(self, position: int):
        if position >= self.item.end_ms and self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.player.setPosition(self.item.end_ms)

    def _toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            pos = self.player.position()
            if pos >= self.item.end_ms:
                self.player.setPosition(self.item.start_ms)
            self.player.play()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._toggle()
        super().mousePressEvent(event)

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)
