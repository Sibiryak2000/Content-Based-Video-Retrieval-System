"""R3 — DRES connection settings, loaded from config.yaml + env overrides."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class DresSettings:
    base_url: str
    username: str
    password: str
    evaluation_id: str = "IVADL2026"
    verify_ssl: bool = True
    timeout_s: float = 10.0


def load_dres_settings(config_path: Path | None = None) -> DresSettings:
    config_path = config_path or (REPO_ROOT / "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    dres_raw = raw.get("dres", {})

    return DresSettings(
        base_url=os.environ.get("DRES_BASE_URL", dres_raw.get("base_url", "https://vbs.videobrowsing.org")),
        username=os.environ.get("DRES_USERNAME", dres_raw.get("username", "")),
        password=os.environ.get("DRES_PASSWORD", dres_raw.get("password", "")),
        evaluation_id=os.environ.get("DRES_EVALUATION_ID", dres_raw.get("evaluation_id", "IVADL2026")),
        verify_ssl=bool(dres_raw.get("verify_ssl", True)),
        timeout_s=float(dres_raw.get("timeout_s", 10.0)),
    )
