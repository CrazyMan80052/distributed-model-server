from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class WorkerConfig:
    worker_id: str = os.getenv("WORKER_ID", "worker-1")
    model_version: str = os.getenv("MODEL_VERSION", "tinybert-sst2-v1")
    model_sha256: str = os.getenv("MODEL_SHA256", "23ea44ed3eb302e22045900ba8565dd672a9f4c127f5514ce182f01d83fe2e3a")
    model_dir: str = os.getenv("MODEL_DIR", "artifacts/model")
    grpc_port: int = int(os.getenv("WORKER_GRPC_PORT", "50051"))
    metrics_port: int = int(os.getenv("WORKER_METRICS_PORT", "9100"))
    queue_capacity: int = int(os.getenv("WORKER_QUEUE_CAPACITY", "64"))
    max_batch_requests: int = int(os.getenv("MAX_BATCH_REQUESTS", "8"))
    max_batch_items: int = int(os.getenv("MAX_BATCH_ITEMS", "32"))
    max_batch_delay_ms: int = int(os.getenv("MAX_BATCH_DELAY_MS", "5"))
    max_tokens_per_input: int = int(os.getenv("MAX_TOKENS_PER_INPUT", "128"))
    ort_intra_op_threads: int = int(os.getenv("ORT_INTRA_OP_THREADS", "1"))
    ort_inter_op_threads: int = int(os.getenv("ORT_INTER_OP_THREADS", "1"))
