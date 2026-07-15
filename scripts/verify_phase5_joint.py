"""Phase 5 pre-competition verification."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SAMPLES = ("00001", "00058", "00122")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-dres", action="store_true")
    args = parser.parse_args()

    failed = 0
    print("=== Phase 5 joint verification ===")

    cmd = [sys.executable, str(REPO / "scripts" / "verify_phase4_joint.py")]
    if args.live_dres:
        cmd.append("--live-dres")
    if subprocess.call(cmd, cwd=str(REPO)) != 0:
        failed += 1

    print("\n--- benchmark smoke ---")
    if subprocess.call(
        [sys.executable, str(REPO / "scripts" / "benchmark_retrieval.py"), "--smoke"],
        cwd=str(REPO),
    ) != 0:
        failed += 1

    print("\n--- sample proxy check ---")
    for vid in SAMPLES:
        proxy = REPO / "data" / "processed" / "proxies" / f"{vid}.mp4"
        ok = proxy.is_file()
        print(f"{'OK' if ok else 'WARN'} proxy {vid}")
        if not ok:
            failed += 1

    golden = REPO / "data" / "eval" / "golden_queries.yaml"
    if not golden.is_file():
        print("FAIL missing golden_queries.yaml")
        failed += 1
    else:
        print(f"OK golden queries ({golden.name})")

    print(f"\n=== Phase 5 verification {'FAILED' if failed else 'OK'} ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
