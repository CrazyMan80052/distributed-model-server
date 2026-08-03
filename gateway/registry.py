from __future__ import annotations

import asyncio
import contextlib
import enum
from dataclasses import dataclass
from typing import Any

import grpc
from generated.inference.v1 import inference_pb2, inference_pb2_grpc
from gateway.config import GatewayConfig
from gateway.metrics import GATEWAY_WORKER_HEALTHY
from shared.logging import get_logger

logger = get_logger("registry")


class HealthState(enum.Enum):
    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DRAINING = "draining"


@dataclass
class WorkerNode:
    worker_id: str
    address: str
    state: HealthState = HealthState.STARTING
    outstanding_requests: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_successful_check: float = 0.0
    channel: grpc.aio.Channel | None = None
    stub: inference_pb2_grpc.InferenceWorkerStub | None = None

    def get_stub(self) -> inference_pb2_grpc.InferenceWorkerStub:
        if self.stub is None:
            self.channel = grpc.aio.insecure_channel(self.address)
            self.stub = inference_pb2_grpc.InferenceWorkerStub(self.channel)
        return self.stub

    async def close(self) -> None:
        if self.channel is not None:
            await self.channel.close()
            self.channel = None
            self.stub = None


class WorkerRegistry:
    def __init__(self, config: GatewayConfig) -> None:
        self.config = config
        self.workers: dict[str, WorkerNode] = {
            wid: WorkerNode(worker_id=wid, address=addr)
            for wid, addr in config.workers.items()
        }
        self._poller_tasks: list[asyncio.Task[None]] = []
        self._stopping = False

    def is_any_worker_healthy(self) -> bool:
        return any(w.state == HealthState.HEALTHY for w in self.workers.values())

    def mark_unhealthy_immediately(self, worker_id: str) -> None:
        worker = self.workers.get(worker_id)
        if worker and worker.state == HealthState.HEALTHY:
            worker.state = HealthState.UNHEALTHY
            worker.consecutive_failures = self.config.health_failure_threshold
            worker.consecutive_successes = 0
            GATEWAY_WORKER_HEALTHY.labels(worker_id=worker_id).set(0)
            logger.log("warning", "worker_marked_unhealthy", worker_id=worker_id)

    async def start(self) -> None:
        self._stopping = False
        loop = asyncio.get_running_loop()
        for wid, worker in self.workers.items():
            task = loop.create_task(self._poll_worker_health(worker))
            self._poller_tasks.append(task)

    async def stop(self) -> None:
        self._stopping = True
        for task in self._poller_tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._poller_tasks.clear()

        for worker in self.workers.values():
            await worker.close()

    async def _poll_worker_health(self, worker: WorkerNode) -> None:
        while not self._stopping:
            try:
                stub = worker.get_stub()
                timeout = self.config.health_timeout_ms / 1000.0
                resp: inference_pb2.StatusResponse = await stub.GetStatus(
                    inference_pb2.StatusRequest(), timeout=timeout
                )

                compatible = (
                    resp.model_version == self.config.model_version
                    and resp.model_sha256 == self.config.model_sha256
                    and resp.state in (inference_pb2.WORKER_STATE_READY, inference_pb2.WORKER_STATE_STARTING)
                )

                if resp.state == inference_pb2.WORKER_STATE_DRAINING:
                    worker.state = HealthState.DRAINING
                    worker.consecutive_failures = 0
                    worker.consecutive_successes = 0
                    GATEWAY_WORKER_HEALTHY.labels(worker_id=worker.worker_id).set(0)
                elif compatible:
                    worker.consecutive_failures = 0
                    worker.consecutive_successes += 1
                    worker.last_successful_check = asyncio.get_running_loop().time()

                    if worker.state == HealthState.STARTING and worker.consecutive_successes >= 1:
                        worker.state = HealthState.HEALTHY
                        GATEWAY_WORKER_HEALTHY.labels(worker_id=worker.worker_id).set(1)
                        logger.log("info", "worker_healthy", worker_id=worker.worker_id)
                    elif (
                        worker.state == HealthState.UNHEALTHY
                        and worker.consecutive_successes >= self.config.health_recovery_threshold
                    ):
                        worker.state = HealthState.HEALTHY
                        GATEWAY_WORKER_HEALTHY.labels(worker_id=worker.worker_id).set(1)
                        logger.log("info", "worker_recovered", worker_id=worker.worker_id)
                else:
                    self._record_probe_failure(worker, "incompatible_status")

            except Exception:
                self._record_probe_failure(worker, "rpc_failed")

            await asyncio.sleep(self.config.health_interval_ms / 1000.0)

    def _record_probe_failure(self, worker: WorkerNode, reason: str) -> None:
        worker.consecutive_successes = 0
        worker.consecutive_failures += 1

        if (
            worker.state == HealthState.HEALTHY
            and worker.consecutive_failures >= self.config.health_failure_threshold
        ):
            worker.state = HealthState.UNHEALTHY
            GATEWAY_WORKER_HEALTHY.labels(worker_id=worker.worker_id).set(0)
            logger.log("warning", "worker_ejected", worker_id=worker.worker_id, reason=reason)
