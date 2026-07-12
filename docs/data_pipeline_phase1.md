# Data Pipeline — Phase 1 Report (R2)

## Summary

Phase 1 established the offline pipeline scaffolding, validated the local V3C-1 subset, parsed TransNet2 shot boundaries from zip, prototyped keyframe extraction and proxy generation on three sample videos, and populated a SQLite metadata database.

## Dataset inventory

| Metric | Value |
|--------|-------|
| Videos in `dataset/` | 200 |
| Scene files in `scenes_v3c1_204.zip` | 200 |
| ID alignment | 100% match |
| Validation errors | 0 |
| Missing numeric IDs (gaps) | `00050`, `00119`, `00153`, `00167` |

**Notes:**

- Assignment references `scenes_v3c1_200.zip`; local archive is named `scenes_v3c1_204.zip`.
- No VIMEO metadata files found in `dataset/` — defer ingestion to Phase 2.
- **FPS varies across videos** — do not hardcode 25.0. Observed values include 15, ~23, 23.976, 24, 25, 29.97, 30, and 50 fps. Per-video fps must be stored and used for DRES millisecond conversion.

Full machine-readable report: `data/processed/inventory_report.json`

## Scene file format

Path inside zip: `scenes_v3c1_204/{video_id}.mp4.scenes.txt`

Each line: `start_frame end_frame` (0-based, inclusive).

Example `00001`: 44 shots, frames 0–6823, 25 fps, 480×270.

Scenes are read **directly from the zip** via `pipeline/scenes.py` (no full extraction required).

## Technology choices

| Layer | Choice | Phase |
|-------|--------|-------|
| Relational metadata | **SQLite** (`data/processed/metadata.db`) | Phase 1 (sample), Phase 2 (full) |
| Vector search | **FAISS** | Phase 2/3 (after R1 embeddings) |
| Video probe | OpenCV `VideoCapture` | Phase 1 |
| Keyframes | OpenCV mid-frame JPEG per shot | Phase 1 prototype |
| Proxies | ffmpeg H.264/AAC with `+faststart` | Phase 1 (fallback: file copy if ffmpeg missing) |

## Phase 1 prototype outputs

Sample videos processed: `00001`, `00058`, `00122`

| Video | Shots | FPS | Keyframes | Proxy |
|-------|-------|-----|-----------|-------|
| 00001 | 44 | 25.0 | `data/processed/keyframes/00001/` | `data/processed/proxies/00001.mp4` |
| 00058 | 92 | 23.976 | `data/processed/keyframes/00058/` | `data/processed/proxies/00058.mp4` |
| 00122 | 123 | 25.0 | `data/processed/keyframes/00122/` | `data/processed/proxies/00122.mp4` |

SQLite: 3 videos, 259 shots, 1 pipeline run logged.

GUI handoff export: `data/processed/sample_result_items.json`

## How to run

```powershell
pip install -r requirements-pipeline.txt
python scripts/run_phase1_prototype.py --config config.yaml
```

Re-run sample processing only (skip 200-video inventory):

```powershell
python scripts/run_phase1_prototype.py --skip-inventory
```

Install **ffmpeg** on PATH for proper proxy re-encoding (currently falls back to copying source MP4).

## Repository layout

```
pipeline/
  config.py          Load config.yaml paths
  inventory.py       Dataset validation
  scenes.py          TransNet2 zip parser
  probe.py           fps / frame_count / resolution
  keyframes.py       JPEG extraction per shot
  transcode.py       ffmpeg proxy generation
  db/
    schema.sql       SQLite DDL
    models.py        Dataclasses
    store.py         CRUD + ResultItem export
scripts/
  run_phase1_prototype.py
data/processed/      Generated outputs (gitignored)
config.yaml
```

## Phase 2 next steps

1. Batch-process all 200 videos (keyframes + proxies + DB insert).
2. Ingest VIMEO metadata when available.
3. Hand off stable catalog API to R3/R4.
4. Build FAISS index once R1 produces embeddings.

## GenAI usage (Phase 1)

Document which scripts/modules were generated or reviewed with GenAI tools for the final report.
