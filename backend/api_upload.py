from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from services.github import extract_zip
from services.analyzer import analyze

router = APIRouter()

@router.post("/api/upload")
async def upload_repository(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Upload a .zip repository archive.")
    temp = Path("/tmp") / f"repopilot-{Path(file.filename).name}"
    try:
        data = await file.read(50 * 1024 * 1024 + 1)
        temp.write_bytes(data)
        if len(data) > 50 * 1024 * 1024:
            raise ValueError("ZIP is too large. Maximum upload size is 50 MB.")
        repo_id, path = extract_zip(temp)
        result = analyze(path)
        result.update(repo_id=repo_id, source_url=f"ZIP: {file.filename}")
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Could not analyze ZIP: {e}")
    finally:
        temp.unlink(missing_ok=True)
