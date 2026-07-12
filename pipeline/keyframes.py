"""Extract keyframe JPEGs for shots."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import cv2

from pipeline.scenes import pick_keyframe_frame


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
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            raise RuntimeError(f"{video_id} shot {shot_index}: could not read frame {frame_no}")

        out_path = output_dir / f"{shot_index:04d}.jpg"
        ok_write, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok_write:
            cap.release()
            raise RuntimeError(f"{video_id} shot {shot_index}: could not encode frame {frame_no}")
        out_path.write_bytes(encoded.tobytes())
        written.append(out_path)

    cap.release()
    return written
