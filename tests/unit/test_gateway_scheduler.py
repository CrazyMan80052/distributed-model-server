import pytest

from gateway.config import GatewayConfig
from gateway.registry import HealthState, WorkerNode, WorkerRegistry
from gateway.scheduler import Scheduler
from shared.errors import GatewayAtCapacityError, NoHealthyWorkerError


@pytest.mark.asyncio
async def test_scheduler_least_outstanding():
    config = GatewayConfig(workers_raw="w1=w1:50051,w2=w2:50051")
    registry = WorkerRegistry(config)
    registry.workers["w1"].state = HealthState.HEALTHY
    registry.workers["w2"].state = HealthState.HEALTHY

    scheduler = Scheduler(registry, config)

    # First selection should pick w1 (or w2) and increment
    selected1 = await scheduler.select_worker()
    assert selected1.outstanding_requests == 1

    # Second selection picks the other candidate with 0 outstanding
    selected2 = await scheduler.select_worker()
    assert selected2.worker_id != selected1.worker_id
    assert selected2.outstanding_requests == 1

    await scheduler.release_worker(selected1.worker_id)
    assert selected1.outstanding_requests == 0


@pytest.mark.asyncio
async def test_scheduler_no_healthy_workers():
    config = GatewayConfig(workers_raw="w1=w1:50051")
    registry = WorkerRegistry(config)
    registry.workers["w1"].state = HealthState.UNHEALTHY

    scheduler = Scheduler(registry, config)
    with pytest.raises(NoHealthyWorkerError):
        await scheduler.select_worker()


@pytest.mark.asyncio
async def test_scheduler_gateway_at_capacity():
    config = GatewayConfig(workers_raw="w1=w1:50051", gateway_max_outstanding_per_worker=1)
    registry = WorkerRegistry(config)
    registry.workers["w1"].state = HealthState.HEALTHY
    registry.workers["w1"].outstanding_requests = 1

    scheduler = Scheduler(registry, config)
    with pytest.raises(GatewayAtCapacityError):
        await scheduler.select_worker()
