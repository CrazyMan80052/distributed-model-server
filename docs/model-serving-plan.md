# Distributed Model Serving System


## Project Status

The design is intentionally small and opinionated so implementation can proceed
without choosing infrastructure, researching models, or inventing contracts while
coding.


Estimated effort:


- 3 focused days for a working local MVP
- 6-8 focused days for the tested, benchmarked, documented release
- No cloud account, GPU, Kubernetes cluster, model training, or model export required


Recommended implementation shape:


- Build the core request path first with fake model and fake clock tests.
- Keep the first milestone single-worker and local before adding routing or Compose.
- Treat batching, retries, health recovery, benchmarks, and docs as later milestones.
- If you want to learn the code yourself, do Milestones 0-2 personally and leave the later hardening work to agents.


Stop after the required release. Optional optimizations are allowed only when a
benchmark identifies a specific bottleneck.


### One-Time Prerequisites


Install these before implementation:


- Docker Desktop with Docker Compose v2
- Python 3.12 for local tests and benchmark scripts
- Git and Make, which are normally available through macOS command-line tools


Preflight:


```bash
docker compose version
python3.12 --version
git --version
make --version
```


Expected major Python version: `3.12`. Do not build against the machine's default
Python when it is a different version. On macOS, the shortest setup path is Docker
Desktop plus `brew install python@3.12` when Homebrew is already available.


## 1. Locked Decisions


These choices are part of the plan:


- Python 3.12
- FastAPI HTTP gateway
- `grpc.aio` worker RPCs with checked-in generated Protobuf code
- One pinned 17 MB TinyBERT SST-2 ONNX model
- Hugging Face `tokenizers` loaded from a local `tokenizer.json`
- ONNX Runtime CPU execution
- One bounded request queue and one inference executor per worker
- Dynamic batching with one inference batch active per worker
- Four statically named Compose worker definitions; two start by default
- Least-outstanding-request routing
- Health-based worker ejection and one retry on `UNAVAILABLE`
- Prometheus-format metrics without running a Prometheus server
- Closed-loop HTTP load generation
- Local Docker Compose deployment only


Do not add circuit breaking, service discovery, Redis, Kafka, Kubernetes,
OpenTelemetry, authentication, a dashboard, model training, or multiple models to
the required release.


## 2. Summary


Build a local distributed inference service that accepts sentiment-classification
requests through an HTTP gateway and routes them over gRPC to multiple model
workers. Each worker runs the same pinned ONNX model, admits requests through a
bounded queue, combines requests into dynamic micro-batches, and returns predictions
before the request deadline.


```text
load generator
     |
     | HTTP/JSON
     v
+---------------------+
| inference gateway   |
| validation          |
| deadlines           |
| worker health       |
| least-loaded routing|
+----------+----------+
          |
          | gRPC + Protobuf
          |
    +-----+-------------------+
    |             |           |
    v             v           v
+----------+  +----------+  +----------+
| worker 1 |  | worker 2 |  | worker N |
| queue    |  | queue    |  | queue    |
| batcher  |  | batcher  |  | batcher  |
| ONNX     |  | ONNX     |  | ONNX     |
+----------+  +----------+  +----------+
```


The project demonstrates service boundaries, concurrency, overload behavior,
failure recovery, observability, and reproducible measurement. It does not make
claims about model quality.


## 3. Required Release and Non-Goals


### Required


- `POST /v1/predict`
- Gateway liveness, readiness, and metrics endpoints
- Two workers in the default Compose stack
- Versioned Protobuf over gRPC
- Pinned local model artifacts with checksum verification
- Bounded gateway concurrency, worker queues, input sizes, and batches
- Deadline propagation through gRPC
- Dynamic micro-batching
- Health polling, worker ejection, recovery, and one bounded retry
- Explicit overload and unavailable errors
- Structured logs with input redaction
- Graceful shutdown
- Unit, integration, and Compose end-to-end tests
- Reproducible scaling, batching, overload, and failure benchmarks
- Saved raw measurements and generated summaries


### Explicit Non-Goals


- Model training, fine-tuning, evaluation, or quality claims
- GPU serving
- Multi-host deployment
- Kubernetes or automatic scaling
- Dynamic service discovery
- Circuit breakers
- Persistent queues or asynchronous jobs
- Multiple models or online model updates
- Authentication, billing, or a web dashboard
- Streaming generation
- Hard cancellation of an ONNX call already in progress
- Active polling for HTTP client disconnects
- Exactly-once processing


The system is multi-process and networked, but it must not be described as
multi-host, globally distributed, production deployed, or production ready.


## 4. Definition of Done


The release is complete only when:


1. A clean checkout starts the default stack with the documented setup and Compose
  commands.
2. One gateway and two independent worker containers become ready.
3. Gateway-to-worker traffic uses the checked-in `inference.v1` Protobuf contract.
4. All configured limits have tests at the boundary and one value beyond it.
5. The worker never runs more than one inference batch concurrently.
6. The gateway propagates remaining deadline budget as the gRPC timeout.
7. An unhealthy worker receives no new requests and returns after two successful
  health probes.
8. Gateway and worker overload return explicit errors without unbounded admission.
9. Shutdown resolves or fails every accepted request within 10 seconds.
10. Unit, integration, and Compose end-to-end tests pass.
11. Required benchmarks have three saved trials per configuration.
12. Raw output includes request latencies, status/error counts, worker assignment,
   queue time, batch sizes, CPU, and memory.
13. The README contains exact setup, test, failure, and benchmark commands.
14. Every resume metric can be regenerated from committed raw results.


No throughput, latency, scaling, or memory target is assumed. Report the measured
result, including weak or negative scaling.


## 5. Exact Model and Artifacts


Use this model to avoid training or ONNX export:


- Task: binary SST-2 sentiment classification
- Public model name: `philschmid/tiny-bert-sst2-distilled`
- ONNX export repository:
 `fxmarty/tiny-bert-sst2-distilled-onnx-subfolder`
- License declared by both repositories: Apache-2.0
- Model version exposed by the service: `tinybert-sst2-v1`
- Labels: output index `0` is `negative`; output index `1` is `positive`
- Runtime maximum: 128 tokens per input
- Inputs longer than 128 tokens are truncated
- Model quality is outside project scope


The sources and checksums below were verified on July 18, 2026. Download from the
immutable commit URLs, never from `main`.


| Local file | Immutable source | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `artifacts/model/model.onnx` | `https://huggingface.co/fxmarty/tiny-bert-sst2-distilled-onnx-subfolder/resolve/d3017b38272765ae30e68f73de1fcb432bb97f3d/my_subfolder/model.onnx` | 17,568,406 | `23ea44ed3eb302e22045900ba8565dd672a9f4c127f5514ce182f01d83fe2e3a` |
| `artifacts/model/config.json` | `https://huggingface.co/fxmarty/tiny-bert-sst2-distilled-onnx-subfolder/resolve/d3017b38272765ae30e68f73de1fcb432bb97f3d/my_subfolder/config.json` | 844 | `3049b86c8f85f0bb54c79b359c9b91f6581e13f2a28d5e5eaac97381b53cb077` |
| `artifacts/model/tokenizer.json` | `https://huggingface.co/philschmid/tiny-bert-sst2-distilled/resolve/874eb28543ea7a7df80b6158bbf772d203efcab6/tokenizer.json` | 466,132 | `99e552efd3b68340ef1b1106ea152526659a9c525992f008fe4c182a5a587234` |
| `artifacts/model/licenses/onnx-export-README.md` | `https://huggingface.co/fxmarty/tiny-bert-sst2-distilled-onnx-subfolder/raw/d3017b38272765ae30e68f73de1fcb432bb97f3d/README.md` | 28 | `98b45ea81164d1e1a1dd82255207053b15cd6c69d922a1c5cf3387ce604d4b74` |
| `artifacts/model/licenses/source-model-README.md` | `https://huggingface.co/philschmid/tiny-bert-sst2-distilled/raw/874eb28543ea7a7df80b6158bbf772d203efcab6/README.md` | 2,036 | `8b2aeb54de195d4023fdb47af43646271c9b354a6e853d3a41ed93b3f52d0b7d` |


The setup script must:


1. Create `artifacts/model/`.
2. Download each file to a temporary name.
3. Calculate SHA-256 and reject any mismatch.
4. Atomically rename verified files.
5. Preserve the verified model cards in `artifacts/model/licenses/`.
6. Exit successfully without downloading when existing files match.


The service never downloads artifacts during startup. Compose mounts
`artifacts/model/` read-only into each worker. The artifact directory is excluded
from Git except for its README and checksum manifest.


The first real-model test uses:


- `"I love this movie."` and expects label `positive`
- `"I hate this movie."` and expects label `negative`


Do not assert an exact floating-point score. Assert the label, a score in `[0, 1]`,
and repeatability within `1e-5` on the same machine and runtime.


## 6. Stack and Dependencies


Runtime dependencies:


- `fastapi`
- `uvicorn`
- `grpcio`
- `protobuf`
- `onnxruntime`
- `tokenizers`
- `numpy`
- `prometheus-client`


Development dependencies:


- `grpcio-tools`
- `httpx`
- `pytest`
- `pytest-asyncio`
- `ruff`
- `mypy`


Use exact pins in `requirements.txt` and `requirements-dev.txt`. A safe initial
baseline is:


```text
fastapi==0.115.12
uvicorn==0.34.3
grpcio==1.71.0
grpcio-tools==1.71.0
protobuf==5.29.5
onnxruntime==1.22.0
tokenizers==0.21.1
numpy==2.2.6
prometheus-client==0.22.1
httpx==0.28.1
pytest==8.4.0
pytest-asyncio==1.0.0
ruff==0.11.13
mypy==1.16.0
```


If a pin does not install on the development machine, change only the incompatible
pin, document the reason in the first commit, and use the resulting exact version
everywhere. Do not leave version ranges.


## 7. Repository Layout


```text
distributed-model-serving/
 README.md
 Makefile
 pyproject.toml
 requirements.txt
 requirements-dev.txt
 Dockerfile
 compose.yaml
 artifacts/
   model/
     README.md
     checksums.json
     licenses/
 proto/
   inference/v1/inference.proto
 generated/
   __init__.py
   inference/
     __init__.py
     v1/
       __init__.py
       inference_pb2.py
       inference_pb2_grpc.py
 gateway/
   __init__.py
   app.py
   config.py
   registry.py
   scheduler.py
   client.py
   metrics.py
 worker/
   __init__.py
   server.py
   config.py
   batcher.py
   model.py
   metrics.py
 shared/
   __init__.py
   errors.py
   logging.py
 scripts/
   download_model.py
   benchmark.py
   summarize_results.py
   sample_resources.py
   failure_scenario.py
 tests/
   unit/
   integration/
   e2e/
 benchmarks/
   corpus.jsonl
   configs/
   raw/
   reports/
 docs/
   architecture.md
   reliability.md
   benchmark-methodology.md
```


Keep scheduling, health transitions, and batching independent from FastAPI and gRPC
adapters. Use a fake monotonic clock and a fake model backend in most tests.


## 8. Configuration


All settings come from environment variables, are parsed once at startup, and fail
startup on invalid values. Tests may construct configuration objects directly.


| Setting | Default | Meaning |
| --- | ---: | --- |
| `MODEL_VERSION` | `tinybert-sst2-v1` | Only accepted model version |
| `MODEL_SHA256` | `23ea44ed3eb302e22045900ba8565dd672a9f4c127f5514ce182f01d83fe2e3a` | Expected ONNX hash |
| `MODEL_DIR` | `/models` | Read-only artifact directory in workers |
| `HTTP_MAX_BODY_BYTES` | `65536` | Maximum complete JSON body |
| `MAX_INPUTS_PER_REQUEST` | `8` | Maximum strings per request |
| `MAX_INPUT_BYTES` | `4096` | Maximum UTF-8 bytes per string |
| `MAX_TOTAL_INPUT_BYTES` | `32768` | Maximum UTF-8 bytes across inputs |
| `MAX_TOKENS_PER_INPUT` | `128` | Tokenizer truncation length |
| `MIN_TIMEOUT_MS` | `100` | Smallest caller timeout |
| `MAX_TIMEOUT_MS` | `10000` | Largest caller timeout |
| `DEFAULT_TIMEOUT_MS` | `1000` | Used when omitted |
| `GATEWAY_MAX_OUTSTANDING_PER_WORKER` | `32` | Local routing reservation limit |
| `WORKER_QUEUE_CAPACITY` | `64` | Queued requests, excluding active batch |
| `MAX_BATCH_REQUESTS` | `8` | Requests per inference batch |
| `MAX_BATCH_ITEMS` | `32` | Flattened input strings per batch |
| `MAX_BATCH_DELAY_MS` | `5` | Wait after first request |
| `HEALTH_INTERVAL_MS` | `1000` | Status polling interval |
| `HEALTH_TIMEOUT_MS` | `250` | Timeout for one status RPC |
| `HEALTH_FAILURE_THRESHOLD` | `3` | Failures before periodic ejection |
| `HEALTH_RECOVERY_THRESHOLD` | `2` | Successes before restoration |
| `MIN_RETRY_BUDGET_MS` | `50` | Remaining budget required for retry |
| `SHUTDOWN_GRACE_SECONDS` | `10` | Gateway and worker drain limit |
| `ORT_INTRA_OP_THREADS` | `1` | ONNX intra-operation threads |
| `ORT_INTER_OP_THREADS` | `1` | ONNX inter-operation threads |
| `WORKER_METRICS_PORT` | `9100` | Prometheus worker endpoint |


Gateway worker configuration is a comma-separated static list:


```text
WORKERS=worker-1=worker-1:50051,worker-2=worker-2:50051,worker-3=worker-3:50051,worker-4=worker-4:50051
```


The gateway may be ready when at least one compatible worker is healthy. Missing
configured workers remain unhealthy; they do not prevent startup.


## 9. Public HTTP Contract


### Request


`POST /v1/predict`


```json
{
 "request_id": "optional-client-id",
 "inputs": ["First text", "Second text"],
 "model_version": "tinybert-sst2-v1",
 "timeout_ms": 1000
}
```


Rules:


- Reject unknown JSON fields.
- Generate a UUID4 hex request ID when omitted.
- Client request IDs must match `[A-Za-z0-9._-]{1,64}`.
- `inputs` contains 1-8 non-empty strings.
- Enforce body, per-input, and total UTF-8 byte limits from Section 8.
- `model_version` defaults to and must equal `tinybert-sst2-v1`.
- `timeout_ms` defaults to 1000 and must be between 100 and 10,000.
- Text beyond 128 model tokens is intentionally truncated by the worker.
- Never return, log, or use input text as a metric label.


Use a small ASGI body-limit middleware that stops reading and returns `413` once
65,536 bytes are received. Do not rely only on `Content-Length`.


### Success Response


```json
{
 "request_id": "resolved-id",
 "model_version": "tinybert-sst2-v1",
 "worker_id": "worker-2",
 "attempts": 1,
 "predictions": [
   {"label": "positive", "score": 0.97},
   {"label": "negative", "score": 0.81}
 ],
 "timing_ms": {
   "queue": 2.1,
   "preprocess": 0.9,
   "inference": 6.8,
   "postprocess": 0.1,
   "worker_total": 9.9,
   "total": 11.7
 }
}
```


Prediction order exactly matches input order. `worker_total` covers the successful
worker attempt. `total` starts after the gateway accepts and validates the body and
ends immediately before response serialization. With a retry, `total` includes both
attempts while worker timing describes only the successful attempt.


### Error Response


```json
{
 "request_id": "resolved-id",
 "error": {
   "code": "NO_HEALTHY_WORKER",
   "message": "No compatible worker is available."
 }
}
```


| HTTP | Stable code | Meaning |
| ---: | --- | --- |
| `400` | `INVALID_REQUEST` | Invalid JSON, fields, counts, timeout, or request ID |
| `400` | `UNSUPPORTED_MODEL` | Unsupported model version |
| `413` | `REQUEST_TOO_LARGE` | Body or UTF-8 byte limit exceeded |
| `429` | `GATEWAY_AT_CAPACITY` | Every eligible worker has 32 reservations |
| `429` | `WORKER_QUEUE_FULL` | Selected worker rejected admission |
| `503` | `NO_HEALTHY_WORKER` | No ready compatible worker |
| `503` | `WORKER_UNAVAILABLE` | Transport failed and retry could not succeed |
| `503` | `SERVICE_DRAINING` | Gateway is shutting down |
| `504` | `DEADLINE_EXCEEDED` | End-to-end deadline expired |
| `500` | `INTERNAL_ERROR` | Unexpected internal failure |


Override FastAPI's default validation response so all errors use this schema. Error
messages are fixed safe text, not exception strings.


## 10. Complete Protobuf Contract


Check in this contract and generated Python files:


```protobuf
syntax = "proto3";


package inference.v1;


service InferenceWorker {
 rpc Predict(PredictRequest) returns (PredictResponse);
 rpc GetStatus(StatusRequest) returns (StatusResponse);
}


message PredictRequest {
 string request_id = 1;
 string model_version = 2;
 repeated string inputs = 3;
}


message Prediction {
 string label = 1;
 double score = 2;
}


message WorkerTiming {
 double queue_ms = 1;
 double preprocess_ms = 2;
 double inference_ms = 3;
 double postprocess_ms = 4;
 double worker_total_ms = 5;
}


message PredictResponse {
 string request_id = 1;
 string model_version = 2;
 string worker_id = 3;
 repeated Prediction predictions = 4;
 WorkerTiming timing = 5;
}


message StatusRequest {}


enum WorkerState {
 WORKER_STATE_UNSPECIFIED = 0;
 WORKER_STATE_STARTING = 1;
 WORKER_STATE_READY = 2;
 WORKER_STATE_DRAINING = 3;
}


message StatusResponse {
 string worker_id = 1;
 string model_version = 2;
 string model_sha256 = 3;
 WorkerState state = 4;
 uint32 queue_depth = 5;
 uint32 queue_capacity = 6;
 uint32 active_batches = 7;
}
```


Generation command:


```bash
python -m grpc_tools.protoc \
 -I proto \
 --python_out=generated \
 --grpc_python_out=generated \
 proto/inference/v1/inference.proto
```


CI reruns generation into a temporary directory and fails if it differs from the
checked-in files.


Generated imports use `inference.v1`, so add both the repository root and
`generated/` to `PYTHONPATH`. Configure the same paths in pytest, mypy, the
Dockerfile, and command-line entry points. Do not edit generated imports manually.


### Worker gRPC Errors


The gRPC status detail contains only the stable code.


| gRPC status | Detail | Gateway behavior |
| --- | --- | --- |
| `INVALID_ARGUMENT` | `INVALID_REQUEST` | HTTP `400` |
| `INVALID_ARGUMENT` | `UNSUPPORTED_MODEL` | HTTP `400` |
| `RESOURCE_EXHAUSTED` | `WORKER_QUEUE_FULL` | HTTP `429`, no retry |
| `FAILED_PRECONDITION` | `WORKER_NOT_READY` | Mark ineligible; HTTP `503` with `WORKER_UNAVAILABLE` |
| `DEADLINE_EXCEEDED` | `DEADLINE_EXCEEDED` | HTTP `504`, no retry |
| `UNAVAILABLE` | `WORKER_UNAVAILABLE` | Mark unhealthy and retry once |
| `INTERNAL` | `INTERNAL_ERROR` | HTTP `500`, no retry |


`CANCELLED` is recorded in metrics and normally produces no HTTP response because
the gateway request task was cancelled.


## 11. Gateway Design


### Registry State


Each configured worker has:


```text
worker_id
address
expected_model_version
expected_model_sha256
health: starting | healthy | unhealthy | draining
outstanding_requests
consecutive_health_failures
consecutive_health_successes
last_successful_health_check
```


### Atomic Scheduling


Protect worker selection, tie-breaking cursor updates, and reservation increments
with one `asyncio.Lock`.


For each attempt:


1. Exclude workers that are not healthy, have the wrong model version, were already
  attempted, or have 32 outstanding reservations.
2. Find the smallest `outstanding_requests` value.
3. Choose from tied workers using a rotating cursor over stable worker-ID order.
4. Increment the chosen worker before releasing the lock.
5. Decrement it in a `finally` block under the same lock.


If compatible healthy workers exist but all are saturated, return
`GATEWAY_AT_CAPACITY`. If none are healthy, return `NO_HEALTHY_WORKER`.


Reported worker queue depth is observable but is not used for initial routing. This
keeps the scheduler deterministic and avoids routing on stale status data.


### Health State Machine


- Poll every worker every second with a 250 ms timeout.
- A starting worker becomes healthy after its first successful compatible status.
- A healthy worker becomes unhealthy after three consecutive failed probes.
- A real `UNAVAILABLE` prediction immediately marks that worker unhealthy.
- An unhealthy worker becomes healthy after two consecutive successful compatible
 probes.
- A `DRAINING` response makes the worker immediately ineligible.
- A successful probe resets failure count; a failed probe resets success count.
- Model-version or checksum mismatch keeps the worker unhealthy and logs a bounded
 reason.
- Health tasks run independently so one slow worker does not delay other probes.


Use a pure transition function and fake clock in unit tests.


### Deadlines


1. After request validation, calculate
  `gateway_deadline = loop.time() + timeout_ms / 1000`.
2. Before every RPC, calculate `remaining = gateway_deadline - loop.time()`.
3. If `remaining <= 0`, return `DEADLINE_EXCEEDED`.
4. Pass `remaining` as the `grpc.aio` call timeout.
5. Never send a monotonic timestamp over the network.
6. The worker derives its own local deadline as
  `loop.time() + context.time_remaining()` at admission.


This preserves an end-to-end budget without assuming process clocks have the same
origin.


### Retry


Retry at most once on a different worker only when:


- the first RPC ends with gRPC `UNAVAILABLE`,
- no HTTP response has been produced,
- at least 50 ms remains,
- another healthy unsaturated worker exists.


Do not retry queue-full, invalid, internal, cancelled, or deadline errors. Prediction
is side-effect-free, so duplicate computation is acceptable if the first worker ran
the request but its response was lost. The response `attempts` field is `2` after a
successful retry.


### Request Cancellation


Gateway shutdown cancels remaining gRPC calls after the 10-second grace period.
The required release does not poll `request.is_disconnected()`. A client that
disconnects may leave work running until the configured deadline; the maximum
10-second timeout bounds that work. Document this limitation.


## 12. Worker and Inference Design


### Startup


1. Verify all model artifact checksums.
2. Load `tokenizer.json`.
3. Configure ONNX Runtime for sequential execution with one intra-op and one
  inter-op thread.
4. Load one `InferenceSession`.
5. Run one warm-up batch.
6. Start the batcher and metrics server.
7. Change state from `STARTING` to `READY`.


Fail startup on a missing artifact, checksum mismatch, unexpected model input/output
names, or failed warm-up.


Expected ONNX inputs are `input_ids`, `attention_mask`, and `token_type_ids`.
Expected output is `logits`.


### Bounded Execution


Each worker owns:


- one `asyncio.Queue` with capacity 64 request envelopes,
- one batcher coroutine,
- one `ThreadPoolExecutor(max_workers=1)`,
- one active inference batch at most.


Never call tokenizer or ONNX Runtime directly on the asyncio event-loop thread.
Submit tokenization, array construction, inference, softmax, and label mapping as one
executor function. The batcher awaits that function before submitting another, so
the executor cannot accumulate an unbounded work queue.


Construct `input_ids`, `attention_mask`, and `token_type_ids` as contiguous NumPy
`int64` arrays. Validate their names against the ONNX session before warm-up.


An envelope contains:


```text
request_id
model_version
raw_inputs
local_deadline
response_future
enqueue_time
```


The gRPC handler:


1. Validates request ID, model version, input count, and byte limits.
2. Rejects with `WORKER_NOT_READY` unless state is `READY`.
3. Derives a local deadline from `context.time_remaining()`.
4. Calls `queue.put_nowait`.
5. Rejects with `WORKER_QUEUE_FULL` if the queue is full.
6. Awaits the envelope future.
7. Cancels that future if its RPC context is cancelled.


### Dynamic Batching


The batcher:


1. Waits for the first envelope.
2. Cancels it if its future is done, or completes it with
  `DEADLINE_EXCEEDED` if its deadline expired.
3. Starts a 5 ms timer.
4. Pulls more envelopes until reaching 8 requests, 32 total inputs, or the timer.
5. Leaves an envelope for the next batch when adding it would exceed 32 inputs.
6. Completes expired envelopes with `DEADLINE_EXCEEDED` and skips cancelled
  envelopes before executor submission.
7. Flattens inputs and records a slice for each request.
8. Tokenizes with truncation at 128 and padding to the longest item in the batch.
9. Runs one ONNX call.
10. Applies numerically stable softmax and chooses the highest-scoring label.
11. Restores each request's original input order.
12. Resolves each still-pending future independently.
13. Calls `queue.task_done()` exactly once for every dequeued envelope.


Because `asyncio.Queue` cannot push an item back to the front, hold one
`next_envelope` variable when an item would exceed the current batch's item limit.
Process it first on the next loop.


When batching is disabled for benchmarks, set `MAX_BATCH_REQUESTS=1` and
`MAX_BATCH_DELAY_MS=0`. Multiple inputs in one request still form one model batch.


If preprocessing or inference raises unexpectedly, fail every live envelope in that
batch with `INTERNAL_ERROR`, log the exception without input text, and keep the
batcher alive. If the ONNX session itself becomes unusable, fail readiness and exit
the worker so Compose can restart it.


### Expiration


- Expired queued requests are failed without inference.
- If a deadline expires during ONNX execution, the call may finish.
- Discard late results and increment `late_results_total`.
- Never claim hard inference cancellation.


## 13. Compose Topology


Define four named services:


- `worker-1`: host gRPC `50051`, metrics `9101`
- `worker-2`: host gRPC `50052`, metrics `9102`
- `worker-3`: host gRPC `50053`, metrics `9103`, profile `four-workers`
- `worker-4`: host gRPC `50054`, metrics `9104`, profile `four-workers`


All workers listen on container ports `50051` and `9100`. The gateway addresses
workers by Compose DNS name and container gRPC port. The gateway exposes HTTP port
`8000`.


`worker-1`, `worker-2`, and `gateway` have no profile, so this starts the default
two-worker stack:


```bash
docker compose up --build -d
```


Start exactly one worker for a benchmark:


```bash
docker compose down
docker compose up --build -d gateway worker-1
```


Start all four:


```bash
docker compose --profile four-workers up --build -d
```


The gateway lists all four static addresses in every mode. Workers that were not
started simply remain unhealthy.


Each worker has `mem_limit: 512m`. Set `cpus: 1.0` only if the local Docker runtime
supports it consistently; otherwise leave CPU unconstrained and record that fact in
benchmark metadata. Do not use Compose replica scaling.


## 14. Liveness, Readiness, and Shutdown


### Gateway Endpoints


- `GET /health/live`: `200` while the process event loop is responsive.
- `GET /health/ready`: `200` only while accepting requests and at least one
 compatible worker is healthy; otherwise `503`.
- `GET /metrics`: Prometheus text format.


### Worker Status


Workers expose status through `GetStatus`, not HTTP. Their separate metrics HTTP
server serves `/metrics` on port `9100`.


### Gateway Shutdown


1. FastAPI lifespan shutdown sets `accepting=false`.
2. Readiness becomes false and new predictions return `SERVICE_DRAINING`.
3. Wait up to 10 seconds for active HTTP handlers.
4. Cancel remaining handler and gRPC tasks.
5. Close all gRPC channels and health tasks.


### Worker Shutdown


1. Signal handling changes state to `DRAINING`.
2. New `Predict` calls fail with `WORKER_NOT_READY`; `GetStatus` still works.
3. Wait for `queue.join()` and the active batch for up to 10 seconds.
4. Fail all remaining queued futures with `WORKER_UNAVAILABLE`.
5. Cancel the batcher and stop the gRPC server.
6. If inference completed, shut down the executor normally. If it exceeded the
  grace period, call `shutdown(wait=False, cancel_futures=True)` and allow Docker's
  15-second stop timeout to terminate the process.


Unit tests assert that every accepted future is completed, failed, or cancelled.
The Compose test uses `docker stop --time 15`.


## 15. Observability


Use seconds for Prometheus durations and milliseconds in API responses and raw
benchmark records.


### Gateway Metrics


- `gateway_requests_total{status_code,error_code}`
- `gateway_request_duration_seconds`
- `gateway_active_requests`
- `gateway_routing_total{worker_id}`
- `gateway_retries_total{result}`
- `gateway_rpc_failures_total{worker_id,grpc_code}`
- `gateway_worker_outstanding{worker_id}`
- `gateway_worker_healthy{worker_id}`


### Worker Metrics


- `worker_requests_total{result}`
- `worker_queue_depth`
- `worker_queue_wait_seconds`
- `worker_batch_requests`
- `worker_batch_items`
- `worker_preprocess_seconds`
- `worker_inference_seconds`
- `worker_active_batches`
- `worker_expired_requests_total{stage}`
- `worker_late_results_total`
- `worker_model_info{worker_id,model_version,model_sha256}` with value `1`


Use fixed histogram buckets appropriate for laptop inference:


```text
0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10
```


Metric labels are fixed enums or configured worker IDs. Never use request IDs,
addresses, exception text, or input text as labels.


### Logs


Emit one JSON object per line. Allowed fields:


```text
timestamp
level
service
event
request_id
worker_id
model_version
attempt
error_code
duration_ms
queue_depth
batch_requests
batch_items
```


Raw inputs, tokens, predictions, stack traces in client responses, and arbitrary
exception strings are forbidden. Server logs may include an exception class and a
stack trace only after confirming it contains no request data; omit the exception
message.


## 16. Test Plan


### Unit Tests


Use fake clocks, fake workers, and a fake model backend.


- Every request-validation boundary and one value beyond it
- Request-ID generation and validation
- Atomic least-outstanding scheduling and deterministic tie rotation
- Reservation release after success, error, timeout, retry, and cancellation
- Starting, unhealthy, recovery, draining, and mismatch transitions
- Retry only for `UNAVAILABLE`, only once, and only with 50 ms remaining
- Remaining deadline budget decreases between attempts
- Queue admission at capacity 63, 64, and 65
- Batch request, item, and 5 ms timer limits
- Deferred `next_envelope` behavior at the 32-item limit
- Expired and cancelled queue entries
- Input and prediction order restoration
- Stable softmax and label mapping
- Executor failure resolves all batch futures
- Shutdown resolves every accepted future
- Metric counters match known events


### Integration Tests


Run real `grpc.aio` servers on ephemeral ports with a fake model unless a test is
explicitly marked `real_model`.


- One gRPC prediction succeeds.
- Concurrent requests form a batch.
- Queue-full maps to `RESOURCE_EXHAUSTED`.
- Deadline expiration maps to `DEADLINE_EXCEEDED`.
- Gateway routes traffic across two workers.
- Saturated workers are excluded atomically.
- `UNAVAILABLE` retries on a different worker exactly once.
- An unhealthy worker receives no new requests.
- A recovered worker returns after two probes.
- Shutdown drains accepted work within the grace period.
- Sentinel input text does not appear in captured logs.
- One `real_model` test verifies positive and negative fixtures.


### Compose End-to-End Test


The script performs these exact steps:


1. Download and verify artifacts.
2. Start the default stack and poll gateway readiness for up to 60 seconds.
3. Verify one deterministic two-input prediction.
4. Send 100 requests at concurrency 16 and require every response to be terminal.
5. Stop `worker-1`.
6. Wait until its health metric becomes `0`.
7. Send 50 requests and verify `worker-1` receives none after ejection.
8. Start `worker-1`.
9. Wait until it becomes healthy after two probes.
10. Verify it receives traffic again.
11. Run a 10-second saturation test and observe at least one success plus bounded
   `429` or `504` errors.
12. Scan container logs for a unique sentinel input and fail if found.
13. Stop the stack with a 15-second timeout.


Tests must not require exact scheduling counts or exact latency.


### CI


GitHub Actions on Python 3.12:


1. Install exact dependencies.
2. Run Ruff.
3. Run mypy.
4. Verify generated Protobuf files.
5. Run unit and integration tests.
6. Cache and verify the 18 MB model artifacts.
7. Run the two-input real-model smoke test.
8. Build the Docker image.


Keep the full Compose failure test and performance benchmarks as documented local
commands rather than required CI jobs.


## 17. Benchmark Plan


### Harness


Use one Python `httpx.AsyncClient` process on the host. The workload is closed-loop:
each client task sends its next request only after the previous request finishes.
This is simpler to implement but does not measure fixed arrival-rate behavior.
Document that limitation.


Use a committed, seeded corpus of 1,000 entries:


- 60% short inputs, approximately 8-16 tokens
- 30% medium inputs, approximately 32-64 tokens
- 10% long inputs, approximately 96-128 tokens


Generate the corpus once from public-domain or synthetic text, inspect it for
sensitive content, and commit it. Every comparison uses the same corpus order and
seed.


Each request record is one NDJSON line:


```json
{
 "trial_id": "scaling-w2-c32-t1",
 "request_index": 42,
 "started_ns": 123,
 "duration_ms": 11.7,
 "http_status": 200,
 "error_code": null,
 "worker_id": "worker-2",
 "attempts": 1,
 "input_count": 1,
 "queue_ms": 2.1,
 "inference_ms": 6.8
}
```


Do not store input text in benchmark output.


`sample_resources.py` runs `docker stats --no-stream` once per second and writes:


```text
timestamp,container,cpu_percent,memory_bytes,memory_limit_bytes
```


### Trial Protocol


For every configuration:


1. Recreate the stack.
2. Wait for readiness.
3. Warm up for 15 seconds at the trial concurrency.
4. Run a 60-second measured trial.
5. Save request NDJSON, resource CSV, configuration JSON, and service metrics.
6. Repeat three times.


The configuration JSON records:


- Git commit
- UTC timestamp
- OS and CPU
- Docker version and allocated CPU/memory
- Python, ONNX Runtime, and model hashes
- worker count
- ONNX thread settings
- queue and batch settings
- corpus hash and seed
- concurrency, warm-up, duration, and trial number


### Required Experiments


| Experiment | Configurations |
| --- | --- |
| Worker scaling | 1, 2, and 4 workers; batching enabled; concurrency 32 |
| Batching | 2 workers; batching disabled and enabled; concurrency 32 |
| Saturation | 2 workers; batching enabled; concurrency 32, 64, and 128 |
| Failure recovery | 2 workers; concurrency 32; 90 seconds; stop worker 1 at second 30 and restart it at second 60 |
| Sustained overload | 2 workers; concurrency 128; 120 seconds after warm-up |


The enabled two-worker concurrency-32 trial is shared by three experiment rows.
After reusing it, this is six unique ordinary configurations plus two special
configurations, not a large combinatorial matrix.


### Summaries


For each trial report:


- attempted throughput: all completed responses divided by measured seconds
- successful throughput: HTTP `200` responses divided by measured seconds
- p50, p95, and p99 successful-request latency using nearest-rank percentiles
- count and percentage by HTTP status and stable error code
- retry count
- requests served per worker
- p50 and p95 queue and inference time
- batch-request and batch-item distributions from worker metrics
- average CPU and peak container memory


For each configuration report the median of the three trial values and the observed
minimum and maximum. Never combine failed-request latency with successful latency.


For failure recovery, additionally report:


- failures during the stop and recovery interval
- time from container stop to health ejection
- time from restart to health restoration
- successful throughput before, during, and after failure


For sustained overload, boundedness passes when:


- worker queue depth never exceeds 64,
- every request receives a terminal result,
- containers remain below the 512 MB limit,
- median total worker memory in the final 30 seconds is no more than
 `max(32 MiB, 20%)` above the first 30-second median after warm-up.


If the memory criterion fails, report the failure and investigate before making a
bounded-memory resume claim.


## 18. Milestone Plan


The milestones below are ordered from easiest to hardest. The simplest path is to
finish Milestones 0-2 yourself, then hand off Milestones 3-5 to agents if you
want help with the more complex scheduling, retry, Compose, and benchmark work.


### Milestone 0: Project Skeleton and Contracts


Goal: make the repository buildable and make the public contract explicit.


- Create the repository layout and exact dependency files.
- Add the Protobuf contract and generated Python code.
- Add the artifact download and checksum verification script.
- Add a tiny synchronous model wrapper and the first fixture tests.


Gate: the checked-in model fixtures load and predict deterministically.


### Milestone 1: Single-Worker Core


Goal: make one worker process requests safely before adding distributed routing.


- Implement worker configuration and startup.
- Add the bounded queue, single inference executor, and batcher.
- Implement `Predict` and `GetStatus`.
- Add worker metrics and unit tests around queue limits, batching, and deadlines.


Gate: concurrent requests batch, preserve order, reject overload, and honor
deadlines in one worker.


### Milestone 2: Gateway MVP


Goal: expose the HTTP API and send traffic to the worker through gRPC.


- Implement request validation, body limits, and response schemas.
- Add the registry, scheduler, gRPC client, and deadline propagation.
- Add health polling and one retry.
- Add gateway metrics and a default two-worker Compose stack.


Gate: HTTP traffic reaches both workers and survives one worker stopping.


### Milestone 3: Shutdown and Failure Semantics


Goal: make failure handling explicit and testable.


- Implement gateway and worker draining.
- Complete gRPC-to-HTTP error mapping.
- Test health ejection, restoration, retries, and shutdown.
- Add structured logging and redaction tests.


Gate: reliability integration tests pass without unresolved futures.


### Milestone 4: End-to-End Checks


Goal: prove the documented setup works from a clean checkout.


- Implement the Compose end-to-end script.
- Add a local failure scenario.
- Complete Ruff, mypy, test, generation, and image CI checks.
- Verify clean-checkout instructions.


Gate: the documented setup works from a clean checkout.


### Milestone 5: Benchmarks and Evidence


Goal: collect the reproducible evidence needed for the final release.


- Commit the seeded corpus.
- Implement request, resource, and configuration capture.
- Implement deterministic summary generation.
- Run the required trial matrix and preserve raw results.
- Write architecture, reliability, limitations, and benchmark documents.


Gate: every potential resume statement has code, tests, and reproducible evidence.


## 19. Exact User Workflow


The final README exposes these commands through the Makefile:


```bash
make setup          # create a Python 3.12 venv, install dependencies, verify model
make proto          # regenerate Protobuf files
make test           # unit and integration tests
make lint           # Ruff and mypy
make up             # default gateway plus two workers
make smoke          # readiness and prediction smoke test
make e2e            # local Compose failure and recovery test
make benchmark      # required benchmark configurations
make report         # regenerate reports from raw results
make down           # graceful Compose shutdown
```


`make setup` must call `python3.12 -m venv .venv` explicitly rather than `python3`.
It downloads Python dependencies and model files. The first Docker build may also
pull its pinned Python base image. After those two operations, ordinary service
startup and tests use the local artifacts and images.


## 20. Evidence and Resume Gate


Preserve:


- architecture and API documentation
- Protobuf source and generated-code check
- exact dependency files
- model cards, revisions, license declarations, and checksums
- unit, integration, end-to-end, and CI results
- benchmark corpus and its hash
- benchmark configurations, request-level raw output, and resource samples
- generated reports
- failure and recovery logs without input text
- environment and hardware description


Before listing the project:


- All required features and tests exist.
- Setup is reproducible from a clean checkout.
- At least two workers communicate over gRPC.
- Inputs, queues, batches, concurrency, retries, and deadlines are bounded.
- Worker failure and recovery tests pass.
- Sustained-overload evidence meets or honestly rejects the memory criterion.
- Logs and metric labels do not expose input text.
- Resume metrics recalculate from saved evidence.
- Sahas can explain batching, routing, deadlines, retries, backpressure, health,
 failure semantics, model limitations, and benchmark limitations.


## 21. Interview Questions


- Why use HTTP externally and gRPC internally?
- Why are static workers enough for this release?
- Why use least-outstanding-request routing?
- Why is scheduler reservation atomic?
- How does batching trade latency for throughput?
- Why are both request count and flattened batch items bounded?
- Why does ONNX inference run in a dedicated executor?
- How is a deadline transferred without sharing monotonic timestamps?
- Which failures are retried, and why can duplicate computation occur?
- What happens when a deadline expires during queueing or inference?
- How does the gateway distinguish overload from unavailability?
- What did the failure benchmark show?
- Why is the load generator's closed-loop design a limitation?
- Why are local containers not a multi-host cluster?
- What bottleneck appeared first, and what evidence demonstrates it?


## 22. Future Resume Bullet Shapes


Use only after replacing every marker with reproduced evidence:


- Built a local distributed inference service using FastAPI, gRPC, Protobuf, and
 ONNX Runtime, routing requests across [VERIFY] workers with deadline-aware health
 checks and load balancing.
- Implemented bounded dynamic batching, load shedding, retry, and graceful worker
 recovery, sustaining [VERIFY] requests per second at [VERIFY] ms p99 latency.
- Measured [VERIFY]x throughput scaling from one to [VERIFY] workers while limiting
 peak memory to [VERIFY] MB under sustained overload through reproducible Docker
 Compose benchmarks.


If scaling is weak, write bullets around the truthful reliability and measurement
results instead of forcing a speedup claim.





