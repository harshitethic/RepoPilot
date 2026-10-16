from pathlib import Path
import tempfile
import logging
from fastapi import APIRouter, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool
from services.github import extract_zip, rollback_import
from services.analyzer import analyze

router = APIRouter()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024


async def write_temp_upload(file: UploadFile) -> Path:
    """Stream uploads into an OS-created temp file with a strict size cap."""
    path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="repopilot-", suffix=".zip", delete=False
        ) as staging:
            path = Path(staging.name)
            total = 0
            while True:
                chunk = await file.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise ValueError("ZIP is too large. Maximum upload size is 50 MB.")
                staging.write(chunk)
        return path
    except Exception:
        if path is not None:
            path.unlink(missing_ok=True)
        raise


@router.post("/api/upload")
async def upload_repository(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Upload a .zip repository archive.")
    temp = None
    repo_id = None
    path = None
    completed = False
    try:
        temp = await write_temp_upload(file)
        # Avoid blocking the ASGI event loop during archive extraction,
        # cross-process quota lock waits, or repository analysis.
        repo_id, path = await run_in_threadpool(extract_zip, temp)
        result = await run_in_threadpool(analyze, path)
        result.update(repo_id=repo_id, source_url=f"ZIP: {file.filename}")
        completed = True
        return result
    except ValueError as exc:
        if repo_id is not None:
            logging.exception("ZIP analysis failed after successful extraction")
            raise HTTPException(500, "Could not analyze the uploaded ZIP.") from exc
        # Whitelist an exact validation message rather than returning
        # arbitrary ValueError content from parsers or configuration.
        if str(exc) == "ZIP is too large. Maximum upload size is 50 MB.":
            raise HTTPException(400, "ZIP is too large. Maximum upload size is 50 MB.") from exc
        raise HTTPException(400, "Invalid ZIP archive or import capacity reached.") from exc
    except Exception as exc:
        logging.exception("Repository ZIP analysis failed")
        raise HTTPException(500, "Could not analyze the uploaded ZIP.") from exc
    finally:
        if repo_id is not None and path is not None and not completed:
            try:
                await run_in_threadpool(rollback_import, repo_id, path)
            except Exception:
                logging.exception("Unable to roll back failed ZIP analysis")
        if temp is not None:
            temp.unlink(missing_ok=True)
