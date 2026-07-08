"""
数据库会话管理器

支持 MySQL 和 SQLite，通过 settings.DATABASE_URL 配置。
提供统一的会话上下文管理、连接池和事务处理。
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from ..models import Base
from config.settings import settings


class SessionManager:
    """
    数据库会话管理器

    职责：
    1. 管理数据库连接和会话（MySQL / SQLite）
    2. 提供统一的会话上下文管理
    3. 处理事务和异常回滚
    4. 连接池管理（MySQL）
    """

    def __init__(self, db_url: str | None = None):
        """
        初始化会话管理器

        Args:
            db_url: 数据库连接 URL，默认使用 settings.DATABASE_URL
                    示例: mysql+pymysql://user:pass@host:3306/dbname
                          sqlite:///./data/smart_appointment.db
        """
        db_url = db_url or settings.DATABASE_URL
        self.db_url = db_url

        connect_args: dict = {}
        engine_kwargs: dict = {
            "echo": settings.DB_ECHO,
        }

        if "sqlite" in db_url:
            connect_args = {"check_same_thread": False}

        if db_url.startswith("mysql"):
            engine_kwargs.update({
                "pool_size": settings.DB_POOL_SIZE,
                "pool_recycle": settings.DB_POOL_RECYCLE,
                "pool_pre_ping": True,  # 使用前检查连接有效性（断线重连）
                "max_overflow": 5,
            })

        self.engine = create_engine(
            db_url,
            connect_args=connect_args,
            **engine_kwargs,
        )
        Base.metadata.create_all(self.engine)
        self.Session = scoped_session(sessionmaker(bind=self.engine))

    @contextmanager
    def session_scope(self):
        """
        提供会话上下文管理

        自动处理：
        - 会话创建和关闭
        - 事务提交和回滚
        - 异常处理
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self):
        """关闭会话管理器和连接池"""
        self.Session.remove()
        self.engine.dispose()

    def __repr__(self) -> str:
        db_type = "MySQL" if self.db_url.startswith("mysql") else "SQLite"
        return f"SessionManager({db_type})"
