"""Transcode lightweight playback proxies with ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def transcode_proxy(
    input_path: Path,
    output_path: Path,
    height: int = 270,
) -> Path:
    """Create an H.264/AAC proxy with faststart for GUI seeking."""
    if not ffmpeg_available():
        raise RuntimeError(
            "ffmpeg not found on PATH. Install ffmpeg to generate playback proxies."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", f"scale=-2:{height}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def copy_as_proxy(input_path: Path, output_path: Path) -> Path:
    """Fallback when ffmpeg is unavailable: copy source to proxy location."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(input_path, output_path)
    return output_path
