# GUI Eval Runbook (R4 — Phase 5)

## Before the live VBS window

1. Run `python scripts/verify_phase5_joint.py`
2. Set `DRES_USERNAME` / `DRES_PASSWORD` (see [`.env.example`](../.env.example))
3. Start GUI: `cd ContBVideoRetr && python main.py`
4. Confirm status bar: index vector count + `DRES: connected` (or mock if rehearsing offline)

## Live eval workflow

1. **Reconnect DRES** if status is not connected
2. Select **Evaluation** from dropdown (live) or use default `IVADL2026`
3. Enter official **DRES task name** when the task opens
4. Choose **KIS** or **VQA** task type
5. Run search (or pick a **Rehearsal** golden query)
6. **Play** shot — verify ms range in player overlay matches DRES dialog
7. For **VQA**: fill **VQA answer** field before submit
8. **Submit to DRES** — confirm dialog shows correct `start_ms` / `end_ms` (check `00058` → 10176 ms end)
9. Use **Copy ms range** in dialog if needed for notes

## Keyboard shortcuts (player)

| Key | Action |
|-----|--------|
| Space | Pause / play |
| S | Submit to DRES |
| L | Loop shot range |
| N | Next result in grid |
| Esc | Close player |

## KIS vs VQA

| Type | VQA answer field | DRES `text` field |
|------|------------------|-------------------|
| KIS | Leave empty | null |
| VQA | Required | submitted text |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `DRES: mock (no credentials)` | Set env vars; click Reconnect DRES |
| `DRES: mock (server unreachable)` | Check network / VPN; verify SSL setting in config |
| Semantic search banner | Run `python scripts/rebuild_index.py` |
| UI frozen during search | Should not happen — async worker; restart GUI |
| Wrong task name error | Use exact task id from eval server |

## Rehearsal

Use **Rehearsal** dropdown (loads `golden_queries.yaml`) to practice KIS/VQA flows before live tasks.
