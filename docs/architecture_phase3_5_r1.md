# R1 — Architecture Report, Phase 3-5 Addendum

## Phase 3 — VQA + query routing
- `pipeline/vqa.py`: BLIP (`Salesforce/blip-vqa-base`) generates a short
  free-text answer per keyframe — pretrained inference only, no training.
- `pipeline/query_router.py`: single search bar, both KIS and VQA. An
  explicit GUI toggle wins; otherwise a question-phrasing heuristic
  (`what/who/where/...`, trailing `?`) selects VQA mode.
- Kept fully decoupled from R2's FAISS index and R3's search API — R3
  wires it in via `services/vqa_service.py`.

## Phase 4 — Re-ranking, fusion, precision tuning
- `pipeline/reranker.py`: CLIP cosine similarity remains the dominant
  ranking signal; a small lexical-overlap bonus (weight 0.05) against
  `videos.vimeo_description` breaks near-ties without overpowering the
  semantic score.
- `MIN_SUBMIT_CONFIDENCE = 0.22`: soft threshold below which a match is
  flagged as low-confidence in the DRES submit dialog (never hidden).
  Chosen conservatively from observed benchmark score distributions
  (`benchmark_retrieval.py`); revisit after a full golden-query run.
- Sign-off: ranking/fusion behaviour is exercised end-to-end by
  `scripts/verify_vqa.py` and `scripts/verify_submit_safeguards.py`.

## Phase 5 — Integration support
- Reviewed `services/faiss_search.py` integration of the reranker; no
  regression to plain browse/similarity paths (those bypass reranking).
- Default query behaviour for the live competition: KIS stays the
  default for ambiguous queries (faster, lower false-negative risk under
  the 5-minute clock); VQA only triggers on clear question phrasing or
  the explicit GUI toggle.

## Live DRES diagnosis (Phase 5)

Real submit initially failed with `500`/`404` against the live server. Root-caused via `client/evaluation/currentTask/{evaluationId}` — DRES distinguishes evaluation (session), task template (visible to viewers), and task **run** (the actual timed window); submit is only accepted while a task run is active. This is expected behavior outside a live evaluation window, not a client-side defect — confirmed end-to-end with a real `submit()` call once the exact active task name ("Test 01") was used.

## GenAI usage notes (Phase 3-5)
- VQA model choice (BLIP vs SigLIP/CLIP for direct answer generation)
  and the reranking formula were drafted with GenAI assistance and
  reviewed against the assignment's precision/penalty constraints
  (DRES: -100 points per wrong submission).
