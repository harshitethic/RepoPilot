"""RAG endpoints sharing RepoPilot's loopback-only security boundary."""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.github import safe_repo_path

from .answer import answer_question
from .service import retrieve

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rag", tags=["RAG"])


class RetrieveRequest(BaseModel):
    repo_id: str
    query: str = Field(min_length=1, max_length=1200)
    limit: int = Field(default=8, ge=1, le=20)
    path_prefix: str | None = Field(default=None, max_length=250)


class AskRequest(BaseModel):
    repo_id: str
    question: str = Field(min_length=3, max_length=1200)
    limit: int = Field(default=6, ge=1, le=12)


def repository_root(repo_id: str):
    try:
        return safe_repo_path(repo_id)
    except ValueError as exc:
        raise HTTPException(400, "Invalid repository ID") from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, "Repository not found") from exc


@router.post("/retrieve")
def retrieve_endpoint(payload: RetrieveRequest):
    root = repository_root(payload.repo_id)
    try:
        hits = retrieve(root, payload.query, limit=payload.limit, path_prefix=payload.path_prefix)
    except ValueError as exc:
        raise HTTPException(400, "Invalid retrieval request") from exc
    except Exception as exc:
        logger.exception("Repository retrieval failed")
        raise HTTPException(500, "Repository retrieval failed") from exc
    return {"results": [hit.public() for hit in hits], "count": len(hits), "retriever": "bm25"}


@router.post("/ask")
def ask_endpoint(payload: AskRequest):
    root = repository_root(payload.repo_id)
    try:
        return answer_question(root, payload.question, limit=payload.limit)
    except ValueError as exc:
        raise HTTPException(400, "Invalid RAG question") from exc
    except Exception as exc:
        logger.exception("Local RAG model unavailable")
        raise HTTPException(503, "Local AI service is unavailable") from exc
