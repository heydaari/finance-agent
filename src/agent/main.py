import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

from .agent import stream_answer  # noqa: E402
from .logging_config import configure_agent_logging  # noqa: E402


configure_agent_logging()
logger = logging.getLogger("finance_agent.api")
FRONTEND_DIR = PROJECT_ROOT / "src" / "frontend"
app = FastAPI(title="Persian Finance & Crypto Assistant", version="0.1.0")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class HistoryMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|model)$")
    content: str


class StreamRequest(BaseModel):
    query: str = Field(min_length=1)
    history: list[HistoryMessage] = Field(default_factory=list)


@app.get("/")
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/stream")
def stream(body: StreamRequest, request: Request) -> StreamingResponse:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured in .env")

    history = [item.model_dump() for item in body.history]
    logger.info("agent_request_started query_length=%d history_messages=%d", len(body.query), len(history))

    def events():
        try:
            logger.info("stage=agent_stream_started")
            for event in stream_answer(api_key, body.query, history):
                yield f"data: {json.dumps(event)}\n\n"
            logger.info("stage=agent_stream_finished")
        except Exception as error:
            logger.exception("agent_request_failed error=%s", error)
            yield f"data: {json.dumps({'type': 'error', 'message': str(error)})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
