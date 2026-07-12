"""Dataset inventory and validation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from pipeline.config import PipelineConfig
from pipeline.probe import VideoProbe, probe_video
from pipeline.scenes import list_scene_video_ids, load_shots


@dataclass
class VideoInventoryEntry:
    video_id: str
    filename: str
    has_scene_file: bool
    shot_count: int = 0
    fps: Optional[float] = None
    frame_count: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    last_shot_end: Optional[int] = None
    frame_bounds_ok: Optional[bool] = None
    errors: List[str] = field(default_factory=list)


@dataclass
class InventoryReport:
    video_count: int
    scene_file_count: int
    matched_ids: int
    videos_without_scenes: List[str]
    scenes_without_videos: List[str]
    missing_id_gaps: List[str]
    fps_values: Dict[str, float]
    entries: List[VideoInventoryEntry]
    vimeo_metadata_present: bool
    notes: List[str] = field(default_factory=list)


def list_video_ids(videos_dir: Path) -> List[str]:
    return sorted(p.stem for p in videos_dir.glob("*.mp4"))


def detect_id_gaps(video_ids: List[str]) -> List[str]:
    """List numeric IDs in the range that have no corresponding video file."""
    nums = [int(v) for v in video_ids if v.isdigit()]
    if not nums:
        return []
    lo, hi = min(nums), max(nums)
    present = set(nums)
    return [f"{i:05d}" for i in range(lo, hi + 1) if i not in present]


def run_inventory(config: PipelineConfig, probe_all: bool = True) -> InventoryReport:
    videos_dir = config.dataset.videos_dir
    scenes_zip = config.dataset.scenes_zip
    scenes_prefix = config.dataset.scenes_prefix

    video_ids = list_video_ids(videos_dir)
    scene_ids = list_scene_video_ids(scenes_zip, scenes_prefix)

    videos_set = set(video_ids)
    scenes_set = set(scene_ids)
    missing_scenes = sorted(videos_set - scenes_set)
    extra_scenes = sorted(scenes_set - videos_set)

    notes: List[str] = []
    if scenes_zip.name != "scenes_v3c1_200.zip":
        notes.append(
            f"Scenes archive is named {scenes_zip.name} "
            f"(assignment references scenes_v3c1_200.zip)."
        )

    vimeo_present = any(
        p.suffix.lower() in {".json", ".csv", ".txt", ".xml"}
        for p in videos_dir.iterdir()
        if p.is_file() and "vimeo" in p.name.lower()
    )
    if not vimeo_present:
        notes.append("No VIMEO metadata files found in dataset/ — defer to Phase 2.")

    entries: List[VideoInventoryEntry] = []
    fps_values: Dict[str, float] = {}

    for vid in video_ids:
        entry = VideoInventoryEntry(
            video_id=vid,
            filename=f"{vid}.mp4",
            has_scene_file=vid in scenes_set,
        )
        if not entry.has_scene_file:
            entry.errors.append("missing scene file")
            entries.append(entry)
            continue

        try:
            shots = load_shots(vid, scenes_zip, scenes_prefix)
            entry.shot_count = len(shots)
            entry.last_shot_end = shots[-1][1] if shots else None
        except (ValueError, FileNotFoundError) as exc:
            entry.errors.append(str(exc))
            entries.append(entry)
            continue

        if probe_all:
            video_path = videos_dir / entry.filename
            try:
                probe: VideoProbe = probe_video(video_path, vid)
                entry.fps = probe.fps
                entry.frame_count = probe.frame_count
                entry.width = probe.width
                entry.height = probe.height
                fps_values[vid] = probe.fps

                if entry.last_shot_end is not None and entry.frame_count > 0:
                    entry.frame_bounds_ok = entry.last_shot_end < entry.frame_count
                    if not entry.frame_bounds_ok:
                        entry.errors.append(
                            f"last shot end {entry.last_shot_end} >= frame_count {entry.frame_count}"
                        )
            except RuntimeError as exc:
                entry.errors.append(str(exc))

        entries.append(entry)

    return InventoryReport(
        video_count=len(video_ids),
        scene_file_count=len(scene_ids),
        matched_ids=len(videos_set & scenes_set),
        videos_without_scenes=missing_scenes,
        scenes_without_videos=extra_scenes,
        missing_id_gaps=detect_id_gaps(video_ids),
        fps_values=fps_values,
        entries=entries,
        vimeo_metadata_present=vimeo_present,
        notes=notes,
    )


def save_inventory_report(report: InventoryReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "video_count": report.video_count,
        "scene_file_count": report.scene_file_count,
        "matched_ids": report.matched_ids,
        "videos_without_scenes": report.videos_without_scenes,
        "scenes_without_videos": report.scenes_without_videos,
        "missing_id_gaps": report.missing_id_gaps,
        "fps_values": report.fps_values,
        "vimeo_metadata_present": report.vimeo_metadata_present,
        "notes": report.notes,
        "entries": [asdict(e) for e in report.entries],
        "error_count": sum(1 for e in report.entries if e.errors),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
