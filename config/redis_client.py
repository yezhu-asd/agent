"""
Redis 客户端统一管理

提供全局单例 Redis 客户端，避免多处重复创建连接。
若未配置 REDIS_URL 或连接失败，自动降级（get_redis_client 返回 None）。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client: Optional[object] = None
_redis_tried: bool = False


def get_redis_client() -> Optional[object]:
    """
    获取 Redis 客户端（单例）

    首次调用时尝试连接 Redis。成功则缓存客户端实例；失败则记为不可用。

    Returns:
        Redis 客户端实例，或 None（Redis 不可用）
    """
    global _redis_client, _redis_tried

    if _redis_tried:
        return _redis_client

    _redis_tried = True

    try:
        import os
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            logger.info("未配置 REDIS_URL，Redis 功能不可用，将使用内存存储")
            return None

        import redis
        client = redis.from_url(redis_url, decode_responses=True, protocol=2)
        client.ping()
        _redis_client = client
        logger.info("✅ Redis 连接成功: %s", redis_url)
        return _redis_client

    except Exception as exc:
        logger.warning("Redis 不可用，回退到内存存储: %s", exc)
        _redis_client = None
        return None


def is_redis_available() -> bool:
    """检查 Redis 是否可用"""
    return get_redis_client() is not None
