# Bounded concurrent import and AI request admission

RepoPilot is a trusted, loopback-only developer tool, not a public,
authenticated, multi-tenant application. Request-size and persistent-storage
quotas alone do not limit how many expensive requests are executing at once.

## Enforced admission

| API operations | Config variable | Default | Accepted values |
| --- | --- | ---: | --- |
| POST /api/upload and /api/analyze | REPOPILOT_MAX_INFLIGHT_IMPORTS | 1 | 1–16 |
| POST /api/ask and /api/architecture | REPOPILOT_MAX_INFLIGHT_AI | 2 | 1–16 |

Requests that cannot obtain a slot immediately return HTTP **503**, a generic
busy response, and **Retry-After: 1**. They do not wait in an unbounded
application queue. An occupied import slot rejects another upload **before**
its body is parsed or spooled. AI and import pools are independent; health
and ordinary repository reads remain accessible under saturation. Invalid
slot settings fail closed with generic HTTP 503 responses.

Slots are file locks beside the configured repository import store, with one
lock file per permitted slot. Workers sharing **the same filesystem and
import store path** coordinate admission across threads and separate
processes. The lock is held from the start of the HTTP operation until the
ASGI response is finished; it is released on success or exception. Do not
remove active lock files while workers are running.

## Reproduce

Install backend test requirements, then run:

    PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_work_admission.py -v
    PYTHONPATH=backend python -m unittest discover -s backend/tests -v

The real FastAPI ASGI tests exercise admission exhaustion, reuse after
completion or failure, early upload refusal without reading its body, two
parallel AI slots followed by a rejected third request, independence of import
and AI pools, health responsiveness, invalid configuration, the loopback
boundary, and a **separate process** holding a file lock and releasing it.

## What this does not enforce

- These are **request concurrency** limits, not quotas for CPU seconds, peak
  process memory, filesystem blocks, or network bytes. In particular, a
  single admitted Git clone or model request can still exhaust resources.
- A worker that is killed while child processes remain alive may release its
  file lock before those children have stopped. Other worker-level supervision
  and process-group cleanup remain necessary.
- Independent servers using different import-store paths, or filesystems
  without reliable interprocess file locks, do not share an admission budget.
- Search requests and ordinary reads are **not** admitted through these
  two pools; this change does not cap every possible expensive operation.
- File lock files persist when idle and should not be deleted while servers
  run. Do not use this as a production multi-tenant scheduling service.

For publicly reachable deployments, enforce identity and authorization,
reverse-proxy connection/rate limits, cgroup/container worker isolation,
filesystem quotas, job timeouts and monitoring. Passing tests and CodeQL do
not substitute for external review.
