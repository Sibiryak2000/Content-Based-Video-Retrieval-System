"""Optional VIMEO metadata ingestion for videos.vimeo_description."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def find_vimeo_metadata_file(videos_dir: Path) -> Path | None:
    for p in sorted(videos_dir.iterdir()):
        if p.is_file() and "vimeo" in p.name.lower():
            if p.suffix.lower() in {".json", ".csv", ".txt"}:
                return p
    return None


def load_descriptions(videos_dir: Path) -> dict[str, str]:
    """Return video_id -> description mapping, or empty dict if no file."""
    path = find_vimeo_metadata_file(videos_dir)
    if path is None:
        return {}

    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        if isinstance(data, list):
            out: dict[str, str] = {}
            for row in data:
                vid = str(row.get("video_id") or row.get("id") or "")
                desc = row.get("description") or row.get("vimeo_description") or ""
                if vid:
                    out[vid] = str(desc)
            return out

    if path.suffix.lower() == ".csv":
        out = {}
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                vid = (row.get("video_id") or row.get("id") or "").strip()
                desc = (row.get("description") or row.get("vimeo_description") or "").strip()
                if vid:
                    out[vid] = desc
        return out

    return {}
