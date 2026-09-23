import tempfile
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from services.github import extract_zip
from services.analyzer import analyze

router = APIRouter()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024


async def write_temp_upload(file: UploadFile) -> Path:
    path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="repopilot-",
            suffix=".zip",
            delete=False,
        ) as handle:
            path = Path(handle.name)
            total = 0
            while True:
                chunk = await file.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise ValueError(
                        "ZIP is too large. Maximum upload size is 50 MB."
                    )
                handle.write(chunk)
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
    try:
        temp = await write_temp_upload(file)
        repo_id, path = extract_zip(temp)
        result = analyze(path)
        result.update(repo_id=repo_id, source_url=f"ZIP: {file.filename}")
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Could not analyze ZIP: {e}")
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
