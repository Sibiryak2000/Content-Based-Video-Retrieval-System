# Data Pipeline — Phase 4 Report (R2 + R4)

## Summary

Phase 4 completes **live DRES HTTP integration** in the GUI and hardens the pipeline for evaluation: payload timing verification, optional ffmpeg proxy rebuild, optional VIMEO metadata ingest, and a joint pre-eval checklist script.

## DRES credentials

Configure in [`config.yaml`](../config.yaml) or via environment variables (env wins when set):

| Setting | Env var | Default |
|---------|---------|---------|
| Username | `DRES_USERNAME` | empty |
| Password | `DRES_PASSWORD` | empty |
| Evaluation ID | `DRES_EVALUATION_ID` | `IVADL2026` |
| Base URL | — | `https://vbs.videobrowsing.org` |

**Never commit real passwords.** Keep `config.yaml` credentials empty in git; use env vars on eval machines.

```powershell
$env:DRES_USERNAME = "team_user"
$env:DRES_PASSWORD = "secret"
python ContBVideoRetr/main.py
```

## DRES payload contract (frozen)

Built by [`DresSubmitPayload.from_result()`](../ContBVideoRetr/services/dres_client.py):

| Field | Source |
|-------|--------|
| `mediaItemName` | `video_id` (no extension) |
| `mediaCollectionName` | `"IVADL"` |
| `start` / `end` | `ResultItem.start_ms` / `end_ms` from probed fps |
| `text` | Optional VQA answer |

Verify timing without network:

```powershell
python scripts/verify_dres_payload.py
```

Expected shot 0 values:

| Video | FPS | Expected ms |
|-------|-----|-------------|
| `00001` | 25.0 | 0–6080 |
| `00058` | 23.976 | 0–10176 |

## GUI DRES wiring (R4)

[`ContBVideoRetr/MainWindow.py`](../ContBVideoRetr/MainWindow.py):

- Uses `create_dres_client()` — no direct HTTP in GUI code
- Status bar: `DRES: connected` or `DRES: mock (no credentials)` / `mock (server unreachable)`
- **Reconnect DRES** button re-runs factory
- Submit dialog shows `evaluation_id`, ms range, fps, optional VQA text
- Submit uses `settings.evaluation_id` from config/env

Run GUI:

```powershell
cd ContBVideoRetr
python main.py
```

## ffmpeg proxy rebuild

Initial Phase 2 batch used **copy fallback** when ffmpeg was absent. For smoother Qt seeking during live eval, re-transcode proxies when ffmpeg is installed:

```powershell
python scripts/run_phase2_batch.py --rebuild-proxies
```

Requires ffmpeg on `PATH`. Skips keyframes; forces ffmpeg transcode for all videos.

Install: [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)

## VIMEO metadata (optional)

Column `videos.vimeo_description` exists but is NULL unless metadata files appear in `dataset/`.

If a file matching `*vimeo*.json` or `*vimeo*.csv` is present:

```powershell
python scripts/ingest_vimeo_metadata.py
```

**Current status:** No VIMEO metadata file in `dataset/` — N/A, not a blocker.

## Verification scripts

| Script | Purpose |
|--------|---------|
| `verify_dres_payload.py` | DRES ms timing gate (00001, 00058) |
| `verify_phase2_joint.py` | Catalog browse + timing matrix |
| `verify_phase3_index.py` | FAISS artifact integrity |
| `verify_phase3_search.py` | Semantic + similarity queries |
| `verify_phase4_joint.py` | Orchestrates all Phase 2/3/4 checks |

Full pre-eval checklist:

```powershell
python scripts/verify_phase4_joint.py
```

Optional live DRES login test (requires credentials):

```powershell
python scripts/verify_phase4_joint.py --live-dres
```

## Known data issues

- **`00016` / `00024`:** Corrupt H.264 segments → gray placeholder keyframes; shots excluded from FAISS index
- **Proxies:** Copy fallback unless `--rebuild-proxies` with ffmpeg installed

## Joint demo (Phase 4)

1. `python scripts/verify_phase4_joint.py` — all checks pass
2. Start GUI — DRES status shows connected (with creds) or mock
3. Semantic search → play shot → confirm ms in overlay
4. Submit to DRES — confirm dialog shows correct timing for `00058` (10176 ms end, not 25-fps value)
5. One real submit during evaluation window (team credentials)

## Phase 4 definition of done

- [x] `verify_dres_payload.py` passes on timing matrix
- [x] `verify_phase4_joint.py` orchestrates Phase 2/3/4 checks
- [x] ffmpeg proxy rebuild flag documented
- [x] VIMEO ingested or documented as N/A
- [x] Phase 4 doc complete
- [x] GUI uses `create_dres_client()` with status UX
- [x] Mock fallback when credentials unavailable
