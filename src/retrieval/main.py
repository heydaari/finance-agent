import logging
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .indexer import get_or_create_index
from .logging_config import configure_logging, stage


configure_logging()
logger = logging.getLogger("cv_retrieval.api")
app = FastAPI(title="Persian Finance Knowledge Retrieval API", version="0.1.0")


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = uuid4().hex[:12]
    request.state.request_id = request_id
    started = time.perf_counter()
    stage(logger, request_id, "request_started", method=request.method, path=request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "stage=request_failed request_id=%s elapsed_ms=%.1f",
            request_id,
            (time.perf_counter() - started) * 1000,
        )
        raise
    response.headers["X-Request-ID"] = request_id
    stage(
        logger,
        request_id,
        "request_finished",
        status_code=response.status_code,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    return response


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, description="Natural-language finance search query")
    k: int = Field(default=5, ge=1, le=20, description="Number of knowledge-base chunks to return")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/search")
def search(body: SearchRequest, http_request: Request) -> dict:
    request_id = http_request.state.request_id
    stage(logger, request_id, "search_received", query_length=len(body.query), k=body.k)
    try:
        vector_db = get_or_create_index(request_id)
        stage(logger, request_id, "semantic_search_started", k=body.k)
        matches = vector_db.similarity_search_with_score(body.query, k=body.k)
    except (FileNotFoundError, RuntimeError, OSError) as error:
        logger.exception("stage=search_failed request_id=%s error=%s", request_id, error)
        raise HTTPException(status_code=500, detail=str(error)) from error

    stage(logger, request_id, "semantic_search_finished", result_count=len(matches))
    return {
        "query": body.query,
        "request_id": request_id,
        "results": [
            {
                "score": float(score),
                "source": document.metadata.get("source"),
                "content": document.page_content,
            }
            for document, score in matches
        ],
    }
