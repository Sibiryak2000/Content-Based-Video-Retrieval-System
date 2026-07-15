"""Rebuild FAISS index (encode + build + verify)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild embeddings + FAISS index")
    parser.add_argument("--config", type=Path, default=REPO / "config.yaml")
    parser.add_argument("--force", action="store_true", help="Force full re-encode")
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()

    index_script = REPO / "scripts" / "run_phase3_index.py"
    cmd = [sys.executable, str(index_script), "--config", str(args.config)]
    if args.force:
        cmd.append("--force")
    print("=== Rebuild index ===")
    if subprocess.call(cmd, cwd=str(REPO)) != 0:
        return 1

    if args.skip_verify:
        return 0

    for script in ("verify_phase3_index.py", "verify_phase3_search.py"):
        if subprocess.call([sys.executable, str(REPO / "scripts" / script)], cwd=str(REPO)) != 0:
            return 1
    print("=== Index rebuild OK ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
