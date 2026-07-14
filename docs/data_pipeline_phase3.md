# Data Pipeline — Phase 3 Report (R2 + R4)

## Summary

Phase 3 adds **CLIP ViT-B/32 embeddings** and a **FAISS IndexFlatIP** over all valid shot keyframes, enabling natural-language KIS search and similarity retrieval in the GUI via `SearchService`.

## Artifacts

```
data/processed/
  embeddings.npy              # float32 [N, 512], L2-normalized
  faiss_id_map.json           # {"shot_ids": ["00001_0000", ...]}
  faiss.index                 # FAISS inner-product index (cosine on normalized vectors)
  embedding_manifest.json     # model, dim, excluded shots, build timestamps
```

Paths configured in [`config.yaml`](../config.yaml) under `output.*` and `embedding.*`.

## Build commands

```powershell
# Full pipeline: embeddings + FAISS index
python scripts/run_phase3_index.py --force

# Subset (mini-batch / resume testing)
python scripts/run_phase3_index.py --from 00001 --to 00010 --force

# Embeddings only or index only
python scripts/run_phase3_index.py --embeddings-only
python scripts/run_phase3_index.py --index-only

# Validation
python scripts/verify_phase3_index.py
python scripts/verify_phase3_search.py
python scripts/verify_phase2_joint.py   # playback / timing regression
```

Re-run without `--force` skips embedding rebuild when manifest + id map are unchanged.

## Model & index design

| Setting | Value |
|---------|-------|
| Model | CLIP ViT-B/32 (`openai/clip-vit-base-patch32`) |
| Dim | 512 |
| Metric | Cosine (L2-normalized vectors + IndexFlatIP) |
| Keyframe input | R2 mid-frame JPEG via [`pipeline/preprocessing.py`](../pipeline/preprocessing.py) |

## Data hygiene

Shots excluded from the index when:

- Keyframe file missing or unreadable
- Gray **placeholder** JPEG (corrupt segments on `00016`, `00024`) — detected by [`is_placeholder_keyframe()`](../pipeline/preprocessing.py)

Excluded `shot_id`s are listed in `embedding_manifest.json`.

## GUI integration (R4)

- [`ContBVideoRetr/MainWindow.py`](../ContBVideoRetr/MainWindow.py) uses `create_search_service()` for all results
- Empty search → browse catalog; text query → CLIP + FAISS semantic ranking
- Tile menu **More like this** → `similarity_query(shot_id)`
- Scores shown on tiles when `ResultItem.score > 0`
- Falls back to prefix browse when FAISS index absent

```powershell
cd ContBVideoRetr
python main.py
```

### Joint demo

1. Run index build (above)
2. Launch GUI — status shows `semantic search (FAISS + CLIP)` when index present
3. Search `person walking` — ranked tiles with scores
4. Right-click tile → **More like this**
5. Play shot → verify ms overlay; DRES submit preview (mock, Phase 4 = real HTTP)

## Phase 3 batch results

| Metric | Value |
|--------|-------|
| Indexed vectors | 13,808 |
| Excluded shots | 537 (placeholders + unreadable) |
| Model | CLIP ViT-B/32 |
| Index type | FAISS IndexFlatIP |

## Phase 3 definition of done

- [x] CLIP embeddings for all valid keyframes
- [x] FAISS index + id map on disk
- [x] `FaissSearchService` text + similarity queries
- [x] GUI wired through `SearchService`
- [x] Scores + similarity menu
- [x] Verification scripts
- [x] Contract checklist updated

## Deferred to Phase 4

- Real DRES HTTP via `create_dres_client()`
- VQA answer text generation (`ResultItem.text`)
- VIMEO metadata ingestion
