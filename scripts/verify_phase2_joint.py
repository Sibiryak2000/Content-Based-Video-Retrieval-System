"""Phase 2 joint verification — catalog browse, timing, asset checks."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ContBVideoRetr"))

from pipeline.config import load_config  # noqa: E402
from pipeline.db.store import MetadataStore  # noqa: E402
from services.catalog_client import create_catalog_client, _dict_to_result_item  # noqa: E402


def main() -> int:
    cfg = load_config(REPO / "config.yaml")
    store = MetadataStore(cfg.output.db_path, cfg.repo_root)
    client = create_catalog_client(REPO / "config.yaml")

    print("=== Phase 2 joint verification ===")
    print(f"Videos in DB: {store.count_videos()}")
    print(f"Shots in DB:  {store.count_shots()}")
    print(f"Catalog:      {client.source_label}")

    page = client.list_shots(48, 0)
    print(f"Page 1:       {len(page)} tiles")
    if page:
        kf_ok = sum(1 for i in page if i.keyframe_path and Path(i.keyframe_path).is_file())
        print(f"Keyframes OK: {kf_ok}/{len(page)}")

    # M3 timing matrix
    checks = [
        ("00001", 25.0, 0, 152, 0, 6080),
        ("00058", 23.976, 0, 244, 0, 10176),
    ]
    failed = 0
    for vid, exp_fps, sf, ef, exp_start_ms, exp_end_ms in checks:
        rows = store.list_shots(limit=1, offset=0, video_id=vid)
        if not rows:
            print(f"SKIP {vid} — not in catalog yet")
            continue
        ri = _dict_to_result_item(store.to_result_item(rows[0]))
        ok = (
            abs(ri.fps - exp_fps) < 0.05
            and ri.start_frame == sf
            and ri.end_frame == ef
            and ri.start_ms == exp_start_ms
            and ri.end_ms == exp_end_ms
        )
        status = "OK" if ok else "FAIL"
        print(f"{status} {vid}: fps={ri.fps:.3f} ms={ri.start_ms}-{ri.end_ms}")
        if not ok:
            failed += 1

    print("=== Done ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
