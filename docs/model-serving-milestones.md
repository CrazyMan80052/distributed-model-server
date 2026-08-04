# Model Serving Milestones

This file splits the work into two tracks:

- `You build this`: the parts that are good for learning the codebase and understanding the core flow.
- `Agent-friendly follow-up`: the parts that are more mechanical, more error-prone, or more time-consuming to harden.

The goal is to get a simple, working slice early, then hand off the harder distributed and benchmarking work later if you want.

## You Build This

### Milestone 0: Skeleton and Contract

Focus:

- Create the repository layout and dependency files.
- Add the Protobuf contract and generated Python code.
- Add the model download and checksum verification script.
- Add a small synchronous model wrapper.
- Add fake model and fake clock test helpers.

Why this first:

- It makes the public shape of the system visible.
- It gives you fast feedback without networking or concurrency complexity.

Gate:

- The checked-in model fixtures load and predict deterministically.

### Milestone 1: Single-Worker Core

Focus:

- Implement worker configuration and startup.
- Add the bounded queue.
- Add one inference executor.
- Add the batcher.
- Implement `Predict` and `GetStatus`.
- Add unit tests for queue limits, batching, and deadlines.

Why this first:

- You learn the core request path before adding routing.
- You can test most of it with fake workers and a fake clock.

Gate:

- Concurrent requests batch, preserve order, reject overload, and honor deadlines in one worker.

### Milestone 2: Gateway MVP

Focus:

- Implement request validation, body limits, and response schemas.
- Add the registry, scheduler, gRPC client, and deadline propagation.
- Add gateway metrics.
- Add a default two-worker Compose stack.

Why this is still manageable:

- It introduces distributed traffic, but the control flow stays narrow.
- The HTTP API and worker RPCs are both visible and testable.

Gate:

- HTTP traffic reaches both workers and survives one worker stopping.

## Agent-Friendly Follow-Up

### Milestone 3: Shutdown and Failure Semantics

Best left to an agent if you want to avoid spending too much time on edge cases.

Focus:

- Implement gateway and worker draining.
- Complete gRPC-to-HTTP error mapping.
- Test health ejection, restoration, retries, and shutdown.
- Add structured logging and redaction tests.

Gate:

- Reliability integration tests pass without unresolved futures.

### Milestone 4: End-to-End Checks

This is good agent work because it is mostly wiring, automation, and validation.

Focus:

- Implement the Compose end-to-end script.
- Add a local failure scenario.
- Complete Ruff, mypy, test, generation, and image CI checks.
- Verify clean-checkout instructions.

Gate:

- The documented setup works from a clean checkout.

### Milestone 5: Benchmarks and Evidence

This is the most time-consuming part and is usually easiest to delegate once the core system works.

Focus:

- Commit the seeded corpus.
- Implement request, resource, and configuration capture.
- Implement deterministic summary generation.
- Run the required trial matrix and preserve raw results.
- Write architecture, reliability, limitations, and benchmark documents.

Gate:

- Every potential resume statement has code, tests, and reproducible evidence.

## Suggested Ownership Split

If you want the most learning per hour, a practical split is:

- You: Milestones 0-2.
- Agent: Milestones 3-5.

If you want, you can also do Milestone 2 yourself and hand off only the retry, shutdown, CI, and benchmark work.
