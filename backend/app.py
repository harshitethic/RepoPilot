import ipaddress
import logging
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
from services.github import clone_repo,safe_repo_path,list_repositories,delete_repository,cleanup_repositories
from services.analyzer import analyze,search_code,build_context
from services.ollama import available,chat
from api_upload import router as upload_router
logger = logging.getLogger(__name__)
app=FastAPI(title="RepoPilot API")


def is_loopback_client(host: str | None) -> bool:
    """Require an actual local TCP peer, never a claimed proxy header."""
    if not host:
        return False
    try:
        address = ipaddress.ip_address(host)
        # IPv4-mapped IPv6 may otherwise be treated differently by stacks.
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            return address.ipv4_mapped.is_loopback
        return address.is_loopback
    except ValueError:
        return False


@app.middleware("http")
async def local_only_by_default(request: Request, call_next):
    # X-Forwarded-For and Host are untrusted, so only the actual ASGI peer
    # address is used. A reverse proxy on the same machine appears local;
    # operators must not expose one without authentication of their own.
    host = request.client.host if request.client else None
    if not is_loopback_client(host):
        return JSONResponse(status_code=403, content={"detail": "Local API only"})
    return await call_next(request)
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],allow_methods=["*"],allow_headers=["*"])
app.include_router(upload_router)
class Analyze(BaseModel): url:str=Field(min_length=10,max_length=500)
class RepoReq(BaseModel): repo_id:str
class Ask(RepoReq): question:str=Field(min_length=3,max_length=1200)
class Search(RepoReq): query:str=Field(min_length=1,max_length=100)
class Cleanup(BaseModel):
    max_age_hours:int=Field(default=24,ge=1,le=720)
    dry_run:bool=True
@app.get("/api/health")
def health():
    # The API itself may be healthy even when optional local Ollama is offline.
    try:
        response = available()
        if not isinstance(response, dict) or type(response.get("online")) is not bool:
            logger.warning("Invalid local AI availability response")
            model_status = {"online": False, "models": []}
        else:
            # Report structured health without reflecting raw exception text,
            # URLs, or internal diagnostics from local model probes.
            model_status = {"online": response["online"], "models": response.get("models", [])}
            if isinstance(response.get("selected"), str):
                model_status["selected"] = response["selected"]
    except Exception:
        logger.warning("Local AI availability probe failed")
        model_status = {"online": False, "models": []}
    return {"ok": True, "ollama": model_status}
@app.post("/api/analyze")
def do_analyze(x: Analyze):
    try:
        repo_id, path = clone_repo(x.url)
        result = analyze(path)
        result.update(repo_id=repo_id, source_url=x.url)
        return result
    except ValueError as exc:
        logger.info("Invalid repository import input: %s", type(exc).__name__)
        raise HTTPException(400, "Invalid repository URL or import capacity reached") from exc
    except Exception as exc:
        logger.exception("Repository import or analysis failed")
        raise HTTPException(500, "Could not import or analyze the repository") from exc


@app.post("/api/search")
def do_search(x: Search):
    try:
        return {"results": search_code(safe_repo_path(x.repo_id), x.query)}
    except ValueError as exc:
        raise HTTPException(400, "Invalid repository ID or search query") from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, "Repository not found") from exc
    except Exception as exc:
        logger.exception("Repository search failed")
        raise HTTPException(500, "Repository search failed") from exc


def ai(repo_id,question,mode):
    path=safe_repo_path(repo_id); context=build_context(path,question,10 if mode=="architecture" else 8,20000)
    prompt=f"""Analyze this repository. The user request is: {question}
Use only the code context below.
{context}
Give a concise developer-facing answer. Cite actual file paths. Do not invent files or behavior."""
    return chat(prompt)
def _ai_answer(x: Ask, question: str, mode: str) -> dict[str, str]:
    try:
        return {"answer": ai(x.repo_id, question, mode)}
    except ValueError as exc:
        raise HTTPException(400, "Invalid repository ID or question") from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, "Repository not found") from exc
    except Exception as exc:
        logger.exception("Local AI request failed")
        raise HTTPException(503, "Local AI service is unavailable") from exc


@app.post("/api/ask")
def do_ask(x: Ask):
    return _ai_answer(x, x.question, "ask")


@app.post("/api/architecture")
def arch(x: Ask):
    return _ai_answer(
        x, "Explain the architecture, components, entry points and request/data flow.",
        "architecture"
    )


@app.get("/api/repositories")
def repositories():
    rows = list_repositories()
    return {"repositories": rows, "count": len(rows)}


@app.delete("/api/repositories/{repo_id}")
def remove_repository(repo_id: str):
    try:
        delete_repository(repo_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"repo_id": repo_id, "deleted": True}


@app.post("/api/repositories/cleanup")
def cleanup_repositories_endpoint(req: Cleanup):
    outcome = cleanup_repositories(req.max_age_hours, dry_run=req.dry_run)
    return {**outcome, "dry_run": req.dry_run, "max_age_hours": req.max_age_hours}