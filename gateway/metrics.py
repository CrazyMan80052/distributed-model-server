from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

PROMETHEUS_BUCKETS = (0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

GATEWAY_REQUESTS_TOTAL = Counter("gateway_requests_total", "Total HTTP requests", ["status_code", "error_code"])
GATEWAY_REQUEST_DURATION_SECONDS = Histogram("gateway_request_duration_seconds", "HTTP request duration", buckets=PROMETHEUS_BUCKETS)
GATEWAY_ACTIVE_REQUESTS = Gauge("gateway_active_requests", "Current active HTTP requests")
GATEWAY_ROUTING_TOTAL = Counter("gateway_routing_total", "Routing decisions per worker", ["worker_id"])
GATEWAY_RETRIES_TOTAL = Counter("gateway_retries_total", "Total retry attempts", ["result"])
GATEWAY_RPC_FAILURES_TOTAL = Counter("gateway_rpc_failures_total", "gRPC failures per worker", ["worker_id", "grpc_code"])
GATEWAY_WORKER_OUTSTANDING = Gauge("gateway_worker_outstanding", "Outstanding requests per worker", ["worker_id"])
GATEWAY_WORKER_HEALTHY = Gauge("gateway_worker_healthy", "Worker health state", ["worker_id"])
