#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys


def percentile(data: list[float], pct: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(math.ceil(pct * len(sorted_data))) - 1
    idx = max(0, min(idx, len(sorted_data) - 1))
    return sorted_data[idx]


def summarize_trial(ndjson_path: str, resource_csv: str | None = None) -> dict:
    records = []
    if os.path.exists(ndjson_path):
        with open(ndjson_path, "r") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))

    if not records:
        return {"error": "No records found"}

    total_requests = len(records)
    successful_records = [r for r in records if r["http_status"] == 200]
    success_count = len(successful_records)

    min_start_ns = min(r["started_ns"] for r in records)
    max_start_ns = max(r["started_ns"] for r in records)
    total_sec = max(0.001, (max_start_ns - min_start_ns) / 1e9)

    attempted_throughput = total_requests / total_sec
    successful_throughput = success_count / total_sec

    successful_latencies = [r["duration_ms"] for r in successful_records]
    p50_lat = percentile(successful_latencies, 0.50)
    p95_lat = percentile(successful_latencies, 0.95)
    p99_lat = percentile(successful_latencies, 0.99)

    status_counts: dict[str, int] = {}
    for r in records:
        st = str(r["http_status"])
        status_counts[st] = status_counts.get(st, 0) + 1

    worker_counts: dict[str, int] = {}
    for r in successful_records:
        wid = r.get("worker_id") or "unknown"
        worker_counts[wid] = worker_counts.get(wid, 0) + 1

    retries_count = sum(1 for r in records if r.get("attempts", 1) > 1)

    queue_times = [r["queue_ms"] for r in successful_records]
    inference_times = [r["inference_ms"] for r in successful_records]

    avg_cpu = 0.0
    peak_mem_mb = 0.0
    if resource_csv and os.path.exists(resource_csv):
        cpus, mems = [], []
        with open(resource_csv, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cpus.append(float(row.get("cpu_percent", 0)))
                mems.append(float(row.get("memory_bytes", 0)))
        if cpus:
            avg_cpu = sum(cpus) / len(cpus)
        if mems:
            peak_mem_mb = max(mems) / (1024 * 1024)

    return {
        "total_requests": total_requests,
        "success_count": success_count,
        "duration_sec": round(total_sec, 2),
        "attempted_throughput": round(attempted_throughput, 2),
        "successful_throughput": round(successful_throughput, 2),
        "p50_latency_ms": round(p50_lat, 2),
        "p95_latency_ms": round(p95_lat, 2),
        "p99_latency_ms": round(p99_lat, 2),
        "status_counts": status_counts,
        "worker_counts": worker_counts,
        "retries_count": retries_count,
        "p50_queue_ms": round(percentile(queue_times, 0.50), 2),
        "p95_queue_ms": round(percentile(queue_times, 0.95), 2),
        "p50_inference_ms": round(percentile(inference_times, 0.50), 2),
        "p95_inference_ms": round(percentile(inference_times, 0.95), 2),
        "avg_cpu_percent": round(avg_cpu, 2),
        "peak_mem_mb": round(peak_mem_mb, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize benchmark trial results.")
    parser.add_argument("--ndjson", required=True, help="Input NDJSON trial file.")
    parser.add_argument("--resource-csv", help="Resource sampling CSV file.")
    parser.add_argument("--output", help="Output summary markdown path.")
    args = parser.parse_args()

    summary = summarize_trial(args.ndjson, args.resource_csv)
    print(json.dumps(summary, indent=2))

    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            f.write(f"# Benchmark Trial Summary\n\n")
            f.write(f"- **Attempted Throughput**: {summary['attempted_throughput']} req/s\n")
            f.write(f"- **Successful Throughput**: {summary['successful_throughput']} req/s\n")
            f.write(f"- **Latency (p50/p95/p99)**: {summary['p50_latency_ms']} ms / {summary['p95_latency_ms']} ms / {summary['p99_latency_ms']} ms\n")
            f.write(f"- **HTTP Statuses**: {summary['status_counts']}\n")
            f.write(f"- **Worker Distribution**: {summary['worker_counts']}\n")
            f.write(f"- **Retries**: {summary['retries_count']}\n")
            f.write(f"- **Queue Time (p50/p95)**: {summary['p50_queue_ms']} ms / {summary['p95_queue_ms']} ms\n")
            f.write(f"- **Inference Time (p50/p95)**: {summary['p50_inference_ms']} ms / {summary['p95_inference_ms']} ms\n")
            f.write(f"- **Avg CPU**: {summary['avg_cpu_percent']}%\n")
            f.write(f"- **Peak Memory**: {summary['peak_mem_mb']} MB\n")
        print(f"Written summary report to {args.output}")


if __name__ == "__main__":
    main()
