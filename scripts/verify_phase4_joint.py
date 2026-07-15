"""Phase 4 end-to-end verification."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run(script: str) -> int:
    print(f"\n--- {script} ---")
    return subprocess.call([sys.executable, str(REPO / "scripts" / script)], cwd=str(REPO))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-dres", action="store_true")
    args = parser.parse_args()

    failed = 0
    print("=== Phase 4 joint verification ===")
    for script in ("verify_phase2_joint.py", "verify_dres_payload.py"):
        if _run(script) != 0:
            failed += 1

    if (REPO / "data" / "processed" / "faiss.index").is_file():
        for script in ("verify_phase3_index.py", "verify_phase3_search.py"):
            if _run(script) != 0:
                failed += 1

    print("\n--- mock DRES submit smoke ---")
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(REPO / "ContBVideoRetr"))
    from pipeline.config import load_config  # noqa: E402
    from pipeline.db.store import MetadataStore  # noqa: E402
    from services.catalog_client import _dict_to_result_item  # noqa: E402
    from services.dres_config import load_dres_settings  # noqa: E402
    from services.dres_http_client import create_dres_client  # noqa: E402

    cfg = load_config(REPO / "config.yaml")
    dres = load_dres_settings(REPO / "config.yaml")
    store = MetadataStore(cfg.output.db_path, cfg.repo_root)
    client = create_dres_client()
    for vid, exp_end in {"00001": 6080, "00058": 10176}.items():
        rows = store.list_shots(1, 0, video_id=vid)
        if not rows:
            failed += 1
            continue
        item = _dict_to_result_item(store.to_result_item(rows[0]))
        result = client.submit(item, "phase4_smoke", evaluation_id=dres.evaluation_id)
        ok = result.ok and result.payload.end_ms == exp_end
        print(f"{'OK' if ok else 'FAIL'} submit {vid}")
        if not ok:
            failed += 1

    if args.live_dres:
        from services.dres_http_client import HttpDresClient, DresConnectionError  # noqa: E402
        try:
            HttpDresClient().login()
            print("OK live DRES login")
        except DresConnectionError as exc:
            print(f"FAIL live DRES: {exc}")
            failed += 1

    print(f"\n=== Phase 4 verification {'FAILED' if failed else 'OK'} ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
