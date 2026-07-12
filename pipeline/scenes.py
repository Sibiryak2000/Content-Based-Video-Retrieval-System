"""Read TransNet2 shot boundaries from the scenes zip archive."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

Shot = Tuple[int, int]


def _scene_entry_name(video_id: str, scenes_prefix: str) -> str:
    return f"{scenes_prefix}/{video_id}.mp4.scenes.txt"


def list_scene_video_ids(scenes_zip: Path, scenes_prefix: str) -> List[str]:
    """Return sorted video IDs that have a .scenes.txt entry in the zip."""
    ids: List[str] = []
    with zipfile.ZipFile(scenes_zip) as zf:
        for name in zf.namelist():
            if name.startswith("__MACOSX"):
                continue
            if not name.endswith(".scenes.txt"):
                continue
            stem = Path(name).name.replace(".mp4.scenes.txt", "")
            ids.append(stem)
    return sorted(set(ids))


def load_shots(video_id: str, scenes_zip: Path, scenes_prefix: str) -> List[Shot]:
    """Return [(start_frame, end_frame), ...] for one video."""
    entry = _scene_entry_name(video_id, scenes_prefix)
    with zipfile.ZipFile(scenes_zip) as zf:
        if entry not in zf.namelist():
            raise FileNotFoundError(f"No scene file for {video_id} in {scenes_zip}")
        text = zf.read(entry).decode("utf-8").strip()

    shots: List[Shot] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f"{video_id} line {line_no}: expected two integers, got {line!r}")
        start, end = int(parts[0]), int(parts[1])
        if start > end:
            raise ValueError(f"{video_id} line {line_no}: start > end ({start} > {end})")
        shots.append((start, end))
    return shots


def load_all_shots(scenes_zip: Path, scenes_prefix: str) -> Dict[str, List[Shot]]:
    """Load shot lists for every video ID in the zip."""
    return {
        vid: load_shots(vid, scenes_zip, scenes_prefix)
        for vid in list_scene_video_ids(scenes_zip, scenes_prefix)
    }


def make_shot_id(video_id: str, shot_index: int) -> str:
    return f"{video_id}_{shot_index:04d}"


def pick_keyframe_frame(start: int, end: int, strategy: str = "mid_frame") -> int:
    if strategy == "start_frame":
        return start
    if strategy == "mid_frame":
        return (start + end) // 2
    raise ValueError(f"Unknown keyframe strategy: {strategy}")
