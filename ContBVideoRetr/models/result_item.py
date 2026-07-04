"""Data contract shared between the GUI, search backend and DRES client.

A ResultItem represents a single shot / keyframe returned by a search. The
frame + fps fields let the DRES submission convert frames to milliseconds later
(start_ms = start_frame / fps * 1000).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ResultItem:
    video_id: str                      # video name WITHOUT extension (DRES needs this)
    shot_id: str = ""
    title: str = ""
    keyframe_path: Optional[str] = None  # local path/URL to the thumbnail image
    proxy_path: Optional[str] = None     # local path to the transcoded playback video
    start_frame: int = 0
    end_frame: int = 0
    fps: float = 25.0
    score: float = 0.0
    text: Optional[str] = None           # optional VQA answer text

    @property
    def start_ms(self) -> int:
        return int(self.start_frame / self.fps * 1000) if self.fps else 0

    @property
    def end_ms(self) -> int:
        return int(self.end_frame / self.fps * 1000) if self.fps else 0

    @property
    def display_title(self) -> str:
        return self.title or self.video_id
