# Distributed Model Server

Distributed Model Server is a small local-first inference system for serving a machine learning model through a gateway and multiple worker processes. It is designed to demonstrate how a simple distributed serving stack can route requests, batch work, expose health and metrics endpoints, and support basic benchmarking for local development and evaluation.

## Quick start

Requirements:
- Python 3.12+
- Docker Compose

```bash
make setup
make up
```

Once the services are up, the gateway should be available at http://localhost:8000.

```bash
curl http://localhost:8000/health/ready
```

## Common commands

The repository exposes the following helpers through Make:

```bash
make setup      # create the virtualenv, install deps, and download the model
make proto      # regenerate gRPC bindings from proto/inference/v1/inference.proto
make test       # run the test suite
make lint       # run ruff and mypy
make up         # start the gateway and workers with docker compose
make smoke      # check that the gateway is ready
make e2e        # run the failure-scenario script
make benchmark  # run the default benchmark workload
make report     # generate a markdown benchmark report
make down       # stop and remove the compose services
```

## Benchmarking

A simple benchmark workflow is included for local performance checks:

```bash
make up
source .venv/bin/activate
python scripts/benchmark.py --concurrency 8 --duration 10 --warmup 3 --trial-id local-trial --output benchmarks/raw/local-trial.ndjson
python scripts/summarize_results.py --ndjson benchmarks/raw/local-trial.ndjson --output benchmarks/reports/local-trial-report.md
```

Example local results from a recent run:
- Total requests: 3663 over 10.0s
- Successful throughput: 366.43 req/s
- Latency: p50 20.21 ms, p95 34.69 ms, p99 45.56 ms

These values are intended as a local baseline and may vary by machine and container resources.
