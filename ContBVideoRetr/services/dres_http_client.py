"""R3 — real DRES HTTP client (Phase 1-2: login + evaluation/list only;
submit() is wired in Phase 4 but implemented now so early end-to-end
connectivity can be verified per the assignment's warning).

Session-cookie based login, matching the DRES OpenAPI spec
(https://github.com/dres-dev/DRES/blob/master/doc/oas-client.json).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests

from models.result_item import ResultItem
from services.dres_client import (
    COLLECTION_NAME,
    DresSubmitPayload,
    DresSubmitResult,
)
from services.dres_config import DresSettings, load_dres_settings

logger = logging.getLogger(__name__)


@dataclass
class EvaluationInfo:
    evaluation_id: str
    name: str
    status: str


class DresConnectionError(RuntimeError):
    pass


class HttpDresClient:
    """Real DRES client. Falls back gracefully — callers should catch
    DresConnectionError and use MockDresClient if the server is unreachable."""

    def __init__(self, settings: Optional[DresSettings] = None):
        self.settings = settings or load_dres_settings()
        self._session = requests.Session()
        self._session_id: Optional[str] = None

    def login(self) -> bool:
        url = f"{self.settings.base_url}/api/v2/login"
        body = {"username": self.settings.username, "password": self.settings.password}
        try:
            resp = self._session.post(
                url, json=body,
                timeout=self.settings.timeout_s,
                verify=self.settings.verify_ssl,
            )
            resp.raise_for_status()
            data = resp.json()
            self._session_id = data.get("sessionId")
            logger.info("DRES login OK for user %s", self.settings.username)
            return True
        except requests.RequestException as exc:
            logger.error("DRES login failed: %s", exc)
            raise DresConnectionError(str(exc)) from exc

    def list_evaluations(self) -> list[EvaluationInfo]:
        if not self._session_id:
            self.login()
        url = f"{self.settings.base_url}/api/v2/client/evaluation/list"
        try:
            resp = self._session.get(
                url,
                params={"session": self._session_id},
                timeout=self.settings.timeout_s,
                verify=self.settings.verify_ssl,
            )
            resp.raise_for_status()
            items = resp.json()
            return [
                EvaluationInfo(
                    evaluation_id=it.get("id", ""),
                    name=it.get("name", ""),
                    status=it.get("status", ""),
                )
                for it in items
            ]
        except requests.RequestException as exc:
            logger.error("DRES evaluation/list failed: %s", exc)
            raise DresConnectionError(str(exc)) from exc

    def submit(self, item: ResultItem, task_name: str,
               evaluation_id: Optional[str] = None) -> DresSubmitResult:
        """Phase 4 will finalize retries/logging; core call implemented now."""
        eval_id = evaluation_id or self.settings.evaluation_id
        payload = DresSubmitPayload.from_result(item, task_name, eval_id)
        url = f"{self.settings.base_url}/api/v2/submit/{eval_id}"
        body = {"answerSets": [{
            "taskId": task_name,
            "answers": [payload.to_api_answer()],
        }]}
        try:
            resp = self._session.post(
                url, json=body,
                params={"session": self._session_id},
                timeout=self.settings.timeout_s,
                verify=self.settings.verify_ssl,
            )
            resp.raise_for_status()
            return DresSubmitResult(
                ok=True,
                message=f"DRES accepted submission for '{task_name}': "
                        f"{payload.video_id} ({payload.start_ms}-{payload.end_ms} ms)",
                payload=payload,
            )
        except requests.RequestException as exc:
            logger.error("DRES submit failed: %s", exc)
            return DresSubmitResult(ok=False, message=str(exc), payload=payload)


def create_dres_client():
    """Factory: real client if credentials configured + reachable, else Mock.
    Import MockDresClient lazily to avoid a hard dependency loop."""
    from services.dres_client import MockDresClient

    settings = load_dres_settings()
    if not settings.username or not settings.password:
        logger.warning("No DRES credentials configured — using MockDresClient.")
        return MockDresClient()

    client = HttpDresClient(settings)
    try:
        client.login()
        return client
    except DresConnectionError:
        logger.warning("DRES unreachable — falling back to MockDresClient.")
        return MockDresClient()
