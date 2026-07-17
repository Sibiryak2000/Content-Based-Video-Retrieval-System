"""Dataclasses mirroring the SQLite schema."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class VideoRecord:
    video_id: str
    filename: str
    fps: float
    frame_count: int
    width: int
    height: int
    proxy_path: Optional[str] = None
    vimeo_description: Optional[str] = None


@dataclass
class ShotRecord:
    shot_id: str
    video_id: str
    shot_index: int
    start_frame: int
    end_frame: int
    keyframe_path: Optional[str] = None


@dataclass
class ShotWithVideo:
    shot_id: str
    video_id: str
    shot_index: int
    start_frame: int
    end_frame: int
    keyframe_path: Optional[str]
    fps: float
    proxy_path: Optional[str]
    vimeo_description: Optional[str] = None

    @property
    def start_ms(self) -> int:
        return int(self.start_frame / self.fps * 1000) if self.fps else 0

    @property
    def end_ms(self) -> int:
        return int(self.end_frame / self.fps * 1000) if self.fps else 0
