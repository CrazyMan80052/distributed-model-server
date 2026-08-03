from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class GatewayConfig:
    model_version: str = os.getenv("MODEL_VERSION", "tinybert-sst2-v1")
    model_sha256: str = os.getenv("MODEL_SHA256", "23ea44ed3eb302e22045900ba8565dd672a9f4c127f5514ce182f01d83fe2e3a")
    http_max_body_bytes: int = int(os.getenv("HTTP_MAX_BODY_BYTES", "65536"))
    max_inputs_per_request: int = int(os.getenv("MAX_INPUTS_PER_REQUEST", "8"))
    max_input_bytes: int = int(os.getenv("MAX_INPUT_BYTES", "4096"))
    max_total_input_bytes: int = int(os.getenv("MAX_TOTAL_INPUT_BYTES", "32768"))
    min_timeout_ms: int = int(os.getenv("MIN_TIMEOUT_MS", "100"))
    max_timeout_ms: int = int(os.getenv("MAX_TIMEOUT_MS", "10000"))
    default_timeout_ms: int = int(os.getenv("DEFAULT_TIMEOUT_MS", "1000"))
    gateway_max_outstanding_per_worker: int = int(os.getenv("GATEWAY_MAX_OUTSTANDING_PER_WORKER", "32"))
    health_interval_ms: int = int(os.getenv("HEALTH_INTERVAL_MS", "1000"))
    health_timeout_ms: int = int(os.getenv("HEALTH_TIMEOUT_MS", "250"))
    health_failure_threshold: int = int(os.getenv("HEALTH_FAILURE_THRESHOLD", "3"))
    health_recovery_threshold: int = int(os.getenv("HEALTH_RECOVERY_THRESHOLD", "2"))
    min_retry_budget_ms: int = int(os.getenv("MIN_RETRY_BUDGET_MS", "50"))
    workers_raw: str = os.getenv(
        "WORKERS",
        "worker-1=worker-1:50051,worker-2=worker-2:50051,worker-3=worker-3:50051,worker-4=worker-4:50051",
    )
    workers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.workers and self.workers_raw:
            parsed = {}
            for item in self.workers_raw.split(","):
                item = item.strip()
                if not item:
                    continue
                if "=" in item:
                    wid, addr = item.split("=", 1)
                    parsed[wid.strip()] = addr.strip()
                else:
                    parsed[item] = item
            self.workers = parsed
