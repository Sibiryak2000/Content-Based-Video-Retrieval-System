"""Export metrics for the course report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.config import load_config  # noqa: E402
from pipeline.db.store import MetadataStore  # noqa: E402

PROCESSED = REPO / "data" / "processed"
BENCHMARK = REPO / "data" / "eval" / "benchmark_results.json"
OUT = REPO / "data" / "eval" / "report_metrics.json"


def main() -> int:
    config = load_config(REPO / "config.yaml")
    store = MetadataStore(config.output.db_path, config.repo_root)

    metrics: dict = {
        "video_count": store.count_videos(),
        "shot_count": store.count_shots(),
    }

    manifest_path = PROCESSED / "embedding_manifest.json"
    if manifest_path.is_file():
        metrics["embedding_manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))

    if BENCHMARK.is_file():
        metrics["benchmark"] = json.loads(BENCHMARK.read_text(encoding="utf-8"))

    with store.connect() as conn:
        runs = conn.execute(
            "SELECT run_id, timestamp, git_commit, notes FROM pipeline_runs ORDER BY run_id DESC LIMIT 10"
        ).fetchall()
        metrics["recent_pipeline_runs"] = [dict(r) for r in runs]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
