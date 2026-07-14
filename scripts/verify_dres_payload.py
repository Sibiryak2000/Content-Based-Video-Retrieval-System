"""Verify DRES payload timing from metadata.db (R2/R4 compatibility gate)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ContBVideoRetr"))

from pipeline.config import load_config  # noqa: E402
from pipeline.db.store import MetadataStore  # noqa: E402
from services.catalog_client import _dict_to_result_item  # noqa: E402
from services.dres_client import COLLECTION_NAME, DresSubmitPayload  # noqa: E402

# video_id -> (start_ms, end_ms) for shot index 0
TIMING_MATRIX = {
    "00001": (0, 6080),
    "00058": (0, 10176),
}


def main() -> int:
    config = load_config(REPO / "config.yaml")
    store = MetadataStore(config.output.db_path, config.repo_root)

    print("=== DRES payload verification ===")
    failed = 0
    samples: list[dict] = []

    for video_id, (exp_start, exp_end) in TIMING_MATRIX.items():
        rows = store.list_shots(limit=1, offset=0, video_id=video_id)
        if not rows:
            print(f"FAIL {video_id}: not in catalog")
            failed += 1
            continue

        item = _dict_to_result_item(store.to_result_item(rows[0]))
        payload = DresSubmitPayload.from_result(item, "test_task", "IVADL2026")
        answer = payload.to_api_answer()

        ok = (
            payload.start_ms == exp_start
            and payload.end_ms == exp_end
            and answer["mediaItemName"] == video_id
            and answer["mediaCollectionName"] == COLLECTION_NAME
            and answer["start"] == exp_start
            and answer["end"] == exp_end
        )
        status = "OK" if ok else "FAIL"
        print(
            f"{status} {video_id}: fps={item.fps:.3f} "
            f"ms={payload.start_ms}-{payload.end_ms} (expected {exp_start}-{exp_end})"
        )
        if not ok:
            failed += 1

        samples.append({
            "evaluationId": payload.evaluation_id,
            "taskName": payload.task_name,
            "answers": [answer],
        })

    print("\nSample DRES API body:")
    print(json.dumps(samples[0] if samples else {}, indent=2))
    print("=== Done ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
