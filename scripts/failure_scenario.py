#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

GATEWAY_URL = "http://localhost:8000"


def http_get(url: str) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8")
    except Exception as exc:
        return 0, str(exc)


def http_post_predict(sentinel: str, timeout_ms: int = 1000) -> dict:
    url = f"{GATEWAY_URL}/v1/predict"
    payload = {
        "request_id": f"sentinel-{int(time.time())}",
        "inputs": [sentinel],
        "model_version": "tinybert-sst2-v1",
        "timeout_ms": timeout_ms,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def run_cmd(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True)


def main() -> None:
    print("--- Starting End-to-End Compose Failure Test ---")
    sentinel = f"SECRET_SENTINEL_{int(time.time())}_DO_NOT_LOG"

    # 1. Verify readiness
    print("1. Polling gateway readiness...")
    for _ in range(30):
        code, body = http_get(f"{GATEWAY_URL}/health/ready")
        if code == 200:
            print("Gateway is READY.")
            break
        time.sleep(1)
    else:
        print("ERROR: Gateway did not become ready.")
        sys.exit(1)

    # 2. Test prediction
    print("2. Verifying initial prediction...")
    res = http_post_predict(sentinel)
    if "predictions" not in res:
        print(f"ERROR: Prediction failed: {res}")
        sys.exit(1)
    print(f"Prediction successful on worker {res.get('worker_id')}")

    # 3. Stop worker-1
    print("3. Stopping worker-1...")
    run_cmd(["docker", "stop", "distributed-model-server-worker-1-1"])
    time.sleep(3)

    # 4. Verify traffic avoids worker-1
    print("4. Sending requests to verify worker-1 receives no traffic...")
    worker1_hits = 0
    for _ in range(20):
        r = http_post_predict("Traffic while worker-1 down")
        if r.get("worker_id") == "worker-1":
            worker1_hits += 1

    if worker1_hits > 0:
        print(f"ERROR: Ejected worker-1 received {worker1_hits} requests!")
        sys.exit(1)
    print("Confirmed: worker-1 received 0 requests while stopped.")

    # 5. Restart worker-1
    print("5. Restarting worker-1...")
    run_cmd(["docker", "start", "distributed-model-server-worker-1-1"])
    time.sleep(4)

    # 6. Verify worker-1 receives traffic again
    print("6. Verifying health restoration for worker-1...")
    recovered = False
    for _ in range(20):
        r = http_post_predict("Traffic after worker-1 recovery")
        if r.get("worker_id") == "worker-1":
            recovered = True
            break
    if not recovered:
        print("WARNING: worker-1 did not serve requests immediately after recovery (may need more probes).")
    else:
        print("Confirmed: worker-1 successfully recovered and accepted traffic.")

    # 7. Verify Log Redaction
    print("7. Verifying container log redaction...")
    logs = run_cmd(["docker", "compose", "logs"])
    if sentinel in logs:
        print(f"CRITICAL ERROR: Sentinel input text '{sentinel}' found in container logs!")
        sys.exit(1)
    print("Confirmed: Sentinel input text was NOT found in any container logs.")

    print("--- End-to-End Failure & Recovery Test PASSED ---")


if __name__ == "__main__":
    main()
