from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import time
from dataclasses import dataclass
from typing import Any

from shared.errors import DeadlineExceededError, WorkerQueueFullError, InternalServerError
from worker.model import ModelInterface


@dataclass
class BatcherResult:
    predictions: list[tuple[str, float]]
    queue_ms: float
    preprocess_ms: float
    inference_ms: float
    postprocess_ms: float
    worker_total_ms: float


@dataclass
class RequestEnvelope:
    request_id: str
    inputs: list[str]
    local_deadline: float
    enqueue_time: float
    future: asyncio.Future[BatcherResult]


class Batcher:
    def __init__(
        self,
        model: ModelInterface,
        queue_capacity: int = 64,
        max_batch_requests: int = 8,
        max_batch_items: int = 32,
        max_batch_delay_ms: int = 5,
    ) -> None:
        self.model = model
        self.queue_capacity = queue_capacity
        self.max_batch_requests = max_batch_requests
        self.max_batch_items = max_batch_items
        self.max_batch_delay_ms = max_batch_delay_ms

        self._queue: asyncio.Queue[RequestEnvelope] = asyncio.Queue(maxsize=queue_capacity)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._loop_task: asyncio.Task[None] | None = None
        self._stopping = False
        self._next_envelope: RequestEnvelope | None = None

    @property
    def queue_depth(self) -> int:
        depth = self._queue.qsize()
        if self._next_envelope is not None:
            depth += 1
        return depth

    def start(self) -> None:
        if self._loop_task is None or self._loop_task.done():
            loop = asyncio.get_running_loop()
            self._loop_task = loop.create_task(self._run_loop())

    async def enqueue(self, request_id: str, inputs: list[str], local_deadline: float) -> BatcherResult:
        if self._stopping:
            raise WorkerQueueFullError("Worker is shutting down.")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[BatcherResult] = loop.create_future()
        envelope = RequestEnvelope(
            request_id=request_id,
            inputs=inputs,
            local_deadline=local_deadline,
            enqueue_time=loop.time(),
            future=future,
        )

        try:
            self._queue.put_nowait(envelope)
        except asyncio.QueueFull:
            raise WorkerQueueFullError("Worker queue capacity reached.")

        self.start()
        return await future

    async def close(self) -> None:
        self._stopping = True
        if self._loop_task is not None and not self._loop_task.done():
            self._loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._loop_task
        self._executor.shutdown(wait=False, cancel_futures=True)

    async def _run_loop(self) -> None:
        loop = asyncio.get_running_loop()

        while not self._stopping:
            # 1. Fetch first envelope
            if self._next_envelope is not None:
                first = self._next_envelope
                self._next_envelope = None
            else:
                try:
                    first = await self._queue.get()
                except asyncio.CancelledError:
                    break

            # Check if first is cancelled or expired
            if first.future.done():
                continue

            now = loop.time()
            if now > first.local_deadline:
                first.future.set_exception(DeadlineExceededError("Deadline expired in queue."))
                continue

            batch: list[RequestEnvelope] = [first]
            total_items = len(first.inputs)

            # 2. Collect batch up to limits or delay timer
            delay_sec = self.max_batch_delay_ms / 1000.0
            deadline_timer = loop.time() + delay_sec

            while len(batch) < self.max_batch_requests and total_items < self.max_batch_items:
                remaining_time = deadline_timer - loop.time()
                if remaining_time <= 0:
                    break

                try:
                    envelope = await asyncio.wait_for(self._queue.get(), timeout=remaining_time)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    break

                if envelope.future.done():
                    continue

                if loop.time() > envelope.local_deadline:
                    envelope.future.set_exception(DeadlineExceededError("Deadline expired in queue."))
                    continue

                if total_items + len(envelope.inputs) > self.max_batch_items:
                    self._next_envelope = envelope
                    break

                batch.append(envelope)
                total_items += len(envelope.inputs)

            if not batch:
                continue

            # 3. Execute batch
            await self._process_batch(batch, loop)

    async def _process_batch(self, batch: list[RequestEnvelope], loop: asyncio.AbstractEventLoop) -> None:
        start_process_time = loop.time()
        flattened_inputs: list[str] = []
        slices: list[tuple[int, int]] = []

        idx = 0
        valid_batch: list[RequestEnvelope] = []
        for env in batch:
            if env.future.done():
                continue
            if loop.time() > env.local_deadline:
                env.future.set_exception(DeadlineExceededError("Deadline expired before execution."))
                continue
            valid_batch.append(env)
            flattened_inputs.extend(env.inputs)
            count = len(env.inputs)
            slices.append((idx, idx + count))
            idx += count

        if not valid_batch:
            return

        try:
            preds, prep_ms, inf_ms, post_ms = await loop.run_in_executor(
                self._executor, self.model.predict_batch, flattened_inputs
            )
        except Exception as exc:
            for env in valid_batch:
                if not env.future.done():
                    env.future.set_exception(InternalServerError("Inference failed."))
            return

        end_process_time = loop.time()

        for env, (s_start, s_end) in zip(valid_batch, slices):
            if env.future.done():
                continue

            req_preds = preds[s_start:s_end]
            queue_ms = (start_process_time - env.enqueue_time) * 1000.0
            worker_total_ms = (end_process_time - env.enqueue_time) * 1000.0

            result = BatcherResult(
                predictions=req_preds,
                queue_ms=max(0.0, queue_ms),
                preprocess_ms=prep_ms,
                inference_ms=inf_ms,
                postprocess_ms=post_ms,
                worker_total_ms=max(0.0, worker_total_ms),
            )

            if loop.time() > env.local_deadline:
                env.future.set_exception(DeadlineExceededError("Deadline expired after execution."))
            else:
                env.future.set_result(result)
