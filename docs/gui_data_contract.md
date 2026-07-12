# GUI ↔ Pipeline Data Contract

Shared specification between **R2 (Data & Pipeline)**, **R3 (Backend)**, and **R4 (GUI)**.

## Identity rules

| Field | Rule |
|-------|------|
| `video_id` | Filename stem without extension (e.g. `00001` from `00001.mp4`) — **DRES media item name** |
| `shot_id` | `{video_id}_{shot_index:04d}` (e.g. `00001_0003`) |
| DRES collection | `"IVADL"` |
| `fps` | Per-video value from probe — **never hardcoded** |

## ResultItem (GUI / search / DRES)

Aligns with [`ContBVideoRetr/models/result_item.py`](../ContBVideoRetr/models/result_item.py):

```python
@dataclass
class ResultItem:
    video_id: str              # DRES media name (no extension)
    shot_id: str = ""
    title: str = ""
    keyframe_path: str | None  # JPEG thumbnail for grid tile
    proxy_path: str | None     # Full-video proxy for playback
    start_frame: int = 0
    end_frame: int = 0
    fps: float = 25.0          # from videos table — use probed value
    score: float = 0.0
    text: str | None = None    # VQA answer text (optional)
```

**Milliseconds for DRES submit:**

```
start_ms = int(start_frame / fps * 1000)
end_ms   = int(end_frame / fps * 1000)
```

**Playback:** `proxy_path` points to the **full transcoded video**. The player seeks to `start_ms` and stops at `end_ms` (Phase 2 GUI work).

## SQLite schema

Database: `data/processed/metadata.db`

### `videos`

| Column | Type | Description |
|--------|------|-------------|
| video_id | TEXT PK | e.g. `00001` |
| filename | TEXT | e.g. `00001.mp4` |
| fps | REAL | Probed frame rate |
| frame_count | INT | Total frames |
| width, height | INT | Resolution |
| proxy_path | TEXT | Relative to repo root |
| vimeo_description | TEXT | Nullable |

### `shots`

| Column | Type | Description |
|--------|------|-------------|
| shot_id | TEXT PK | e.g. `00001_0003` |
| video_id | TEXT FK | Parent video |
| shot_index | INT | 0-based order in scene file |
| start_frame | INT | TransNet2 boundary |
| end_frame | INT | TransNet2 boundary |
| keyframe_path | TEXT | Relative JPEG path |

### Example query (R3 catalog API)

```sql
SELECT s.shot_id, s.video_id, s.shot_index,
       s.start_frame, s.end_frame, s.keyframe_path,
       v.fps, v.proxy_path
FROM shots s
JOIN videos v ON s.video_id = v.video_id
WHERE s.video_id = '00001'
ORDER BY s.shot_index;
```

## File layout

```
data/processed/
  proxies/{video_id}.mp4           # one proxy per video
  keyframes/{video_id}/{index:04d}.jpg   # one JPEG per shot
  metadata.db
  sample_result_items.json         # Phase 1 GUI handoff examples
```

Paths stored in DB are **relative to repo root** (e.g. `data/processed/proxies/00001.mp4`).

## Phase 1 sample records

See `data/processed/sample_result_items.json` for live examples with absolute paths.

Example (`00001`, shot 0):

```json
{
  "video_id": "00001",
  "shot_id": "00001_0000",
  "keyframe_path": "data/processed/keyframes/00001/0000.jpg",
  "proxy_path": "data/processed/proxies/00001.mp4",
  "start_frame": 0,
  "end_frame": 152,
  "fps": 25.0
}
```

Example with non-25 fps (`00058`):

```json
{
  "video_id": "00058",
  "shot_id": "00058_0000",
  "start_frame": 0,
  "end_frame": 244,
  "fps": 23.976023976023978
}
```

## R4 integration checklist (Phase 2)

- [x] Load `keyframe_path` in `VideoTile` (placeholder fallback when asset missing)
- [x] Catalog client reads `metadata.db` via `SqliteCatalogClient` (`create_catalog_client`)
- [x] Seek player to `start_ms`, stop at `end_ms` on `proxy_path`
- [x] Pass probed `fps` through to DRES submit dialog
- [x] Pagination (`gui.page_size`, default 48) for large shot counts
- [x] Filter by `video_id` prefix; Clear filters resets browse
- [x] Mock fallback when DB absent or empty

## R3 integration checklist

- [ ] Expose `list_shots(video_id)` / text search over index (Phase 3)
- [ ] Resolve relative paths against repo root or config `output.root`
- [ ] Map `video_id` to DRES collection `"IVADL"`
