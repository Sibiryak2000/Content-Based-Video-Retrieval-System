"""Ingest VIMEO descriptions into metadata.db (no-op if metadata file absent)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.config import load_config  # noqa: E402
from pipeline.db.models import VideoRecord  # noqa: E402
from pipeline.db.store import MetadataStore  # noqa: E402
from pipeline.metadata_vimeo import find_vimeo_metadata_file, load_descriptions  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest VIMEO metadata into SQLite")
    parser.add_argument("--config", type=Path, default=REPO / "config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    store = MetadataStore(config.output.db_path, config.repo_root)

    meta_file = find_vimeo_metadata_file(config.dataset.videos_dir)
    if meta_file is None:
        print("No VIMEO metadata file in dataset/ — nothing to ingest.")
        return 0

    descriptions = load_descriptions(config.dataset.videos_dir)
    updated = 0
    with store.connect() as conn:
        for video_id, desc in descriptions.items():
            row = conn.execute(
                "SELECT filename, fps, frame_count, width, height, proxy_path FROM videos WHERE video_id = ?",
                (video_id,),
            ).fetchone()
            if not row:
                continue
            store.upsert_video(VideoRecord(
                video_id=video_id,
                filename=row["filename"],
                fps=row["fps"],
                frame_count=row["frame_count"],
                width=row["width"],
                height=row["height"],
                proxy_path=row["proxy_path"],
                vimeo_description=desc,
            ))
            updated += 1

    print(f"Ingested {updated} VIMEO descriptions from {meta_file.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
