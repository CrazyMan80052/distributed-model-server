from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, start_http_server

PROMETHEUS_BUCKETS = (0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

WORKER_REQUESTS_TOTAL = Counter("worker_requests_total", "Total requests processed", ["result"])
WORKER_QUEUE_DEPTH = Gauge("worker_queue_depth", "Current worker queue depth")
WORKER_QUEUE_WAIT_SECONDS = Histogram("worker_queue_wait_seconds", "Time spent in queue", buckets=PROMETHEUS_BUCKETS)
WORKER_BATCH_REQUESTS = Histogram("worker_batch_requests", "Requests per batch", buckets=(1, 2, 4, 8, 16, 32))
WORKER_BATCH_ITEMS = Histogram("worker_batch_items", "Inputs per batch", buckets=(1, 2, 4, 8, 16, 32, 64))
WORKER_PREPROCESS_SECONDS = Histogram("worker_preprocess_seconds", "Preprocess duration", buckets=PROMETHEUS_BUCKETS)
WORKER_INFERENCE_SECONDS = Histogram("worker_inference_seconds", "Inference duration", buckets=PROMETHEUS_BUCKETS)
WORKER_ACTIVE_BATCHES = Gauge("worker_active_batches", "Active inference batches")
WORKER_EXPIRED_REQUESTS_TOTAL = Counter("worker_expired_requests_total", "Expired requests", ["stage"])
WORKER_LATE_RESULTS_TOTAL = Counter("worker_late_results_total", "Late results after deadline")
WORKER_MODEL_INFO = Gauge("worker_model_info", "Worker model info", ["worker_id", "model_version", "model_sha256"])


def start_worker_metrics_server(port: int) -> None:
    try:
        start_http_server(port)
    except Exception:
        pass
