# Request-body admission before multipart parsing

RepoPilot is an **unauthenticated, loopback-only local developer tool**. Its
ZIP endpoint previously bounded uploaded file bytes only after FastAPI had
already parsed and spooled the multipart body. An oversized or chunked request
could consume substantial temporary disk before reaching that check.

## Applied limits

| Route | Maximum request-body bytes |
| --- | ---: |
| POST /api/upload | 50 MiB + 64 KiB multipart framing allowance |
| Other /api/ POST, PUT, PATCH routes | 64 KiB |

The existing ZIP *file* limit remains 50 MiB. Normal multipart framing
accounts for the additional 64 KiB; requests with excessive form fields or
multipart headers are rejected as well.

The ASGI middleware:

1. Rejects declared Content-Length over budget with HTTP **413** without
   reading or invoking the endpoint. Malformed, duplicate, or excessively
   long values receive HTTP **400**.
2. For missing, falsified, or stream-encoded lengths, counts actual ASGI
   request bytes **before** invoking the multipart/JSON parser.
3. Spools bodies within the budget into a temporary binary file, keeping no
   more than 1 MiB in the spool's own memory before spilling to temporary
   disk. Replays the accepted body to the normal FastAPI route in 256 KiB
   chunks. The spool is closed on success, early rejection, and error.
4. Preserves the existing real-client-IP loopback boundary. Remote peers
   continue to receive HTTP **403**, not access to the import route.

This is **not** a hard bound on the number of concurrent requests, network
ingress, server buffering, memory outside the spool, filesystem block usage,
thread/process count, or CPU usage. The ASGI server may already have buffered
one incoming chunk before the middleware examines it. Valid uploads temporarily
use both the request spool and FastAPI's multipart spool; the full end-to-end
temporary disk footprint is higher than the request body cap. Reverse proxies
must still enforce their own size and authentication policies.

## Reproduce

From the project root after installing backend/requirements-test.txt:

    PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_request_body_limits.py -v
    PYTHONPATH=backend python -m unittest discover -s backend/tests -v

The regression scenarios use the real FastAPI ASGI application, disposable
ZIP imports, and synthetic streams. They check oversized declared lengths
without consuming a stream, missing/false lengths, exact-limit acceptance,
malformed headers, actual chunked multipart parsing, spool rollovers and
cleanup, JSON payload caps, and the local-only access policy. No paid service,
real user repository, or network connection is required.

## Remaining work for public deployment

Do not expose RepoPilot as a public, multi-user API. Use an authenticating
reverse proxy with request-size and concurrent-connection caps, filesystem
quotas for temp and repository storage, isolated workers, CPU/memory limits,
rate limiting and monitoring. A passing CodeQL scan is not proof of security.
