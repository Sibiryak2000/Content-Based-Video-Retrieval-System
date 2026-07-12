"""Probe video files for fps, frame count, and resolution."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2


@dataclass
class VideoProbe:
    video_id: str
    path: Path
    fps: float
    frame_count: int
    width: int
    height: int

    @property
    def duration_sec(self) -> float:
        return self.frame_count / self.fps if self.fps > 0 else 0.0


def probe_video(video_path: Path, video_id: str | None = None) -> VideoProbe:
    vid = video_id or video_path.stem
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if fps <= 0:
        fps = 25.0  # fallback only when container lacks fps metadata

    return VideoProbe(
        video_id=vid,
        path=video_path,
        fps=fps,
        frame_count=frame_count,
        width=width,
        height=height,
    )


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def probe_video_ffprobe(video_path: Path, video_id: str | None = None) -> VideoProbe | None:
    """Optional cross-check using ffprobe when ffmpeg is installed."""
    if not ffprobe_available():
        return None
    vid = video_id or video_path.stem
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1",
        str(video_path),
    ]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    width = height = 0
    fps = 25.0
    frame_count = 0
    for line in out.splitlines():
        if line.startswith("width="):
            width = int(line.split("=", 1)[1])
        elif line.startswith("height="):
            height = int(line.split("=", 1)[1])
        elif line.startswith("r_frame_rate="):
            num, den = line.split("=", 1)[1].split("/")
            fps = float(num) / float(den) if float(den) else 25.0
        elif line.startswith("nb_frames="):
            val = line.split("=", 1)[1]
            if val.isdigit():
                frame_count = int(val)

    if frame_count <= 0 and fps > 0:
        for line in out.splitlines():
            if line.startswith("duration="):
                frame_count = int(float(line.split("=", 1)[1]) * fps)
                break

    if width <= 0:
        return None

    return VideoProbe(
        video_id=vid,
        path=video_path,
        fps=fps,
        frame_count=frame_count,
        width=width,
        height=height,
    )
