from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from gateway.config import GatewayConfig
from gateway.metrics import GATEWAY_ROUTING_TOTAL, GATEWAY_WORKER_OUTSTANDING
from gateway.registry import HealthState, WorkerNode, WorkerRegistry
from shared.errors import GatewayAtCapacityError, NoHealthyWorkerError


class Scheduler:
    def __init__(self, registry: WorkerRegistry, config: GatewayConfig) -> None:
        self.registry = registry
        self.config = config
        self._lock = asyncio.Lock()
        self._cursor = 0

    async def select_worker(self, exclude_ids: set[str] | None = None) -> WorkerNode:
        if exclude_ids is None:
            exclude_ids = set()

        async with self._lock:
            healthy_workers = [
                w for w in self.registry.workers.values()
                if w.state == HealthState.HEALTHY
            ]

            if not healthy_workers:
                raise NoHealthyWorkerError()

            eligible = [
                w for w in healthy_workers
                if w.worker_id not in exclude_ids
                and w.outstanding_requests < self.config.gateway_max_outstanding_per_worker
            ]

            if not eligible:
                raise GatewayAtCapacityError()

            min_outstanding = min(w.outstanding_requests for w in eligible)
            candidates = [w for w in eligible if w.outstanding_requests == min_outstanding]
            candidates.sort(key=lambda w: w.worker_id)

            selected = candidates[self._cursor % len(candidates)]
            self._cursor = (self._cursor + 1) % len(candidates)

            selected.outstanding_requests += 1
            GATEWAY_WORKER_OUTSTANDING.labels(worker_id=selected.worker_id).set(selected.outstanding_requests)
            GATEWAY_ROUTING_TOTAL.labels(worker_id=selected.worker_id).inc()

            return selected

    async def release_worker(self, worker_id: str) -> None:
        async with self._lock:
            worker = self.registry.workers.get(worker_id)
            if worker and worker.outstanding_requests > 0:
                worker.outstanding_requests -= 1
                GATEWAY_WORKER_OUTSTANDING.labels(worker_id=worker.worker_id).set(worker.outstanding_requests)
