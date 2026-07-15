"""Benchmark semantic retrieval against golden queries."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ContBVideoRetr"))

from services.faiss_search import faiss_index_available  # noqa: E402
from services.search_api import create_search_service  # noqa: E402

GOLDEN = REPO / "data" / "eval" / "golden_queries.yaml"
OUT = REPO / "data" / "eval" / "benchmark_results.json"


def load_queries(path: Path, smoke: bool = False) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    queries = data if isinstance(data, list) else data.get("queries", [])
    kis = [q for q in queries if q.get("type") == "KIS"]
    if smoke:
        return kis[:3]
    return queries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="Run 3 KIS queries only")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    if not faiss_index_available():
        print("FAIL: FAISS index not available")
        return 1

    if not GOLDEN.is_file():
        print(f"FAIL: missing {GOLDEN}")
        return 1

    queries = load_queries(GOLDEN, smoke=args.smoke)
    svc = create_search_service()
    latencies: list[float] = []
    results: list[dict] = []
    hit1 = hit5 = labeled = 0

    for entry in queries:
        if entry.get("type") != "KIS":
            continue
        q = entry["query"]
        resp = svc.text_query(q, limit=args.top_k, offset=0)
        latencies.append(resp.latency_ms)
        top_vids = [it.video_id for it in resp.items]
        expected = entry.get("expected_video_ids") or []
        row = {
            "id": entry.get("id"),
            "query": q,
            "latency_ms": resp.latency_ms,
            "top_shot_ids": [it.shot_id for it in resp.items[:5]],
            "top_video_ids": top_vids[:5],
        }
        if expected:
            labeled += 1
            if top_vids and top_vids[0] in expected:
                hit1 += 1
                row["hit_at_1"] = True
            if any(v in expected for v in top_vids[:5]):
                hit5 += 1
                row["hit_at_5"] = True
        results.append(row)
        print(f"  {entry.get('id')}: {resp.latency_ms:.0f}ms top={top_vids[:3]}")

    summary = {
        "query_count": len(results),
        "latency_ms_p50": statistics.median(latencies) if latencies else 0,
        "latency_ms_p95": (
            sorted(latencies)[int(len(latencies) * 0.95) - 1] if len(latencies) >= 2 else (latencies[0] if latencies else 0)
        ),
        "hit_at_1": hit1,
        "hit_at_5": hit5,
        "labeled_kis": labeled,
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nOK benchmark: p50={summary['latency_ms_p50']:.0f}ms labeled={labeled} hit@1={hit1} hit@5={hit5}")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
