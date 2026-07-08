"""
应用程序设置模块

集中管理所有环境变量配置，包括：
- 数据库（MySQL/SQLite）
- Redis
- Pinecone 向量数据库
- LLM / Embedding
- 认证
"""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    """读取环境变量，空字符串视为未设置"""
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _env_int(name: str, default: int = 0) -> int:
    """读取整型环境变量"""
    try:
        return int(os.getenv(name, str(default)))
    except (ValueError, TypeError):
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    """读取布尔型环境变量"""
    val = os.getenv(name, str(default)).strip().lower()
    return val in ("true", "1", "yes", "on")


class AppSettings:
    """应用程序全局设置"""

    # ===========================
    # 数据库
    # ===========================
    @property
    def DATABASE_URL(self) -> str:
        """数据库连接 URL，默认 SQLite"""
        return _env("DATABASE_URL", "sqlite:///./data/smart_appointment.db") or "sqlite:///./data/smart_appointment.db"

    @property
    def DB_ECHO(self) -> bool:
        """是否打印 SQL 日志"""
        return _env_bool("DB_ECHO", False)

    @property
    def DB_POOL_SIZE(self) -> int:
        """数据库连接池大小"""
        return _env_int("DB_POOL_SIZE", 10)

    @property
    def DB_POOL_RECYCLE(self) -> int:
        """连接回收时间（秒）"""
        return _env_int("DB_POOL_RECYCLE", 3600)

    @property
    def IS_MYSQL(self) -> bool:
        """是否使用 MySQL"""
        return self.DATABASE_URL.startswith("mysql")

    # ===========================
    # Redis
    # ===========================
    @property
    def REDIS_URL(self) -> Optional[str]:
        """Redis 连接 URL，未配置则回退内存存储"""
        return _env("REDIS_URL")

    @property
    def REDIS_ENABLED(self) -> bool:
        """Redis 是否启用"""
        return self.REDIS_URL is not None

    # ===========================
    # Pinecone
    # ===========================
    @property
    def PINECONE_API_KEY(self) -> Optional[str]:
        """Pinecone API Key"""
        return _env("PINECONE_API_KEY")

    @property
    def PINECONE_INDEX_NAME(self) -> str:
        """Pinecone 索引名"""
        return _env("PINECONE_INDEX_NAME", "campus-medical-knowledge") or "campus-medical-knowledge"

    @property
    def PINECONE_ENABLED(self) -> bool:
        """Pinecone 是否启用"""
        return self.PINECONE_API_KEY is not None

    # ===========================
    # LLM
    # ===========================
    @property
    def MODEL_PROVIDER(self) -> str:
        return (_env("MODEL_PROVIDER", "zhipu") or "zhipu").strip().lower()

    @property
    def LLM_API_KEY(self) -> str:
        return _env("LLM_API_KEY", "") or ""

    @property
    def LLM_BASE_URL(self) -> Optional[str]:
        return _env("LLM_BASE_URL")

    @property
    def LLM_MODEL(self) -> str:
        return _env("LLM_MODEL", "glm-4-flash") or "glm-4-flash"

    # ===========================
    # Embedding
    # ===========================
    @property
    def EMBEDDING_PROVIDER(self) -> str:
        return (_env("EMBEDDING_PROVIDER") or self.MODEL_PROVIDER).strip().lower()

    @property
    def EMBEDDING_API_KEY(self) -> str:
        return _env("EMBEDDING_API_KEY") or self.LLM_API_KEY

    @property
    def EMBEDDING_BASE_URL(self) -> Optional[str]:
        return _env("EMBEDDING_BASE_URL") or self.LLM_BASE_URL

    @property
    def EMBEDDING_MODEL(self) -> str:
        return _env("EMBEDDING_MODEL", "embedding-3") or "embedding-3"

    # ===========================
    # 认证
    # ===========================
    @property
    def AUTH_CODE_TTL_SECONDS(self) -> int:
        return _env_int("AUTH_CODE_TTL_SECONDS", 300)

    @property
    def AUTH_SESSION_TTL_SECONDS(self) -> int:
        return _env_int("AUTH_SESSION_TTL_SECONDS", 86400)

    @property
    def AUTH_CODE_MAX_RETRY(self) -> int:
        return _env_int("AUTH_CODE_MAX_RETRY", 5)

    # ===========================
    # 应用
    # ===========================
    @property
    def DEBUG(self) -> bool:
        return _env_bool("DEBUG", True)

    @property
    def LOG_LEVEL(self) -> str:
        return _env("LOG_LEVEL", "INFO") or "INFO"

    @property
    def APP_VERSION(self) -> str:
        return "2.0.0-medical"

    @property
    def APP_TITLE(self) -> str:
        return "🏥 校园医务室 AI Agent"


# 全局设置单例
settings = AppSettings()
