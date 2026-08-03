from __future__ import annotations

import asyncio
from dataclasses import dataclass

import grpc
from generated.inference.v1 import inference_pb2, inference_pb2_grpc
from gateway.config import GatewayConfig
from gateway.metrics import GATEWAY_RETRIES_TOTAL, GATEWAY_RPC_FAILURES_TOTAL
from gateway.registry import WorkerNode, WorkerRegistry
from gateway.scheduler import Scheduler
from shared.errors import (
    AppError,
    DeadlineExceededError,
    InternalServerError,
    InvalidRequestError,
    UnsupportedModelError,
    WorkerQueueFullError,
    WorkerUnavailableError,
)
from shared.logging import get_logger

logger = get_logger("client")


@dataclass
class GatewayPredictionResult:
    worker_id: str
    attempts: int
    predictions: list[dict[str, float | str]]
    worker_timing: dict[str, float]


class GatewayClient:
    def __init__(
        self,
        registry: WorkerRegistry,
        scheduler: Scheduler,
        config: GatewayConfig,
    ) -> None:
        self.registry = registry
        self.scheduler = scheduler
        self.config = config

    async def predict(
        self,
        request_id: str,
        inputs: list[str],
        model_version: str,
        timeout_ms: int,
    ) -> GatewayPredictionResult:
        loop = asyncio.get_running_loop()
        gateway_deadline = loop.time() + (timeout_ms / 1000.0)
        exclude_ids: set[str] = set()

        for attempt in (1, 2):
            remaining = gateway_deadline - loop.time()
            if remaining <= 0:
                raise DeadlineExceededError("Gateway deadline exceeded before RPC dispatch.")

            worker = await self.scheduler.select_worker(exclude_ids=exclude_ids)
            try:
                stub = worker.get_stub()
                req = inference_pb2.PredictRequest(
                    request_id=request_id,
                    model_version=model_version,
                    inputs=inputs,
                )
                resp: inference_pb2.PredictResponse = await stub.Predict(req, timeout=remaining)

                predictions = [
                    {"label": p.label, "score": float(p.score)}
                    for p in resp.predictions
                ]

                timing = {
                    "queue": resp.timing.queue_ms,
                    "preprocess": resp.timing.preprocess_ms,
                    "inference": resp.timing.inference_ms,
                    "postprocess": resp.timing.postprocess_ms,
                    "worker_total": resp.timing.worker_total_ms,
                }

                return GatewayPredictionResult(
                    worker_id=worker.worker_id,
                    attempts=attempt,
                    predictions=predictions,
                    worker_timing=timing,
                )
            except grpc.aio.AioRpcError as rpc_err:
                GATEWAY_RPC_FAILURES_TOTAL.labels(
                    worker_id=worker.worker_id, grpc_code=rpc_err.code().name
                ).inc()

                if rpc_err.code() == grpc.StatusCode.UNAVAILABLE:
                    self.registry.mark_unhealthy_immediately(worker.worker_id)
                    exclude_ids.add(worker.worker_id)
                    remaining_after = gateway_deadline - loop.time()
                    if (
                        attempt == 1
                        and (remaining_after * 1000.0) >= self.config.min_retry_budget_ms
                    ):
                        GATEWAY_RETRIES_TOTAL.labels(result="attempted").inc()
                        continue
                    else:
                        GATEWAY_RETRIES_TOTAL.labels(result="failed").inc()
                        raise WorkerUnavailableError("Worker unavailable and retry budget exhausted.")

                self._map_rpc_error(rpc_err)

            finally:
                await self.scheduler.release_worker(worker.worker_id)

        raise WorkerUnavailableError("Prediction failed after retries.")

    def _map_rpc_error(self, rpc_err: grpc.aio.AioRpcError) -> None:
        code = rpc_err.code()
        details = rpc_err.details() or ""

        if code == grpc.StatusCode.INVALID_ARGUMENT:
            if "UNSUPPORTED_MODEL" in details:
                raise UnsupportedModelError()
            raise InvalidRequestError()
        elif code == grpc.StatusCode.RESOURCE_EXHAUSTED:
            raise WorkerQueueFullError()
        elif code == grpc.StatusCode.FAILED_PRECONDITION:
            raise WorkerUnavailableError()
        elif code == grpc.StatusCode.DEADLINE_EXCEEDED:
            raise DeadlineExceededError()
        elif code == grpc.StatusCode.INTERNAL:
            raise InternalServerError()
        else:
            raise InternalServerError(f"gRPC error: {code.name}")
