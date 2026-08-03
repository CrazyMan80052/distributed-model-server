import asyncio
import pytest

from shared.errors import DeadlineExceededError, WorkerQueueFullError
from worker.batcher import Batcher, RequestEnvelope
from worker.model import FakeModel


@pytest.mark.asyncio
async def test_batcher_single_request():
    batcher = Batcher(model=FakeModel(), max_batch_requests=8)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 2.0

    res = await batcher.enqueue("req-1", ["I love this movie."], deadline)
    assert len(res.predictions) == 1
    assert res.predictions[0][0] == "positive"
    assert res.predictions[0][1] >= 0.5
    assert res.worker_total_ms >= 0.0
    await batcher.close()


@pytest.mark.asyncio
async def test_batcher_batching_multiple_requests():
    batcher = Batcher(model=FakeModel(), max_batch_requests=4, max_batch_delay_ms=20)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 2.0

    t1 = asyncio.create_task(batcher.enqueue("req-1", ["I love this."], deadline))
    t2 = asyncio.create_task(batcher.enqueue("req-2", ["I hate this."], deadline))

    res1, res2 = await asyncio.gather(t1, t2)
    assert res1.predictions[0][0] == "positive"
    assert res2.predictions[0][0] == "negative"
    await batcher.close()


@pytest.mark.asyncio
async def test_batcher_queue_overflow():
    batcher = Batcher(model=FakeModel(), queue_capacity=1)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 2.0

    # Fill queue capacity directly
    dummy_future = loop.create_future()
    batcher._queue.put_nowait(
        RequestEnvelope("req-dummy", ["a"], deadline, loop.time(), dummy_future)
    )

    with pytest.raises(WorkerQueueFullError):
        await batcher.enqueue("req-overflow", ["b"], deadline)

    await batcher.close()


@pytest.mark.asyncio
async def test_batcher_expired_deadline():
    batcher = Batcher(model=FakeModel())
    loop = asyncio.get_running_loop()
    past_deadline = loop.time() - 0.1

    with pytest.raises(DeadlineExceededError):
        await batcher.enqueue("req-1", ["expired"], past_deadline)

    await batcher.close()
