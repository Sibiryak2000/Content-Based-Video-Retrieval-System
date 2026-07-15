"""Fullscreen video player with shot-range playback and eval shortcuts."""

from __future__ import annotations

import os
from typing import Callable, Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QLabel, QPushButton, QStackedLayout, QVBoxLayout, QWidget

from models.result_item import ResultItem


class FullScreenPlayer(QWidget):
    def __init__(
        self,
        item: ResultItem,
        result_list: Optional[list[ResultItem]] = None,
        start_index: int = 0,
        submit_callback: Optional[Callable[[ResultItem], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.item = item
        self._result_list = result_list or [item]
        self._index = start_index
        self._submit_callback = submit_callback
        self._loop_shot = False
        self._seek_pending = True
        self.setWindowTitle(f"Playing — {item.display_title}")
        self.setStyleSheet("background: black;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        stack_host = QWidget()
        layout = QStackedLayout(stack_host)
        layout.setStackingMode(QStackedLayout.StackAll)
        layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget(stack_host)
        layout.addWidget(self.video_widget)

        self.overlay = QLabel(stack_host)
        self.overlay.setAlignment(Qt.AlignCenter)
        self.overlay.setStyleSheet("color: #9fb0c0; font-size: 16px;")
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.overlay)

        outer.addWidget(stack_host, stretch=1)

        btn_row = QWidget()
        btn_row.setStyleSheet("background: rgba(15,23,31,200);")
        btn_layout = QVBoxLayout(btn_row)
        self.submit_btn = QPushButton("Submit to DRES (S)")
        self.submit_btn.setStyleSheet(
            "QPushButton { background: #1B7BB8; color: white; border: none;"
            " padding: 10px 20px; font-size: 14px; border-radius: 6px; }"
        )
        self.submit_btn.clicked.connect(self._submit)
        btn_layout.addWidget(self.submit_btn)
        outer.addWidget(btn_row)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_widget)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.positionChanged.connect(self._on_position_changed)

        QShortcut(QKeySequence(Qt.Key_Escape), self, self.close)
        QShortcut(QKeySequence(Qt.Key_Space), self, self._toggle)
        QShortcut(QKeySequence("S"), self, self._submit)
        QShortcut(QKeySequence("L"), self, self._toggle_loop)
        QShortcut(QKeySequence("N"), self, self._next_result)

        self._load()

    def _info_overlay(self) -> str:
        it = self.item
        loop = "ON" if self._loop_shot else "off"
        return (
            f"{it.video_id} · {it.shot_id}\n"
            f"DRES: {it.start_ms}–{it.end_ms} ms @ {it.fps:.3f} fps\n"
            f"frames {it.start_frame}–{it.end_frame}\n\n"
            f"Space: pause/play  ·  S: submit  ·  L: loop ({loop})  ·  N: next  ·  Esc: close"
        )

    def _load(self):
        self._seek_pending = True
        path = self.item.proxy_path
        self.overlay.setText(self._info_overlay())
        if path and os.path.isfile(path):
            self.player.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
        else:
            self.overlay.setText(
                f"\u25B6  {self.item.display_title}\n\nNo proxy video available.\n(Esc to close)"
            )

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self._seek_pending:
            self._seek_pending = False
            self.player.setPosition(self.item.start_ms)
            self.player.play()

    def _on_position_changed(self, position: int):
        if position >= self.item.end_ms and self.player.playbackState() == QMediaPlayer.PlayingState:
            if self._loop_shot:
                self.player.setPosition(self.item.start_ms)
                self.player.play()
            else:
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

    def _toggle_loop(self):
        self._loop_shot = not self._loop_shot
        self.overlay.setText(self._info_overlay())

    def _next_result(self):
        if len(self._result_list) <= 1:
            return
        self._index = (self._index + 1) % len(self._result_list)
        self.item = self._result_list[self._index]
        self.player.stop()
        self._load()

    def _submit(self):
        if self._submit_callback:
            self._submit_callback(self.item)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._toggle()
        super().mousePressEvent(event)

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)
