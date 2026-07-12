"""Run the Phase 2 batch pipeline on all (or selected) videos."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.config import load_config  # noqa: E402
from pipeline.db.store import MetadataStore  # noqa: E402
from pipeline.inventory import list_video_ids  # noqa: E402
from pipeline.process_video import is_video_complete, process_video  # noqa: E402
from pipeline.scenes import load_shots  # noqa: E402
from pipeline.transcode import ffmpeg_available  # noqa: E402


def export_phase2_stats(config_path: Path) -> dict:
    config = load_config(config_path)
    store = MetadataStore(config.output.db_path, config.repo_root)
    stats = {
        "video_count": store.count_videos(),
        "shot_count": store.count_shots(),
        "db_path": str(config.output.db_path),
    }
    missing_kf = 0
    missing_proxy = 0
    with store.connect() as conn:
        for r in conn.execute("SELECT video_id, proxy_path FROM videos").fetchall():
            if not r["proxy_path"]:
                missing_proxy += 1
                continue
            if not (config.repo_root / r["proxy_path"]).is_file():
                missing_proxy += 1
        for r in conn.execute("SELECT keyframe_path FROM shots").fetchall():
            kp = r["keyframe_path"]
            if not kp or not (config.repo_root / kp).is_file():
                missing_kf += 1
    stats["missing_keyframes"] = missing_kf
    stats["missing_proxies"] = missing_proxy
    out = config.output.root / "phase2_stats.json"
    out.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    stats["stats_path"] = str(out)
    return stats


def run_batch(
    config_path: Path,
    video_ids: list[str],
    skip_existing: bool = False,
    skip_keyframes: bool = False,
    skip_proxies: bool = False,
) -> dict:
    config = load_config(config_path)
    config.ensure_output_dirs()
    store = MetadataStore(config.output.db_path, config.repo_root)
    store.init_schema()

    processed = skipped = failed = 0
    errors: list[dict] = []
    use_ffmpeg = ffmpeg_available()

    for i, video_id in enumerate(video_ids, start=1):
        try:
            shots = load_shots(video_id, config.dataset.scenes_zip, config.dataset.scenes_prefix)
            if skip_existing and is_video_complete(store, config, video_id, len(shots)):
                skipped += 1
                print(f"[{i}/{len(video_ids)}] skip {video_id} (complete)", flush=True)
                continue

            print(f"[{i}/{len(video_ids)}] processing {video_id} ({len(shots)} shots)...", flush=True)
            result = process_video(
                config, store, video_id,
                skip_keyframes=skip_keyframes,
                skip_proxies=skip_proxies,
                use_ffmpeg=use_ffmpeg,
            )
            processed += 1
            print(f"  done fps={result.fps} shots={result.shot_count}", flush=True)
        except Exception as exc:
            failed += 1
            errors.append({"video_id": video_id, "error": str(exc)})
            print(f"  FAILED {video_id}: {exc}", flush=True)

    run_id = store.log_run(config_path, notes=f"phase2_batch processed={processed} skipped={skipped}")
    stats = export_phase2_stats(config_path)
    return {
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
        "ffmpeg": use_ffmpeg,
        "pipeline_run_id": run_id,
        **stats,
    }


def select_video_ids(
    all_ids: list[str],
    video_id: str | None,
    from_id: str | None,
    to_id: str | None,
) -> list[str]:
    if video_id:
        return [video_id]
    ids = all_ids
    if from_id:
        ids = [v for v in ids if v >= from_id]
    if to_id:
        ids = [v for v in ids if v <= to_id]
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description="IVADL R2 Phase 2 batch pipeline")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config.yaml")
    parser.add_argument("--video-id", type=str, help="Process a single video ID")
    parser.add_argument("--from", dest="from_id", type=str, help="Start video ID (inclusive)")
    parser.add_argument("--to", dest="to_id", type=str, help="End video ID (inclusive)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip fully processed videos")
    parser.add_argument("--skip-keyframes", action="store_true")
    parser.add_argument("--skip-proxies", action="store_true")
    parser.add_argument("--stats-only", action="store_true", help="Only export phase2_stats.json")
    args = parser.parse_args()

    if args.stats_only:
        stats = export_phase2_stats(args.config)
        print(json.dumps(stats, indent=2))
        return 0

    config = load_config(args.config)
    all_ids = list_video_ids(config.dataset.videos_dir)
    video_ids = select_video_ids(all_ids, args.video_id, args.from_id, args.to_id)

    summary = run_batch(
        args.config, video_ids,
        skip_existing=args.skip_existing,
        skip_keyframes=args.skip_keyframes,
        skip_proxies=args.skip_proxies,
    )
    print("\n=== Phase 2 batch complete ===")
    print(json.dumps(summary, indent=2))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
