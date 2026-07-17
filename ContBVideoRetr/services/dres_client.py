"""DRES submission client (mock + shared payload contract)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional, Protocol

from models.result_item import ResultItem

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.reranker import MIN_SUBMIT_CONFIDENCE, is_confident_match  # noqa: E402

logger = logging.getLogger(__name__)

COLLECTION_NAME = "IVADL"
DEFAULT_EVALUATION_ID = "IVADL2026"


@dataclass
class DresSubmitPayload:
    evaluation_id: str
    task_name: str
    video_id: str
    collection: str
    start_ms: int
    end_ms: int
    text: Optional[str] = None

    @classmethod
    def from_result(cls, item: ResultItem, task_name: str,
                    evaluation_id: str = DEFAULT_EVALUATION_ID) -> "DresSubmitPayload":
        return cls(
            evaluation_id=evaluation_id,
            task_name=task_name,
            video_id=item.video_id,
            collection=COLLECTION_NAME,
            start_ms=item.start_ms,
            end_ms=item.end_ms,
            text=item.text,
        )

    def to_api_answer(self) -> dict:
        return {
            "text": self.text,
            "mediaItemName": self.video_id,
            "mediaCollectionName": self.collection,
            "start": self.start_ms,
            "end": self.end_ms,
        }


@dataclass
class DresSubmitResult:
    ok: bool
    message: str
    payload: DresSubmitPayload


class DresClient(Protocol):
    is_live: bool
    status_label: str

    def submit(self, item: ResultItem, task_name: str,
               evaluation_id: str = DEFAULT_EVALUATION_ID) -> DresSubmitResult: ...


class MockDresClient:
    is_live: bool = False

    def __init__(self, status_label: str = "mock (no credentials)"):
        self.status_label = status_label

    def submit(self, item: ResultItem, task_name: str,
               evaluation_id: str = DEFAULT_EVALUATION_ID) -> DresSubmitResult:
        payload = DresSubmitPayload.from_result(item, task_name, evaluation_id)
        body = {
            "evaluationId": payload.evaluation_id,
            "taskName": payload.task_name,
            "answers": [payload.to_api_answer()],
        }
        logger.info("DRES mock submit: %s", json.dumps(body, indent=2))
        return DresSubmitResult(
            ok=True,
            message=(
                f"Mock submission accepted for task '{task_name}'.\n"
                f"Video: {payload.video_id}  "
                f"({payload.start_ms}-{payload.end_ms} ms)"
            ),
            payload=payload,
        )

    def current_task_name(self, evaluation_id: str) -> Optional[str]:
        return None

def submission_confidence_warning(item: ResultItem, threshold: float = MIN_SUBMIT_CONFIDENCE) -> Optional[str]:
    """R1/R3 Phase 4 safeguard: DRES penalises a wrong submission by -100
    points, so a low-similarity match should be flagged (not blocked) before
    the GUI's confirm-and-submit step. Returns None when the match looks
    confident enough, or when the item has no retrieval score (pure browse)."""
    if item.score <= 0:
        return None
    if is_confident_match(item.score, threshold):
        return None
    return (
        f"Low match confidence (score={item.score:.2f}). "
        f"A wrong DRES submission costs 100 points — double-check before submitting."
    )
