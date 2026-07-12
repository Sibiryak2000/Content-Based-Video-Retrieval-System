"""Run the Phase 1 prototype pipeline on sample videos."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.config import load_config  # noqa: E402
from pipeline.db.models import ShotRecord, VideoRecord  # noqa: E402
from pipeline.db.store import MetadataStore  # noqa: E402
from pipeline.inventory import run_inventory, save_inventory_report  # noqa: E402
from pipeline.keyframes import extract_keyframes_for_video  # noqa: E402
from pipeline.probe import probe_video  # noqa: E402
from pipeline.scenes import load_shots, make_shot_id  # noqa: E402
from pipeline.transcode import copy_as_proxy, ffmpeg_available, transcode_proxy  # noqa: E402


def run_prototype(config_path: Path, skip_inventory: bool = False) -> dict:
    config = load_config(config_path)
    config.ensure_output_dirs()
    store = MetadataStore(config.output.db_path, config.repo_root)
    store.init_schema()

    summary: dict = {"sample_videos": [], "ffmpeg": ffmpeg_available()}

    if not skip_inventory:
        print("Running full dataset inventory (probing all videos)...")
        report = run_inventory(config, probe_all=True)
        save_inventory_report(report, config.output.inventory_report)
        summary["inventory"] = {
            "video_count": report.video_count,
            "scene_file_count": report.scene_file_count,
            "matched_ids": report.matched_ids,
            "error_count": sum(1 for e in report.entries if e.errors),
            "missing_id_gaps": report.missing_id_gaps,
            "report_path": str(config.output.inventory_report),
        }
        print(f"  videos={report.video_count} scenes={report.scene_file_count} "
              f"errors={summary['inventory']['error_count']}")

    sample_ids = config.prototype.sample_video_ids
    strategy = config.prototype.keyframe_strategy
    use_ffmpeg = ffmpeg_available()

    for video_id in sample_ids:
        print(f"\nProcessing sample {video_id}...")
        video_path = config.dataset.videos_dir / f"{video_id}.mp4"
        if not video_path.is_file():
            raise FileNotFoundError(f"Missing video: {video_path}")

        shots = load_shots(video_id, config.dataset.scenes_zip, config.dataset.scenes_prefix)
        probe = probe_video(video_path, video_id)

        proxy_out = config.output.proxies_dir / f"{video_id}.mp4"
        if use_ffmpeg:
            transcode_proxy(video_path, proxy_out, height=config.prototype.proxy_height)
            print(f"  proxy (ffmpeg): {proxy_out}")
        else:
            copy_as_proxy(video_path, proxy_out)
            print(f"  proxy (copy fallback — install ffmpeg for re-encode): {proxy_out}")

        kf_dir = config.output.keyframes_dir / video_id
        kf_paths = extract_keyframes_for_video(
            video_path, video_id, shots, kf_dir, strategy=strategy,
        )
        print(f"  keyframes: {len(kf_paths)} files in {kf_dir}")

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

        sample_items = store.export_sample_result_items(video_id, limit=2)
        summary["sample_videos"].append({
            "video_id": video_id,
            "shot_count": len(shots),
            "fps": probe.fps,
            "proxy_path": str(proxy_out),
            "example_result_items": sample_items,
        })

    run_id = store.log_run(config_path, notes="phase1_prototype")
    summary["pipeline_run_id"] = run_id
    summary["db_path"] = str(config.output.db_path)

    sample_export = config.output.root / "sample_result_items.json"
    sample_export.write_text(json.dumps(summary["sample_videos"], indent=2), encoding="utf-8")
    summary["sample_export"] = str(sample_export)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="IVADL R2 Phase 1 prototype pipeline")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config.yaml")
    parser.add_argument("--skip-inventory", action="store_true",
                        help="Skip full 200-video inventory (faster re-runs)")
    args = parser.parse_args()

    summary = run_prototype(args.config, skip_inventory=args.skip_inventory)
    print("\n=== Phase 1 prototype complete ===")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
