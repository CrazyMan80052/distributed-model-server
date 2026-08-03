#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time


def parse_bytes(val_str: str) -> int:
    val_str = val_str.strip().upper()
    multipliers = {"KIB": 1024, "MIB": 1024**2, "GIB": 1024**3, "KB": 1000, "MB": 1000**2, "GB": 1000**3, "B": 1}
    for unit, mult in multipliers.items():
        if val_str.endswith(unit):
            num = float(val_str.replace(unit, "").strip())
            return int(num * mult)
    try:
        return int(float(val_str))
    except Exception:
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample Docker container resource stats.")
    parser.add_argument("--output", required=True, help="Path to output CSV file.")
    parser.add_argument("--duration", type=int, default=60, help="Sampling duration in seconds.")
    parser.add_argument("--interval", type=float, default=1.0, help="Sampling interval in seconds.")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "container", "cpu_percent", "memory_bytes", "memory_limit_bytes"])

        start_time = time.time()
        while time.time() - start_time < args.duration:
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            try:
                out = subprocess.check_output(
                    ["docker", "stats", "--no-stream", "--format", "{{.Name}},{{.CPUPerc}},{{.MemUsage}}"],
                    text=True,
                )
                for line in out.strip().splitlines():
                    if not line:
                        continue
                    parts = line.split(",")
                    if len(parts) >= 3:
                        name = parts[0].strip()
                        cpu_str = parts[1].replace("%", "").strip()
                        mem_usage_str = parts[2].strip()

                        cpu_pct = float(cpu_str) if cpu_str else 0.0
                        if "/" in mem_usage_str:
                            used_str, limit_str = mem_usage_str.split("/", 1)
                            mem_bytes = parse_bytes(used_str)
                            limit_bytes = parse_bytes(limit_str)
                        else:
                            mem_bytes = parse_bytes(mem_usage_str)
                            limit_bytes = 0

                        writer.writerow([ts, name, cpu_pct, mem_bytes, limit_bytes])
                f.flush()
            except Exception:
                pass
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
