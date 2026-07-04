"""Generate short sample MP4 clips for the GUI shell.

Run once from the ContRetr directory:
    python scripts/generate_sample_videos.py
"""

from __future__ import annotations

import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "sample_videos")

SAMPLES = [
    ("city_street_at_night", (30, 40, 80), "City street at night"),
    ("person_riding_bicycle", (20, 90, 50), "Person riding a bicycle"),
    ("aerial_coastline", (10, 120, 160), "Aerial view of coastline"),
    ("cooking_kitchen", (120, 70, 30), "Cooking in a kitchen"),
    ("crowd_concert", (90, 30, 120), "Crowd at a concert"),
    ("dog_running_park", (50, 130, 60), "Dog running in a park"),
]

FPS = 25
DURATION_SEC = 3
WIDTH, HEIGHT = 640, 360


def _write_clip(path: str, bgr: tuple[int, int, int], label: str) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, FPS, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open VideoWriter for {path}")

    frames = int(DURATION_SEC * FPS)
    for i in range(frames):
        frame = np.full((HEIGHT, WIDTH, 3), bgr, dtype=np.uint8)
        # subtle motion so playback is visibly "alive"
        offset = int(10 * np.sin(i / 8))
        cv2.circle(frame, (WIDTH // 2 + offset, HEIGHT // 2), 48, (255, 255, 255), -1)
        cv2.putText(
            frame, label, (24, HEIGHT - 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA,
        )
        writer.write(frame)
    writer.release()


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    for stem, color, label in SAMPLES:
        path = os.path.join(OUT_DIR, f"{stem}.mp4")
        _write_clip(path, color, label)
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
