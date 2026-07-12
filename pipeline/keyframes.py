"""Extract keyframe JPEGs for shots."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

from pipeline.scenes import pick_keyframe_frame


def _read_frame_robust(
    cap: cv2.VideoCapture,
    start: int,
    end: int,
    preferred: int,
) -> tuple[int, np.ndarray]:
    """Seek and read a frame, trying nearby indices when OpenCV seek is unreliable."""
    candidates: list[int] = [preferred, start, end]
    for delta in range(1, 32):
        candidates.extend([preferred - delta, preferred + delta])

    tried: set[int] = set()
    for frame_no in candidates:
        if frame_no in tried or frame_no < start or frame_no > end:
            continue
        tried.add(frame_no)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ok, frame = cap.read()
        if ok and frame is not None:
            return frame_no, frame

    raise RuntimeError(f"could not read any frame in range {start}-{end} (preferred {preferred})")


def _placeholder_frame(width: int = 480, height: int = 270) -> np.ndarray:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (48, 48, 48)
    return frame


def extract_keyframes_for_video(
    video_path: Path,
    video_id: str,
    shots: List[Tuple[int, int]],
    output_dir: Path,
    strategy: str = "mid_frame",
) -> List[Path]:
    """Extract one JPEG per shot; return paths written."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open {video_path}")

    written: List[Path] = []
    for shot_index, (start, end) in enumerate(shots):
        frame_no = pick_keyframe_frame(start, end, strategy)
        try:
            _, frame = _read_frame_robust(cap, start, end, frame_no)
        except RuntimeError as exc:
            print(f"  WARN {video_id} shot {shot_index}: {exc} - using placeholder", flush=True)
            frame = _placeholder_frame()

        out_path = output_dir / f"{shot_index:04d}.jpg"
        ok_write, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok_write:
            cap.release()
            raise RuntimeError(f"{video_id} shot {shot_index}: could not encode frame {frame_no}")
        out_path.write_bytes(encoded.tobytes())
        written.append(out_path)

    cap.release()
    return written
