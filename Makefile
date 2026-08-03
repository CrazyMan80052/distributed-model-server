.PHONY: setup proto test lint up smoke e2e benchmark report down

setup:
	python3.12 -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	.venv/bin/python scripts/download_model.py

proto:
	.venv/bin/python -m grpc_tools.protoc -I proto --python_out=generated --grpc_python_out=generated proto/inference/v1/inference.proto

test:
	.venv/bin/pytest tests/

lint:
	.venv/bin/ruff check .
	.venv/bin/mypy gateway worker shared

up:
	docker compose up --build -d

smoke:
	.venv/bin/python -c "import urllib.request, json; resp=urllib.request.urlopen('http://localhost:8000/health/ready'); print(resp.read().decode())"

e2e:
	.venv/bin/python scripts/failure_scenario.py

benchmark:
	.venv/bin/python scripts/benchmark.py --concurrency 32 --duration 15 --trial-id trial-1 --output benchmarks/raw/trial-1.ndjson

report:
	.venv/bin/python scripts/summarize_results.py --ndjson benchmarks/raw/trial-1.ndjson --output benchmarks/reports/trial-1-report.md

down:
	docker compose down
