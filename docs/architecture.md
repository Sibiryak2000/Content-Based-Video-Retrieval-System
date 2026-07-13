# Architecture & Model Strategy — R1 Report (Phase 1-2)

## Model selection (Phase 1)

- Chosen: CLIP ViT-B/32 (openai/clip-vit-base-patch32) for both image and
  text encoding — zero-shot text-to-image retrieval, 512-dim embeddings,
  CPU-inference feasible for ~14k shots.
- Alternatives considered: SigLIP (slightly better zero-shot accuracy, heavier),
  BLIP (better for captioning/VQA text generation, slower for pure retrieval).
- Similarity metric: cosine similarity (normalized dot product) — see
  pipeline/embedding_spec.py::EmbeddingConfig.

## Keyframe policy (Phase 2 review)

- R2 implements mid_frame extraction (one JPEG per shot) — sufficient for
  Phase 2 given the time budget; see pipeline/embedding_spec.py::KeyframePolicy.
- Reserved for Phase 3: multi-frame sampling for shots > 75 frames (~3s)
  if retrieval quality on fast-motion shots proves insufficient.

## Preprocessing contract

- All model-specific resizing/normalization is isolated in
  pipeline/preprocessing.py, so R2's raw JPEGs stay reusable across model
  choices (swap EmbeddingConfig.image_model without re-running the pipeline).

## Data flow (locked Phase 1 interface)

TransNet2 shots -> R2 keyframes (mid_frame JPEG) -> R1 preprocessing (224x224, CLIP norm)
-> R1 embeddings (Phase 3) -> R2 FAISS index (Phase 3) -> R3 search API (Phase 3)
-> R4 GUI results grid -> R3 DRES submit

## Review of R2 Phase 2 outputs

- 200/200 videos processed, 14,345 shots, 0 missing keyframes/proxies on disk.
- Known issue: 00016/00024 have corrupt H.264 segments -> gray placeholder
  JPEGs written; flagged for exclusion or re-check before embedding in Phase 3
  since a blank embedding would pollute the index.

## Next steps (Phase 3 handoff)

1. Implement pipeline/embeddings.py (R1): batch-encode all keyframes with
   CLIP ViT-B/32, using pipeline/preprocessing.py for normalization.
2. Exclude or re-verify 00016/00024 placeholder shots before indexing.
3. Persist embeddings alongside shot_id for R2's FAISS index builder.
4. Hand off the stable EmbeddingConfig (dim, metric) to R2 for index creation
   and to R3 for the similarity_query() implementation in search_api.py.

## GenAI usage notes (Phase 1-2)

- Model shortlist (CLIP/SigLIP/BLIP) and preprocessing pipeline drafted with
  GenAI assistance, reviewed and adjusted against the assignment's
  compute/deadline constraints before finalizing.
