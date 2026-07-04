"""Mock result provider for the GUI shell.

Phase 1 has no real search backend yet, so this module fabricates ResultItems.
If real (transcoded) video files are dropped into ``ContRetr/sample_videos/``
they are picked up automatically so the fullscreen player actually plays
something; otherwise placeholder tiles are shown.
"""

from __future__ import annotations

import os
from typing import List

from models.result_item import ResultItem

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}

_SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_videos")

_TITLES = [
    "City street at night", "Person riding a bicycle", "Aerial view of coastline",
    "Cooking in a kitchen", "Crowd at a concert", "Dog running in a park",
    "Train arriving at station", "Snowy mountain landscape", "Children playing football",
    "Busy market stalls", "Sunset over the ocean", "Car driving through tunnel",
    "Waterfall in the forest", "Fireworks over a city", "Diver exploring a reef",
    "Rainy window close-up",
]


def _scan_sample_videos() -> List[str]:
    if not os.path.isdir(_SAMPLE_DIR):
        return []
    files = []
    for name in sorted(os.listdir(_SAMPLE_DIR)):
        if os.path.splitext(name)[1].lower() in VIDEO_EXTS:
            files.append(os.path.join(_SAMPLE_DIR, name))
    return files


def get_mock_results(query: str = "") -> List[ResultItem]:
    """Return mock results, optionally filtered by a query substring."""
    videos = _scan_sample_videos()
    items: List[ResultItem] = []

    if videos:
        for i, proxy in enumerate(videos):
            stem = os.path.splitext(os.path.basename(proxy))[0]
            title = stem.replace("_", " ").title()
            items.append(ResultItem(
                video_id=stem,
                shot_id=f"{stem}_1",
                title=title,
                proxy_path=proxy,
                start_frame=0,
                end_frame=75,
                fps=25.0,
                score=round(1.0 - i * 0.03, 3),
            ))
    else:
        for i, title in enumerate(_TITLES):
            items.append(ResultItem(
                video_id=f"{i:05d}",
                shot_id=f"{i:05d}_1",
                title=title,
                proxy_path=None,
                start_frame=0,
                end_frame=150,
                fps=25.0,
                score=round(1.0 - i * 0.03, 3),
            ))

    if query:
        q = query.strip().lower()
        items = [it for it in items if q in it.display_title.lower()]
    return items
