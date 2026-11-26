"""Shared daily cost accounting in Redis."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .config import settings
from .redis_client import r


PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def budget_key(day: datetime) -> str:
    return f"agent:budget:{day.date().isoformat()}"


def check_budget() -> None:
    day = datetime.now(timezone.utc)
    spent = float(r.get(budget_key(day)) or 0)
    if spent >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exhausted")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    day = datetime.now(timezone.utc)
    expires_at = (day + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    key = budget_key(day)
    with r.pipeline() as transaction:
        transaction.incrbyfloat(key, cost)
        transaction.expireat(key, int(expires_at.timestamp()))
        transaction.execute()
    return cost
