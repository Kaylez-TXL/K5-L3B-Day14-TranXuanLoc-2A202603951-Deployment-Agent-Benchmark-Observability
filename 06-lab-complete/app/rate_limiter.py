"""Per-key sliding-window rate limiting across workers."""

from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException

from .config import settings
from .redis_client import r


WINDOW_MS = 60_000

# Redis runs the entire window update atomically. Its clock is shared by all workers.
take_slot = r.register_script("""
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local time = redis.call('TIME')
local now_ms = time[1] * 1000 + math.floor(time[2] / 1000)

redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)
if redis.call('ZCARD', key) >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    return math.max(1, math.ceil((oldest[2] + window_ms - now_ms) / 1000))
end

redis.call('ZADD', key, now_ms, ARGV[3])
redis.call('PEXPIRE', key, window_ms)
return 0
""")


def check_rate_limit(key: str) -> None:
    key_digest = sha256(key.encode("utf-8")).hexdigest()
    retry_after = take_slot(
        keys=[f"agent:rate:{key_digest}"],
        args=[settings.rate_limit_per_minute, WINDOW_MS, uuid4().hex],
    )
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
