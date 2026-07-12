# Data Pipeline — Phase 2 Report (R2)

## Summary

Phase 2 generalizes the Phase 1 prototype into a **resumable batch pipeline** that processes all 200 V3C-1 videos into SQLite metadata, per-shot keyframe JPEGs, and full-video playback proxies. The GUI reads the same database via `MetadataStore.list_shots()` / `CatalogClient`.

## Batch runner

Script: [`scripts/run_phase2_batch.py`](../scripts/run_phase2_batch.py)

```powershell
# Full catalog (resume-safe — skips videos already complete in DB)
python scripts/run_phase2_batch.py --skip-existing

# Single video or range
python scripts/run_phase2_batch.py --video-id 00075
python scripts/run_phase2_batch.py --from 00001 --to 00050 --skip-existing

# Export stats only
python scripts/run_phase2_batch.py --stats-only
```

Flags:

| Flag | Purpose |
|------|---------|
| `--skip-existing` | Skip video when DB shot count matches scene file and all keyframe/proxy files exist |
| `--skip-keyframes` | Re-probe / proxy only |
| `--skip-proxies` | Keyframes only |
| `--stats-only` | Write `data/processed/phase2_stats.json` without processing |

Each batch run logs a row to `pipeline_runs` (timestamp, git commit, config hash).

## MetadataStore browse API (R4 / R3)

Added to [`pipeline/db/store.py`](../pipeline/db/store.py):

| Method | Description |
|--------|-------------|
| `list_shots(limit, offset, video_id=None, query="")` | Paginated shots joined with video fps/proxy |
| `count_shots(video_id=None, query="")` | Total for pagination |
| `search_shots_by_video_id_prefix(prefix, limit)` | Browse filter stub |
| `to_result_item(shot)` | Maps `ShotWithVideo` → GUI `ResultItem` dict with absolute paths |
| `resolve_path(path_str, repo_root)` | Relative DB path → absolute filesystem path |
| `count_videos()` | Processed video count |

Query filter (`query` parameter): `video_id` prefix match **or** `vimeo_description` LIKE (when populated).

## Outputs

```
data/processed/
  metadata.db              # videos + shots + pipeline_runs
  proxies/{video_id}.mp4   # one proxy per video (ffmpeg H.264 or copy fallback)
  keyframes/{video_id}/{index:04d}.jpg
  phase2_stats.json        # video/shot counts, missing asset counts
  batch_log.txt            # optional console log from batch run
```

Paths in DB are **relative to repo root** — see [`docs/gui_data_contract.md`](gui_data_contract.md).

## ffmpeg

When `ffmpeg` is on `PATH`, proxies are transcoded to H.264 with `+faststart` at 270 px height (config `prototype.proxy_height`). Without ffmpeg, the pipeline copies the source MP4 (playback still works; seeking may be less reliable in Qt).

Install (Windows): [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html) and add to PATH.

## Resume / idempotency

A video is **complete** when:

1. Shot count in DB equals scene file line count
2. Proxy file exists at `data/processed/proxies/{video_id}.mp4`
3. Every shot has a keyframe JPEG on disk

Re-running with `--skip-existing` is safe for interrupted batches.

## Compatibility verification (M3)

| Video | FPS | Shot 0 frames | Expected ms |
|-------|-----|---------------|-------------|
| `00001` | 25.0 | 0–152 | 0–6080 |
| `00058` | 23.976 | 0–244 | 0–10176 |

Verify with:

```powershell
python scripts/run_phase2_batch.py --stats-only
```

GUI: open a tile → Play → overlay shows frame/ms range; DRES submit dialog uses the same `start_ms` / `end_ms`.

## GUI integration (R4)

- [`ContBVideoRetr/services/catalog_client.py`](../ContBVideoRetr/services/catalog_client.py) — `SqliteCatalogClient` reads `config.yaml` → `metadata.db`; falls back to mock when DB empty/missing
- Pagination: `gui.page_size` (default 48) in [`config.yaml`](../config.yaml)
- Player: seeks `start_ms`, pauses at `end_ms` on full proxy file

Run GUI:

```powershell
cd ContBVideoRetr
python main.py
```

### Joint demo (browse → play → DRES preview)

1. Start GUI — status bar shows `Showing 1–48 of 14345 shots · catalog (metadata.db)`
2. Click any tile → **Play** — player seeks to `start_ms`, pauses at `end_ms`
3. Search `00058` — verify 23.976 fps timing in overlay and DRES submit dialog
4. **Submit to DRES** — confirm dialog shows correct `start_ms` / `end_ms`

Automated: `python scripts/verify_phase2_joint.py`

## Phase 2 batch results

| Metric | Value |
|--------|-------|
| Videos processed | 200 / 200 |
| Total shots | 14,345 |
| Missing keyframes (on disk) | 0 |
| Missing proxies (on disk) | 0 |
| ffmpeg available | No (copy fallback used) |

**Known data issues:** `00016` and `00024` contain corrupt H.264 segments late in the file. OpenCV cannot decode frames in those shot ranges; the pipeline writes gray **placeholder** JPEGs and logs `WARN` lines instead of failing the whole video.

Re-run anytime:

```powershell
python scripts/run_phase2_batch.py --skip-existing
python scripts/verify_phase2_joint.py
```

## Phase 2 definition of done

- [x] Batch script for all 200 videos with resume flags
- [x] `list_shots` / `count_shots` / `to_result_item` in MetadataStore
- [x] GUI catalog client + pagination + shot-range player
- [x] All 200 videos in DB
- [x] `phase2_stats.json` export
- [x] Contract checklist updated in `gui_data_contract.md`

## Deferred to Phase 3

- CLIP/FAISS embedding index and semantic search
- R3 HTTP search API
- Real DRES HTTP client
- VIMEO description ingestion (if metadata files appear)
