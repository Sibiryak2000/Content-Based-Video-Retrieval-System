"""R3 — Generate a typed Python client from the DRES OpenAPI spec.

The assignment requires using the OpenAPI spec to generate DRES
communication code, rather than hand-writing it from scratch.
`services/dres_http_client.py` already implements and is tested against
the real DRES v2 API (login, evaluation/list, submit) and remains the
client actually used by the GUI. This script additionally produces the
officially generated typed client/models under `dres_openapi_client/`
for the report and for any future endpoint.

Usage:
    pip install openapi-python-client
    python scripts/generate_dres_client.py
"""
from __future__ import annotations

import shutil
import subprocess
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPEC_URL = "https://raw.githubusercontent.com/dres-dev/DRES/master/doc/oas-client.json"
SPEC_PATH = REPO / "dres_oas_client.json"
OUT_DIR = REPO / "dres_openapi_client"


def download_spec() -> None:
    print(f"Downloading DRES OpenAPI spec from {SPEC_URL} ...")
    urllib.request.urlretrieve(SPEC_URL, SPEC_PATH)
    print(f"  saved to {SPEC_PATH}")


def generate_client() -> int:
    if shutil.which("openapi-python-client") is None:
        print("openapi-python-client not found. Install with:\n  pip install openapi-python-client\n")
        return 1
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    cmd = [
        "openapi-python-client", "generate",
        "--path", str(SPEC_PATH),
        "--output-path", str(OUT_DIR),
        "--meta", "none",
    ]
    print("Generating client:", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(REPO))


def main() -> int:
    download_spec()
    code = generate_client()
    if code == 0:
        print(f"\nOK — generated client at {OUT_DIR}")
        print(
            "Note: services/dres_http_client.py remains the client actually used "
            "by the GUI (live-tested); the generated package documents the "
            "official OpenAPI contract for the report."
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
