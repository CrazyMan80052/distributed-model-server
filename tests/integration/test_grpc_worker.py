import asyncio
import pytest
import grpc

from generated.inference.v1 import inference_pb2, inference_pb2_grpc
from gateway.client import GatewayClient
from gateway.config import GatewayConfig
from gateway.registry import HealthState, WorkerRegistry
from gateway.scheduler import Scheduler
from worker.batcher import Batcher
from worker.config import WorkerConfig
from worker.model import FakeModel, ONNXModel
from worker.server import InferenceWorkerServicer


@pytest.mark.asyncio
async def test_grpc_worker_integration():
    # 1. Start a live gRPC worker server on an ephemeral port
    worker_config = WorkerConfig(worker_id="worker-test", grpc_port=50099)
    batcher = Batcher(model=FakeModel())
    servicer = InferenceWorkerServicer(worker_config, batcher)

    server = grpc.aio.server()
    inference_pb2_grpc.add_InferenceWorkerServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    servicer.state = inference_pb2.WORKER_STATE_READY

    try:
        # 2. Setup Gateway with client pointing to this test server
        gw_config = GatewayConfig(workers_raw=f"worker-test=127.0.0.1:{port}")
        registry = WorkerRegistry(gw_config)
        registry.workers["worker-test"].state = HealthState.HEALTHY

        scheduler = Scheduler(registry, gw_config)
        client = GatewayClient(registry, scheduler, gw_config)

        # 3. Perform prediction request over gRPC
        res = await client.predict(
            request_id="test-req-1",
            inputs=["I love this model server!", "I hate bugs."],
            model_version="tinybert-sst2-v1",
            timeout_ms=1000,
        )

        assert res.worker_id == "worker-test"
        assert res.attempts == 1
        assert len(res.predictions) == 2
        assert res.predictions[0]["label"] == "positive"
        assert res.predictions[1]["label"] == "negative"
        assert res.worker_timing["queue"] >= 0.0

        await registry.stop()

    finally:
        await batcher.close()
        await server.stop(grace=0)


@pytest.mark.asyncio
async def test_grpc_real_onnx_model_integration():
    # Test real ONNX model prediction if artifacts exist
    try:
        model = ONNXModel("artifacts/model")
    except Exception:
        pytest.skip("Model artifacts not downloaded.")

    worker_config = WorkerConfig(worker_id="worker-onnx")
    batcher = Batcher(model=model)
    servicer = InferenceWorkerServicer(worker_config, batcher)

    server = grpc.aio.server()
    inference_pb2_grpc.add_InferenceWorkerServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    servicer.state = inference_pb2.WORKER_STATE_READY

    try:
        gw_config = GatewayConfig(workers_raw=f"worker-onnx=127.0.0.1:{port}")
        registry = WorkerRegistry(gw_config)
        registry.workers["worker-onnx"].state = HealthState.HEALTHY

        scheduler = Scheduler(registry, gw_config)
        client = GatewayClient(registry, scheduler, gw_config)

        res = await client.predict(
            request_id="onnx-req-1",
            inputs=["I love this movie.", "I hate this movie."],
            model_version="tinybert-sst2-v1",
            timeout_ms=5000,
        )

        assert res.worker_id == "worker-onnx"
        assert len(res.predictions) == 2
        assert res.predictions[0]["label"] == "positive"
        assert res.predictions[1]["label"] == "negative"

        await registry.stop()
    finally:
        await batcher.close()
        await server.stop(grace=0)
