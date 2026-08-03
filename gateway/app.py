from __future__ import annotations

import asyncio
import contextlib
import re
import time
import uuid
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import generate_latest

from gateway.client import GatewayClient
from gateway.config import GatewayConfig
from gateway.metrics import (
    GATEWAY_ACTIVE_REQUESTS,
    GATEWAY_REQUEST_DURATION_SECONDS,
    GATEWAY_REQUESTS_TOTAL,
)
from gateway.registry import WorkerRegistry
from gateway.scheduler import Scheduler
from shared.errors import (
    AppError,
    InvalidRequestError,
    RequestTooLargeError,
    ServiceDrainingError,
    UnsupportedModelError,
)

REQUEST_ID_REGEX = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

config = GatewayConfig()
registry = WorkerRegistry(config)
scheduler = Scheduler(registry, config)
client = GatewayClient(registry, scheduler, config)

accepting_requests = True


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global accepting_requests
    accepting_requests = True
    await registry.start()
    yield
    accepting_requests = False
    await registry.stop()


app = FastAPI(title="Distributed Model Server Gateway", lifespan=lifespan)


@app.middleware("http")
async def body_limit_and_metrics_middleware(request: Request, call_next: any) -> Response:
    global accepting_requests

    if request.url.path == "/v1/predict":
        if not accepting_requests:
            return JSONResponse(
                status_code=503,
                content={
                    "request_id": "",
                    "error": ServiceDrainingError().to_dict(),
                },
            )

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > config.http_max_body_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "request_id": "",
                    "error": RequestTooLargeError().to_dict(),
                },
            )

        # Stream body to verify length strictly
        body = await request.body()
        if len(body) > config.http_max_body_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "request_id": "",
                    "error": RequestTooLargeError().to_dict(),
                },
            )

    GATEWAY_ACTIVE_REQUESTS.inc()
    start_time = time.perf_counter()
    status_code = 500
    error_code = "NONE"

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except AppError as app_err:
        status_code = app_err.status_code
        error_code = app_err.code
        return JSONResponse(
            status_code=app_err.status_code,
            content={"request_id": "", "error": app_err.to_dict()},
        )
    except Exception:
        status_code = 500
        error_code = "INTERNAL_ERROR"
        return JSONResponse(
            status_code=500,
            content={
                "request_id": "",
                "error": {"code": "INTERNAL_ERROR", "message": "Internal server error."},
            },
        )
    finally:
        GATEWAY_ACTIVE_REQUESTS.dec()
        duration = time.perf_counter() - start_time
        GATEWAY_REQUEST_DURATION_SECONDS.observe(duration)
        GATEWAY_REQUESTS_TOTAL.labels(status_code=str(status_code), error_code=error_code).inc()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, __: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"request_id": "", "error": InvalidRequestError().to_dict()},
    )


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
async def health_ready() -> JSONResponse:
    if accepting_requests and registry.is_any_worker_healthy():
        return JSONResponse(status_code=200, content={"status": "ready"})
    return JSONResponse(status_code=503, content={"status": "not_ready"})


@app.get("/metrics")
async def metrics() -> Response:
    return PlainTextResponse(generate_latest().decode("utf-8"))


@app.post("/v1/predict")
async def predict(request: Request) -> JSONResponse:
    t0 = time.perf_counter()
    try:
        payload = await request.json()
    except Exception:
        raise InvalidRequestError("Invalid JSON payload.")

    if not isinstance(payload, dict):
        raise InvalidRequestError("Payload must be a JSON object.")

    # Validate extra unknown keys
    allowed_keys = {"request_id", "inputs", "model_version", "timeout_ms"}
    if set(payload.keys()) - allowed_keys:
        raise InvalidRequestError("Unknown fields in payload.")

    req_id = payload.get("request_id")
    if req_id is None:
        req_id = uuid.uuid4().hex
    elif not isinstance(req_id, str) or not REQUEST_ID_REGEX.match(req_id):
        raise InvalidRequestError("Invalid request_id format.")

    inputs = payload.get("inputs")
    if not isinstance(inputs, list) or not inputs or len(inputs) > config.max_inputs_per_request:
        raise InvalidRequestError("inputs must be a non-empty list of 1 to 8 strings.")

    total_bytes = 0
    for inp in inputs:
        if not isinstance(inp, str) or not inp:
            raise InvalidRequestError("inputs elements must be non-empty strings.")
        inp_bytes = len(inp.encode("utf-8"))
        if inp_bytes > config.max_input_bytes:
            raise RequestTooLargeError("Input item byte limit exceeded.")
        total_bytes += inp_bytes

    if total_bytes > config.max_total_input_bytes:
        raise RequestTooLargeError("Total inputs byte limit exceeded.")

    model_ver = payload.get("model_version", config.model_version)
    if model_ver != config.model_version:
        raise UnsupportedModelError()

    timeout_ms = payload.get("timeout_ms", config.default_timeout_ms)
    if not isinstance(timeout_ms, int) or not (config.min_timeout_ms <= timeout_ms <= config.max_timeout_ms):
        raise InvalidRequestError("timeout_ms out of bounds.")

    try:
        res = await client.predict(
            request_id=req_id,
            inputs=inputs,
            model_version=model_ver,
            timeout_ms=timeout_ms,
        )
    except AppError as app_err:
        return JSONResponse(
            status_code=app_err.status_code,
            content={"request_id": req_id, "error": app_err.to_dict()},
        )

    t1 = time.perf_counter()
    total_ms = round((t1 - t0) * 1000.0, 2)

    res.worker_timing["total"] = total_ms

    return JSONResponse(
        status_code=200,
        content={
            "request_id": req_id,
            "model_version": model_ver,
            "worker_id": res.worker_id,
            "attempts": res.attempts,
            "predictions": res.predictions,
            "timing_ms": res.worker_timing,
        },
    )
