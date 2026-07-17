"""R1 — Phase 4 late-fusion re-ranking and submission-confidence gating.

Combines the CLIP cosine similarity (dominant signal) with a small lexical
overlap bonus against `videos.vimeo_description` when available, so a query
term matching the upload text can break a near-tie. Also exposes a
confidence gate: DRES penalises a wrong submission by -100 points, so the
GUI/R3 submit flow should warn (not block) on a low-confidence match.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_RE = re.compile(r"[a-z0-9]+")

# Small on purpose: semantic score must stay the primary ranking signal.
LEXICAL_BONUS_WEIGHT = 0.05

# Soft warning threshold only — never used to hide results.
MIN_SUBMIT_CONFIDENCE = 0.22


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def lexical_overlap_bonus(query: str, description: str | None) -> float:
    if not description:
        return 0.0
    q_tokens = _tokenize(query)
    if not q_tokens:
        return 0.0
    overlap = len(q_tokens & _tokenize(description)) / len(q_tokens)
    return overlap * LEXICAL_BONUS_WEIGHT


@dataclass
class RankedCandidate:
    shot_id: str
    clip_score: float
    description: str | None = None


def rerank_candidates(query: str, candidates: list[RankedCandidate]) -> list[RankedCandidate]:
    """Return candidates sorted by clip_score + lexical bonus, descending."""
    scored = [(c, c.clip_score + lexical_overlap_bonus(query, c.description)) for c in candidates]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [c for c, _ in scored]


def is_confident_match(score: float, threshold: float = MIN_SUBMIT_CONFIDENCE) -> bool:
    return score >= threshold
