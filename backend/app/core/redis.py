from typing import Optional
import redis
from backend.app.core.config import settings
from backend.app.core.logging import logger

_redis_pool: Optional[redis.ConnectionPool] = None


def get_redis_pool() -> redis.ConnectionPool:
    """
    Get or initialize the shared Redis connection pool.
    """
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            db=settings.REDIS_DB,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            decode_responses=True,
        )
    return _redis_pool


def get_redis_client() -> redis.Redis:
    """
    Returns a configured Redis client instance.
    """
    pool = get_redis_pool()
    return redis.Redis(connection_pool=pool)


def check_redis_connection() -> bool:
    """
    Execute a PING command against the Redis server.
    Returns True if PONG response is received, False otherwise.
    """
    try:
        client = get_redis_client()
        return bool(client.ping())
    except Exception as exc:
        logger.warning(f"Redis health check failed: {exc}")
        return False


def close_redis_pool() -> None:
    """
    Gracefully disconnect all connections in the pool upon application shutdown.
    """
    global _redis_pool
    if _redis_pool is not None:
        _redis_pool.disconnect()
        _redis_pool = None
        logger.info("Redis connection pool closed.")
