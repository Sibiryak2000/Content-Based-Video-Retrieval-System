# Phase 5 — Data Pipeline (R2)

## Pre-competition checklist

1. Dataset + `data/processed/metadata.db` present (Phase 2)
2. FAISS index artifacts present (`faiss.index`, `embeddings.npy`, `faiss_id_map.json`)
3. Run full verification: `python scripts/verify_phase5_joint.py`
4. Optional live DRES: `python scripts/verify_phase5_joint.py --live-dres`
5. Set credentials via `.env.example` template (env vars, not git)
6. Optional ffmpeg proxy rebuild: `python scripts/run_phase2_batch.py --rebuild-proxies`
7. Export report metrics: `python scripts/export_report_metrics.py`

## Golden-query benchmark

Shared query set: [`data/eval/golden_queries.yaml`](../data/eval/golden_queries.yaml)

```powershell
python scripts/benchmark_retrieval.py
python scripts/benchmark_retrieval.py --smoke
```

Outputs [`data/eval/benchmark_results.json`](../data/eval/benchmark_results.json) with latency p50/p95 and hit@1/hit@5 for labeled KIS queries.

## Index rebuild

```powershell
python scripts/rebuild_index.py          # skip if index exists
python scripts/rebuild_index.py --force   # full re-encode
```

## Known limitations

- **00016 / 00024:** corrupt segments → placeholder keyframes excluded from FAISS index
- **CPU CLIP latency:** ~3–5 s per semantic query; GUI uses async worker (R4)
- **Keyframe policy:** mid_frame (single JPEG per shot); multi-frame re-index deferred unless benchmark shows poor hit@5

## GenAI usage (Phase 5)

Document scripts reviewed or generated with GenAI for the final course report.
