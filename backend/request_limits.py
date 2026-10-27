"""Bound incoming API bodies *before* FastAPI multipart or JSON parsing.

Content-Length is only an early hint; missing/lying lengths are handled by
streaming bytes into a disk-backed, size-limited temporary spool before route
dispatch. This is not a hard CPU/peak-disk/concurrent-request or network quota.
"""
import tempfile

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from api_upload import MAX_UPLOAD_BYTES

# Allow normal multipart framing on top of the 50-MiB ZIP file limit.
MAX_MULTIPART_BODY_BYTES = MAX_UPLOAD_BYTES + 64 * 1024
MAX_JSON_BODY_BYTES = 64 * 1024
SPOOL_MEMORY_BYTES = 1024 * 1024
REPLAY_CHUNK_BYTES = 256 * 1024


class RequestBodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        method = scope.get("method", "GET")
        path = scope.get("path", "")
        if method not in {"POST", "PUT", "PATCH"} or not path.startswith("/api/"):
            return await self.app(scope, receive, send)

        limit = (
            MAX_MULTIPART_BODY_BYTES if path.rstrip("/") == "/api/upload"
            else MAX_JSON_BODY_BYTES
        )
        lengths = [
            value for key, value in scope.get("headers", [])
            if key.lower() == b"content-length"
        ]
        if lengths:
            if (
                len(lengths) != 1
                or len(lengths[0]) > 20
                or not lengths[0].isascii()
                or not lengths[0].isdigit()
            ):
                return await self._reject(scope, receive, send, 400, "Invalid Content-Length.")
            if int(lengths[0]) > limit:
                return await self._reject(scope, receive, send, 413, "Request body too large.")

        with tempfile.SpooledTemporaryFile(max_size=SPOOL_MEMORY_BYTES, mode="w+b") as staged:
            used = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                if message["type"] != "http.request":
                    continue
                data = message.get("body", b"")
                used += len(data)
                if used > limit:
                    return await self._reject(scope, receive, send, 413, "Request body too large.")
                if data:
                    await run_in_threadpool(staged.write, data)
                if not message.get("more_body", False):
                    break

            await run_in_threadpool(staged.seek, 0)
            remaining = used
            delivered_end = False

            async def replay_receive():
                nonlocal remaining, delivered_end
                if remaining:
                    size = min(remaining, REPLAY_CHUNK_BYTES)
                    data = await run_in_threadpool(staged.read, size)
                    if not data:
                        raise RuntimeError("Incomplete buffered request body")
                    remaining -= len(data)
                    delivered_end = remaining == 0
                    return {
                        "type": "http.request",
                        "body": data,
                        "more_body": not delivered_end,
                    }
                if not delivered_end:
                    delivered_end = True
                    return {"type": "http.request", "body": b"", "more_body": False}
                return await receive()

            await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(scope, receive, send, status, detail):
        await JSONResponse({"detail": detail}, status_code=status)(
            scope, receive, send
        )
