"""Phase 4 end-to-end verification — Phase 2/3/4 checks."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run(script: str, extra: list[str] | None = None) -> int:
    cmd = [sys.executable, str(REPO / "scripts" / script)] + (extra or [])
    print(f"\n--- {script} ---")
    return subprocess.call(cmd, cwd=str(REPO))


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4 joint verification")
    parser.add_argument(
        "--live-dres", action="store_true",
        help="Test DRES login (requires credentials)",
    )
    args = parser.parse_args()

    failed = 0
    print("=== Phase 4 joint verification ===")

    for script in ("verify_phase2_joint.py", "verify_dres_payload.py"):
        if _run(script) != 0:
            failed += 1

    faiss_index = REPO / "data" / "processed" / "faiss.index"
    if faiss_index.is_file():
        if _run("verify_phase3_index.py") != 0:
            failed += 1
        if _run("verify_phase3_search.py") != 0:
            failed += 1
    else:
        print("\nSKIP Phase 3 checks (no FAISS index)")

    print("\n--- mock DRES submit smoke (00001, 00058) ---")
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(REPO / "ContBVideoRetr"))
    from pipeline.config import load_config  # noqa: E402
    from pipeline.db.store import MetadataStore  # noqa: E402
    from services.catalog_client import _dict_to_result_item  # noqa: E402
    from services.dres_config import load_dres_settings  # noqa: E402
    from services.dres_http_client import create_dres_client  # noqa: E402

    cfg = load_config(REPO / "config.yaml")
    dres_settings = load_dres_settings(REPO / "config.yaml")
    store = MetadataStore(cfg.output.db_path, cfg.repo_root)
    client = create_dres_client()
    print(f"DRES client: {'live' if client.is_live else client.status_label}")

    timing = {"00001": 6080, "00058": 10176}
    for vid, exp_end in timing.items():
        rows = store.list_shots(limit=1, offset=0, video_id=vid)
        if not rows:
            print(f"FAIL {vid}: not in catalog")
            failed += 1
            continue
        item = _dict_to_result_item(store.to_result_item(rows[0]))
        result = client.submit(item, "phase4_smoke", evaluation_id=dres_settings.evaluation_id)
        ok = result.ok and result.payload.end_ms == exp_end
        print(
            f"{'OK' if ok else 'FAIL'} submit {vid}: end_ms={result.payload.end_ms} "
            f"(expected {exp_end})"
        )
        if not ok:
            failed += 1

    if args.live_dres:
        sys.path.insert(0, str(REPO / "ContBVideoRetr"))
        from services.dres_http_client import HttpDresClient, DresConnectionError  # noqa: E402

        print("\n--- live DRES login ---")
        try:
            client = HttpDresClient()
            client.login()
            evals = client.list_evaluations()
            print(f"OK login; {len(evals)} evaluation(s) listed")
        except DresConnectionError as exc:
            print(f"FAIL live DRES: {exc}")
            failed += 1

    print(f"\n=== Phase 4 verification {'FAILED' if failed else 'OK'} ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
