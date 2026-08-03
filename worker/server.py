from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import sys
import time
from typing import Any

import grpc
from generated.inference.v1 import inference_pb2, inference_pb2_grpc
from shared.errors import AppError, DeadlineExceededError, WorkerQueueFullError
from shared.logging import get_logger
from worker.batcher import Batcher
from worker.config import WorkerConfig
from worker.metrics import (
    WORKER_MODEL_INFO,
    WORKER_QUEUE_DEPTH,
    WORKER_REQUESTS_TOTAL,
    start_worker_metrics_server,
)
from worker.model import FakeModel, ONNXModel

logger = get_logger("worker")


class InferenceWorkerServicer(inference_pb2_grpc.InferenceWorkerServicer):
    def __init__(self, config: WorkerConfig, batcher: Batcher) -> None:
        self.config = config
        self.batcher = batcher
        self.state = inference_pb2.WORKER_STATE_STARTING
        WORKER_MODEL_INFO.labels(
            worker_id=config.worker_id,
            model_version=config.model_version,
            model_sha256=config.model_sha256,
        ).set(1)

    async def Predict(
        self, request: inference_pb2.PredictRequest, context: grpc.aio.ServicerContext
    ) -> inference_pb2.PredictResponse:
        if self.state != inference_pb2.WORKER_STATE_READY:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "WORKER_NOT_READY")

        if not request.inputs or len(request.inputs) > 8:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "INVALID_REQUEST")

        if request.model_version != self.config.model_version:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "UNSUPPORTED_MODEL")

        time_remaining = context.time_remaining()
        if time_remaining is None or time_remaining <= 0:
            await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "DEADLINE_EXCEEDED")

        loop = asyncio.get_running_loop()
        local_deadline = loop.time() + time_remaining

        try:
            result = await self.batcher.enqueue(request.request_id, list(request.inputs), local_deadline)
        except WorkerQueueFullError:
            WORKER_REQUESTS_TOTAL.labels(result="queue_full").inc()
            await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "WORKER_QUEUE_FULL")
        except DeadlineExceededError:
            WORKER_REQUESTS_TOTAL.labels(result="deadline_exceeded").inc()
            await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "DEADLINE_EXCEEDED")
        except AppError as exc:
            WORKER_REQUESTS_TOTAL.labels(result="error").inc()
            await context.abort(grpc.StatusCode.INTERNAL, exc.code)
        except Exception:
            WORKER_REQUESTS_TOTAL.labels(result="error").inc()
            await context.abort(grpc.StatusCode.INTERNAL, "INTERNAL_ERROR")

        WORKER_REQUESTS_TOTAL.labels(result="success").inc()

        predictions = [
            inference_pb2.Prediction(label=label, score=score)
            for label, score in result.predictions
        ]

        timing = inference_pb2.WorkerTiming(
            queue_ms=result.queue_ms,
            preprocess_ms=result.preprocess_ms,
            inference_ms=result.inference_ms,
            postprocess_ms=result.postprocess_ms,
            worker_total_ms=result.worker_total_ms,
        )

        return inference_pb2.PredictResponse(
            request_id=request.request_id,
            model_version=self.config.model_version,
            worker_id=self.config.worker_id,
            predictions=predictions,
            timing=timing,
        )

    async def GetStatus(
        self, request: inference_pb2.StatusRequest, context: grpc.aio.ServicerContext
    ) -> inference_pb2.StatusResponse:
        WORKER_QUEUE_DEPTH.set(self.batcher.queue_depth)
        return inference_pb2.StatusResponse(
            worker_id=self.config.worker_id,
            model_version=self.config.model_version,
            model_sha256=self.config.model_sha256,
            state=self.state,
            queue_depth=self.batcher.queue_depth,
            queue_capacity=self.config.queue_capacity,
            active_batches=0,
        )


async def serve(config: WorkerConfig | None = None, use_fake_model: bool = False) -> None:
    if config is None:
        config = WorkerConfig()

    logger.log("info", "starting_worker", worker_id=config.worker_id, port=config.grpc_port)
    start_worker_metrics_server(config.metrics_port)

    if use_fake_model or os.getenv("USE_FAKE_MODEL", "false").lower() == "true":
        model = FakeModel()
    else:
        model = ONNXModel(
            config.model_dir,
            intra_op_threads=config.ort_intra_op_threads,
            inter_op_threads=config.ort_inter_op_threads,
        )

    batcher = Batcher(
        model=model,
        queue_capacity=config.queue_capacity,
        max_batch_requests=config.max_batch_requests,
        max_batch_items=config.max_batch_items,
        max_batch_delay_ms=config.max_batch_delay_ms,
    )

    servicer = InferenceWorkerServicer(config, batcher)
    server = grpc.aio.server()
    inference_pb2_grpc.add_InferenceWorkerServicer_to_server(servicer, server)

    server.add_insecure_port(f"[::]:{config.grpc_port}")
    await server.start()
    servicer.state = inference_pb2.WORKER_STATE_READY
    logger.log("info", "worker_ready", worker_id=config.worker_id)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler() -> None:
        servicer.state = inference_pb2.WORKER_STATE_DRAINING
        logger.log("info", "worker_draining", worker_id=config.worker_id)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _sig_handler)

    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        servicer.state = inference_pb2.WORKER_STATE_DRAINING
        await batcher.close()
        await server.stop(grace=10)
        logger.log("info", "worker_stopped", worker_id=config.worker_id)


if __name__ == "__main__":
    asyncio.run(serve())
