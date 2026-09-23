import tempfile
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from services.github import extract_zip
from services.analyzer import analyze

router = APIRouter()


def write_temp_upload(data: bytes) -> Path:
    with tempfile.NamedTemporaryFile(
        prefix="repopilot-",
        suffix=".zip",
        delete=False,
    ) as handle:
        handle.write(data)
        return Path(handle.name)


@router.post("/api/upload")
async def upload_repository(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Upload a .zip repository archive.")
    temp = None
    try:
        data = await file.read(50 * 1024 * 1024 + 1)
        if len(data) > 50 * 1024 * 1024:
            raise ValueError("ZIP is too large. Maximum upload size is 50 MB.")
        temp = write_temp_upload(data)
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
