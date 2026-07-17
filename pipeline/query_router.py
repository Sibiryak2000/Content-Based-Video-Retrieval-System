"""R1 — KIS vs VQA query-mode detection and retrieval-request contract.

Phase 3: the GUI has a single search bar that must serve both Known-Item
Search (pure retrieval) and Visual Question Answering (retrieval + short
text answer) queries. This module decides which mode applies so R3's
service layer (services/vqa_service.py) knows whether to just rank shots
or also generate an answer.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

_QUESTION_WORDS = (
    "what", "who", "where", "when", "why", "how", "which",
    "is there", "are there", "how many", "does ", "do ",
)


class QueryMode(str, Enum):
    KIS = "kis"
    VQA = "vqa"


@dataclass(frozen=True)
class RetrievalRequest:
    raw_query: str
    mode: QueryMode
    question: str | None = None  # populated only for VQA


def detect_query_mode(query: str, explicit_mode: QueryMode | None = None) -> QueryMode:
    """Explicit GUI toggle (KIS/VQA) always wins; otherwise sniff question phrasing."""
    if explicit_mode is not None:
        return explicit_mode
    q = query.strip().lower()
    if q.endswith("?") or any(q.startswith(w) for w in _QUESTION_WORDS):
        return QueryMode.VQA
    return QueryMode.KIS


def build_request(query: str, explicit_mode: QueryMode | None = None) -> RetrievalRequest:
    mode = detect_query_mode(query, explicit_mode)
    return RetrievalRequest(raw_query=query, mode=mode, question=query.strip() if mode == QueryMode.VQA else None)
