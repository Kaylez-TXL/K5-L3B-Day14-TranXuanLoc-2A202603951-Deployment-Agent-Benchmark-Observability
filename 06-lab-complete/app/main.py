"""Production AI agent for the Day 14 final lab."""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from utils.mock_llm import ask as llm_ask

from .auth import verify_api_key
from .config import settings
from .cost_guard import check_budget, record_cost
from .rate_limiter import check_rate_limit
from .redis_client import r, redis_healthy


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        event.update(getattr(record, "fields", {}))
        return json.dumps(event)


logger = logging.getLogger(__name__)
logger.setLevel(settings.log_level)
logger.propagate = False
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("startup", extra={"fields": {"environment": settings.environment}})
    try:
        yield
    finally:
        r.close()
        logger.info("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_request(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    logger.info(
        "request",
        extra={
            "fields": {
                "method": request.method,
                "path": getattr(route, "path", "unmatched"),
                "status": response.status_code,
                "ms": round((perf_counter() - start) * 1000, 2),
            }
        },
    )
    return response


@app.exception_handler(RedisError)
async def redis_unavailable(_request: Request, _error: RedisError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Redis unavailable"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, key: str = Depends(verify_api_key)):
    check_rate_limit(key)
    check_budget()
    answer = llm_ask(body.question)
    # The mock returns text only. Use word counts as a token estimate for the lab.
    record_cost(len(body.question.split()), len(answer.split()))
    return {"question": body.question, "answer": answer}
