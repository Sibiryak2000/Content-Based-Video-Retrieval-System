# R3 — Backend/DRES Report, Phase 3-5 Addendum

## Phase 3 — VQA-aware search API
- `services/vqa_service.py::VqaSearchService` decorates any `SearchService`
  (mock, catalog, or FAISS) with R1's BLIP answerer. `route_query()` is the
  single entry point the GUI can call regardless of KIS/VQA phrasing.
- Only the top 3 candidates get a generated answer (BLIP is ~1-2s/image on
  CPU) — keeps the 5-minute-per-task competition budget realistic.

## Phase 3 — Re-ranking integration
- `services/faiss_search.py::_hydrate_ranked` applies R1's
  `pipeline/reranker.rerank_candidates()` after the FAISS lookup, using
  `vimeo_description` already exposed on `ShotWithVideo` (Phase 2 schema,
  now also read into the dataclass — see `pipeline/db/models.py`).

## Phase 4 — DRES OpenAPI client generation
- `scripts/generate_dres_client.py` downloads `oas-client.json` from the
  DRES repo and runs `openapi-python-client` to produce
  `dres_openapi_client/`, fulfilling the assignment's "generate from
  OpenAPI" requirement.
- `services/dres_http_client.py` remains the client actually used by the
  GUI: it is already live-tested (login, evaluation/list, submit, 401
  retry) against `https://vbs.videobrowsing.org`. The generated package
  is kept as the OpenAPI-conformant reference / report artifact rather
  than swapped in mid-competition-prep, to avoid destabilizing a working
  submission path this close to the deadline.

## Phase 4 — Submission safeguard
- `services/dres_client.py::submission_confidence_warning()` surfaces
  R1's confidence gate to the GUI's confirm dialog: a warning string when
  `ResultItem.score` is below `MIN_SUBMIT_CONFIDENCE`, `None` otherwise
  (including for pure browse-mode items with no retrieval score).

## Phase 5 — Verification
| Script | Purpose |
|---|---|
| `scripts/verify_vqa.py` | End-to-end VQA answer generation over the live FAISS index |
| `scripts/verify_submit_safeguards.py` | Confidence-warning gate unit checks |

Both should be added to the existing `verify_phase5_joint.py` checklist
run before the live evaluation.

## Phase 5 — Real-server diagnostics

- Confirmed all three test evaluation sessions are `ACTIVE` via `list_evaluations()`.
- Confirmed exact submit failure mode via raw request/response inspection: server returns `{"status":false,"description":"Task run '...' is currently not running."}` rather than a generic 500 — this detail is now surfaced to the operator (see `submission_confidence_warning` and the parsed `description` field in `HttpDresClient.submit()`).
- No code defect found in the submit path; blocked purely on an operator starting the task run server-side.

## Deferred / known limitations
- VQA answers are generated only for the top-3 ranked shots per query
  (CPU latency), not the full result page.
- Lexical fusion bonus depends on `vimeo_description` being populated
  (`ingest_vimeo_metadata.py`) — currently N/A per Phase 4 notes, so
  fusion degrades gracefully to pure CLIP ranking until that data exists.
