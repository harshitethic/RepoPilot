"""Cross-process, fail-fast work admission for expensive local API operations.

Separate import and AI slot pools are backed by file locks placed beside the
configured import store. This bounds *active admitted requests* across local
workers that share the filesystem, not CPU/RAM/disk per worker.
"""
import logging
import os
from pathlib import Path

from filelock import FileLock, Timeout
from starlette.responses import JSONResponse

from services import github

logger = logging.getLogger(__name__)
MAX_SLOT_COUNT = 16
DEFAULT_IMPORT_SLOTS = 1
DEFAULT_AI_SLOTS = 2

ROUTES = {
    ("POST", "/api/upload"): "import",
    ("POST", "/api/analyze"): "import",
    ("POST", "/api/ask"): "ai",
    ("POST", "/api/architecture"): "ai",
}


def slot_count(kind: str) -> int:
    default, key = (
        (DEFAULT_IMPORT_SLOTS, "REPOPILOT_MAX_INFLIGHT_IMPORTS")
        if kind == "import"
        else (DEFAULT_AI_SLOTS, "REPOPILOT_MAX_INFLIGHT_AI")
    )
    raw = os.getenv(key, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if not 1 <= value <= MAX_SLOT_COUNT:
        raise ValueError(f"{key} must be from 1 to {MAX_SLOT_COUNT}")
    return value


def slot_path(kind: str, slot: int) -> Path:
    if kind not in {"import", "ai"} or not 0 <= slot < MAX_SLOT_COUNT:
        raise ValueError("Invalid resource admission slot.")
    root = github.BASE_DIR
    return root.parent / f".{root.name}.work-{kind}-{slot}.lock"


def take_slot(kind: str):
    """Return a held FileLock or None if every configured slot is occupied."""
    for index in range(slot_count(kind)):
        lock = FileLock(str(slot_path(kind, index)), timeout=0)
        try:
            lock.acquire(timeout=0)
        except Timeout:
            continue
        return lock
    return None


class WorkAdmissionMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        kind = ROUTES.get((scope.get("method"), scope.get("path")))
        if kind is None:
            return await self.app(scope, receive, send)

        try:
            held = take_slot(kind)
        except (OSError, ValueError):
            logger.warning("Resource admission configuration or lock unavailable")
            return await JSONResponse(
                {"detail": "Resource admission unavailable"}, status_code=503,
                headers={"Retry-After": "1"}
            )(scope, receive, send)

        if held is None:
            return await JSONResponse(
                {"detail": "Server busy. Retry shortly."}, status_code=503,
                headers={"Retry-After": "1"}
            )(scope, receive, send)

        try:
            return await self.app(scope, receive, send)
        finally:
            held.release()
