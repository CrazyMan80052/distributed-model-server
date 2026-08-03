#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

import httpx


def load_corpus(path: str = "benchmarks/corpus.jsonl") -> list[str]:
    texts = []
    if os.path.exists(path):
        with open(path, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    texts.append(data["text"])
    if not texts:
        texts = ["Default benchmark sentence for classification."]
    return texts


async def worker_loop(
    client: httpx.AsyncClient,
    url: str,
    texts: list[str],
    end_time: float,
    trial_id: str,
    results: list[dict],
    counter_lock: asyncio.Lock,
    global_counter: list[int],
) -> None:
    idx = 0
    n = len(texts)

    while time.time() < end_time:
        text = texts[idx % n]
        idx += 1

        async with counter_lock:
            req_idx = global_counter[0]
            global_counter[0] += 1

        payload = {
            "request_id": f"bm-{trial_id}-{req_idx}",
            "inputs": [text],
            "model_version": "tinybert-sst2-v1",
            "timeout_ms": 5000,
        }

        t0_ns = time.time_ns()
        t0 = time.perf_counter()
        status_code = 500
        error_code = None
        worker_id = None
        attempts = 1
        queue_ms = 0.0
        inference_ms = 0.0

        try:
            resp = await client.post(url, json=payload)
            status_code = resp.status_code
            if status_code == 200:
                body = resp.json()
                worker_id = body.get("worker_id")
                attempts = body.get("attempts", 1)
                timing = body.get("timing_ms", {})
                queue_ms = timing.get("queue", 0.0)
                inference_ms = timing.get("inference", 0.0)
            else:
                try:
                    err_json = resp.json()
                    error_code = err_json.get("error", {}).get("code")
                except Exception:
                    error_code = f"HTTP_{status_code}"
        except Exception as exc:
            status_code = 0
            error_code = type(exc).__name__

        t1 = time.perf_counter()
        dur_ms = round((t1 - t0) * 1000.0, 2)

        results.append(
            {
                "trial_id": trial_id,
                "request_index": req_idx,
                "started_ns": t0_ns,
                "duration_ms": dur_ms,
                "http_status": status_code,
                "error_code": error_code,
                "worker_id": worker_id,
                "attempts": attempts,
                "input_count": 1,
                "queue_ms": queue_ms,
                "inference_ms": inference_ms,
            }
        )


async def run_benchmark(args: argparse.Namespace) -> None:
    texts = load_corpus(args.corpus)
    url = f"{args.url.rstrip('/')}/v1/predict"

    limits = httpx.Limits(max_keepalive_connections=args.concurrency, max_connections=args.concurrency)
    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        # Warmup phase
        if args.warmup > 0:
            print(f"Warming up for {args.warmup} seconds...")
            warmup_end = time.time() + args.warmup
            warmup_results: list[dict] = []
            c_lock = asyncio.Lock()
            g_counter = [0]
            tasks = [
                asyncio.create_task(
                    worker_loop(client, url, texts, warmup_end, "warmup", warmup_results, c_lock, g_counter)
                )
                for _ in range(args.concurrency)
            ]
            await asyncio.gather(*tasks)

        # Measured trial phase
        print(f"Running trial {args.trial_id} for {args.duration} seconds with concurrency {args.concurrency}...")
        measured_results: list[dict] = []
        c_lock = asyncio.Lock()
        g_counter = [0]
        end_time = time.time() + args.duration
        tasks = [
            asyncio.create_task(
                worker_loop(client, url, texts, end_time, args.trial_id, measured_results, c_lock, g_counter)
            )
            for _ in range(args.concurrency)
        ]
        await asyncio.gather(*tasks)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        for item in measured_results:
            f.write(json.dumps(item) + "\n")

    print(f"Saved {len(measured_results)} request records to {args.output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run closed-loop benchmark against model gateway.")
    parser.add_argument("--url", default="http://localhost:8000", help="Gateway URL.")
    parser.add_argument("--corpus", default="benchmarks/corpus.jsonl", help="Corpus JSONL file.")
    parser.add_argument("--concurrency", type=int, default=32, help="Client concurrency.")
    parser.add_argument("--warmup", type=int, default=5, help="Warmup duration in seconds.")
    parser.add_argument("--duration", type=int, default=15, help="Measured trial duration in seconds.")
    parser.add_argument("--trial-id", default="trial-1", help="Trial identifier.")
    parser.add_argument("--output", required=True, help="Output NDJSON path.")

    args = parser.parse_args()
    asyncio.run(run_benchmark(args))


if __name__ == "__main__":
    main()
