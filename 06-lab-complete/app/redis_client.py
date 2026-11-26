"""Shared Redis client. Connection attempts happen only when commands run."""

import redis
from redis.exceptions import RedisError

from .config import settings


r = redis.Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


def redis_healthy() -> bool:
    try:
        return bool(r.ping())
    except RedisError:
        return False
