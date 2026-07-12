"""Resolve paths stored relative to the repository root."""

from __future__ import annotations

from pathlib import Path


def resolve_repo_path(path_str: str | None, repo_root: Path) -> str | None:
    if not path_str:
        return None
    p = Path(path_str)
    if p.is_absolute():
        return str(p.resolve())
    return str((repo_root / p).resolve())
