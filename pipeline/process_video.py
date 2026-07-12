"""Process a single video through the Phase 2 pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pipeline.config import PipelineConfig
from pipeline.db.models import ShotRecord, VideoRecord
from pipeline.db.store import MetadataStore
from pipeline.keyframes import extract_keyframes_for_video
from pipeline.probe import probe_video
from pipeline.scenes import load_shots, make_shot_id
from pipeline.transcode import copy_as_proxy, ffmpeg_available, transcode_proxy


@dataclass
class ProcessResult:
    video_id: str
    shot_count: int
    skipped: bool
    fps: float


def is_video_complete(
    store: MetadataStore,
    config: PipelineConfig,
    video_id: str,
    expected_shots: int,
) -> bool:
    shots = store.list_shots_for_video(video_id)
    if len(shots) != expected_shots:
        return False
    proxy = config.output.proxies_dir / f"{video_id}.mp4"
    if not proxy.is_file():
        return False
    for s in shots:
        if not s.keyframe_path:
            return False
        kf = config.repo_root / s.keyframe_path
        if not kf.is_file():
            return False
    return True


def process_video(
    config: PipelineConfig,
    store: MetadataStore,
    video_id: str,
    *,
    skip_keyframes: bool = False,
    skip_proxies: bool = False,
    use_ffmpeg: bool | None = None,
) -> ProcessResult:
    video_path = config.dataset.videos_dir / f"{video_id}.mp4"
    if not video_path.is_file():
        raise FileNotFoundError(f"Missing video: {video_path}")

    shots = load_shots(video_id, config.dataset.scenes_zip, config.dataset.scenes_prefix)
    probe = probe_video(video_path, video_id)
    use_ffmpeg = ffmpeg_available() if use_ffmpeg is None else use_ffmpeg

    proxy_out = config.output.proxies_dir / f"{video_id}.mp4"
    if not skip_proxies:
        if use_ffmpeg:
            transcode_proxy(video_path, proxy_out, height=config.prototype.proxy_height)
        else:
            copy_as_proxy(video_path, proxy_out)

    kf_dir = config.output.keyframes_dir / video_id
    kf_paths: list[Path] = []
    if not skip_keyframes:
        kf_paths = extract_keyframes_for_video(
            video_path, video_id, shots, kf_dir, strategy=config.prototype.keyframe_strategy,
        )
    else:
        for shot_index in range(len(shots)):
            kf_paths.append(kf_dir / f"{shot_index:04d}.jpg")

    proxy_rel = store.make_relative(proxy_out, config.repo_root)
    store.upsert_video(VideoRecord(
        video_id=video_id,
        filename=f"{video_id}.mp4",
        fps=probe.fps,
        frame_count=probe.frame_count,
        width=probe.width,
        height=probe.height,
        proxy_path=proxy_rel,
    ))

    for shot_index, (start, end) in enumerate(shots):
        kf_rel = store.make_relative(kf_paths[shot_index], config.repo_root)
        store.upsert_shot(ShotRecord(
            shot_id=make_shot_id(video_id, shot_index),
            video_id=video_id,
            shot_index=shot_index,
            start_frame=start,
            end_frame=end,
            keyframe_path=kf_rel,
        ))

    return ProcessResult(video_id=video_id, shot_count=len(shots), skipped=False, fps=probe.fps)
