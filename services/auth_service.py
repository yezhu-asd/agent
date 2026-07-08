"""
认证服务

提供手机号验证码登录、Token 会话管理和会话锁。
默认使用线程安全的内存存储；如果配置了 REDIS_URL 且安装了 redis 包，则自动切换到 Redis 存储。
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterator, Optional

logger = logging.getLogger(__name__)

PHONE_PATTERN = re.compile(r"^1\d{10}$")


class AuthError(Exception):
    """认证相关异常"""


@dataclass
class VerificationCodeRecord:
    code: str
    expires_at: float
    retry_count: int = 0


@dataclass
class SessionRecord:
    token: str
    user_id: str
    phone: str
    conversation_id: str
    expires_at: float
    user_name: Optional[str] = None
    role: str = "student"
    grade_or_department: Optional[str] = None
    created_at: float = 0.0


class AuthStorageBase:
    def set_code(self, phone: str, record: VerificationCodeRecord) -> None:
        raise NotImplementedError

    def get_code(self, phone: str) -> Optional[VerificationCodeRecord]:
        raise NotImplementedError

    def delete_code(self, phone: str) -> None:
        raise NotImplementedError

    def set_session(self, token: str, record: SessionRecord) -> None:
        raise NotImplementedError

    def get_session(self, token: str) -> Optional[SessionRecord]:
        raise NotImplementedError

    def delete_session(self, token: str) -> None:
        raise NotImplementedError

    def blacklist_token(self, token: str, ttl_seconds: int) -> None:
        raise NotImplementedError

    def is_blacklisted(self, token: str) -> bool:
        raise NotImplementedError

    @contextmanager
    def session_lock(self, conversation_id: str, timeout_seconds: int = 10) -> Iterator[None]:
        raise NotImplementedError


class InMemoryAuthStorage(AuthStorageBase):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._codes: Dict[str, VerificationCodeRecord] = {}
        self._sessions: Dict[str, SessionRecord] = {}
        self._blacklist: Dict[str, float] = {}
        self._conversation_locks: Dict[str, threading.RLock] = {}

    def _cleanup_locked(self) -> None:
        now = time.time()
        expired_codes = [phone for phone, record in self._codes.items() if record.expires_at <= now]
        for phone in expired_codes:
            self._codes.pop(phone, None)

        expired_sessions = [token for token, record in self._sessions.items() if record.expires_at <= now]
        for token in expired_sessions:
            self._sessions.pop(token, None)

        expired_blacklist = [token for token, expires_at in self._blacklist.items() if expires_at <= now]
        for token in expired_blacklist:
            self._blacklist.pop(token, None)

    def set_code(self, phone: str, record: VerificationCodeRecord) -> None:
        with self._lock:
            self._cleanup_locked()
            self._codes[phone] = record

    def get_code(self, phone: str) -> Optional[VerificationCodeRecord]:
        with self._lock:
            self._cleanup_locked()
            return self._codes.get(phone)

    def delete_code(self, phone: str) -> None:
        with self._lock:
            self._codes.pop(phone, None)

    def set_session(self, token: str, record: SessionRecord) -> None:
        with self._lock:
            self._cleanup_locked()
            self._sessions[token] = record

    def get_session(self, token: str) -> Optional[SessionRecord]:
        with self._lock:
            self._cleanup_locked()
            if self.is_blacklisted(token):
                return None
            return self._sessions.get(token)

    def delete_session(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(token, None)

    def blacklist_token(self, token: str, ttl_seconds: int) -> None:
        with self._lock:
            self._blacklist[token] = time.time() + ttl_seconds

    def is_blacklisted(self, token: str) -> bool:
        with self._lock:
            self._cleanup_locked()
            return token in self._blacklist

    @contextmanager
    def session_lock(self, conversation_id: str, timeout_seconds: int = 10) -> Iterator[None]:
        with self._lock:
            lock = self._conversation_locks.setdefault(conversation_id, threading.RLock())

        acquired = lock.acquire(timeout=timeout_seconds)
        if not acquired:
            raise AuthError("会话繁忙，请稍后再试")

        try:
            yield
        finally:
            lock.release()


class RedisAuthStorage(AuthStorageBase):
    def __init__(self, redis_client: Any) -> None:
        self.redis = redis_client

    @staticmethod
    def _code_key(phone: str) -> str:
        return f"login:code:{phone}"

    @staticmethod
    def _session_key(token: str) -> str:
        return f"auth:token:{token}"

    @staticmethod
    def _blacklist_key(token: str) -> str:
        return f"auth:blacklist:{token}"

    @staticmethod
    def _lock_key(conversation_id: str) -> str:
        return f"conversation:{conversation_id}:lock"

    def set_code(self, phone: str, record: VerificationCodeRecord) -> None:
        payload = json.dumps(asdict(record), ensure_ascii=False)
        ttl = max(1, int(record.expires_at - time.time()))
        self.redis.setex(self._code_key(phone), ttl, payload)

    def get_code(self, phone: str) -> Optional[VerificationCodeRecord]:
        raw = self.redis.get(self._code_key(phone))
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return VerificationCodeRecord(**data)

    def delete_code(self, phone: str) -> None:
        self.redis.delete(self._code_key(phone))

    def set_session(self, token: str, record: SessionRecord) -> None:
        payload = json.dumps(asdict(record), ensure_ascii=False)
        ttl = max(1, int(record.expires_at - time.time()))
        self.redis.setex(self._session_key(token), ttl, payload)

    def get_session(self, token: str) -> Optional[SessionRecord]:
        if self.is_blacklisted(token):
            return None
        raw = self.redis.get(self._session_key(token))
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return SessionRecord(**data)

    def delete_session(self, token: str) -> None:
        self.redis.delete(self._session_key(token))

    def blacklist_token(self, token: str, ttl_seconds: int) -> None:
        self.redis.setex(self._blacklist_key(token), max(1, ttl_seconds), "1")

    def is_blacklisted(self, token: str) -> bool:
        return bool(self.redis.exists(self._blacklist_key(token)))

    @contextmanager
    def session_lock(self, conversation_id: str, timeout_seconds: int = 10) -> Iterator[None]:
        lock = self.redis.lock(
            self._lock_key(conversation_id),
            timeout=max(1, timeout_seconds),
            blocking_timeout=max(1, timeout_seconds),
        )
        acquired = lock.acquire(blocking=True)
        if not acquired:
            raise AuthError("会话繁忙，请稍后再试")

        try:
            yield
        finally:
            try:
                lock.release()
            except Exception:
                pass


class AuthService:
    def __init__(self) -> None:
        self.code_ttl_seconds = int(os.getenv("AUTH_CODE_TTL_SECONDS", "300"))
        self.session_ttl_seconds = int(os.getenv("AUTH_SESSION_TTL_SECONDS", "86400"))
        self.max_retry_count = int(os.getenv("AUTH_CODE_MAX_RETRY", "5"))
        self._storage = self._create_storage()

    def _create_storage(self) -> AuthStorageBase:
        from config.redis_client import get_redis_client
        redis_client = get_redis_client()
        if redis_client:
            try:
                return RedisAuthStorage(redis_client)
            except Exception as exc:
                logger.warning("Redis 不可用，回退到内存认证存储: %s", exc)
        return InMemoryAuthStorage()

    @staticmethod
    def _validate_phone(phone: str) -> str:
        normalized_phone = phone.strip()
        if not PHONE_PATTERN.match(normalized_phone):
            raise AuthError("手机号格式不正确")
        return normalized_phone

    def request_verification_code(self, phone: str) -> Dict[str, Any]:
        normalized_phone = self._validate_phone(phone)
        code = f"{secrets.randbelow(1000000):06d}"
        record = VerificationCodeRecord(
            code=code,
            expires_at=time.time() + self.code_ttl_seconds,
            retry_count=0,
        )
        self._storage.set_code(normalized_phone, record)
        logger.info("已生成验证码，phone=%s, code=%s", normalized_phone, code)
        return {
            "phone": normalized_phone,
            "code": code,
            "expires_in": self.code_ttl_seconds,
            "retry_count": 0,
        }

    def verify_code(self, phone: str, code: str) -> bool:
        normalized_phone = self._validate_phone(phone)
        normalized_code = code.strip()
        record = self._storage.get_code(normalized_phone)
        if record is None:
            raise AuthError("验证码不存在或已过期")
        if record.expires_at <= time.time():
            self._storage.delete_code(normalized_phone)
            raise AuthError("验证码已过期")
        if record.code != normalized_code:
            record.retry_count += 1
            if record.retry_count >= self.max_retry_count:
                self._storage.delete_code(normalized_phone)
                raise AuthError("验证码错误次数过多，请重新获取")
            self._storage.set_code(normalized_phone, record)
            raise AuthError("验证码错误")
        return True

    def login(
        self,
        phone: str,
        code: str,
        user_name: Optional[str] = None,
        role: str = "student",
        grade_or_department: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_phone = self._validate_phone(phone)
        self.verify_code(normalized_phone, code)

        token = uuid.uuid4().hex
        conversation_id = f"conv_{uuid.uuid4().hex[:16]}"
        created_at = time.time()
        record = SessionRecord(
            token=token,
            user_id=normalized_phone,
            phone=normalized_phone,
            conversation_id=conversation_id,
            expires_at=created_at + self.session_ttl_seconds,
            user_name=user_name,
            role=role,
            grade_or_department=grade_or_department,
            created_at=created_at,
        )
        self._storage.set_session(token, record)
        self._storage.delete_code(normalized_phone)

        logger.info("用户登录成功，phone=%s, token=%s, conversation_id=%s", normalized_phone, token, conversation_id)
        return self._session_to_payload(record)

    def get_session(self, token: str) -> Optional[Dict[str, Any]]:
        token = token.strip()
        if not token:
            return None
        record = self._storage.get_session(token)
        if record is None:
            return None
        return self._session_to_payload(record)

    def logout(self, token: str) -> None:
        token = token.strip()
        session = self._storage.get_session(token)
        if session is not None:
            remaining_ttl = max(1, int(session.expires_at - time.time()))
            self._storage.blacklist_token(token, remaining_ttl)
        self._storage.delete_session(token)

    def acquire_session_lock(self, conversation_id: str, timeout_seconds: int = 10):
        return self._storage.session_lock(conversation_id, timeout_seconds=timeout_seconds)

    def _session_to_payload(self, record: SessionRecord) -> Dict[str, Any]:
        remaining_seconds = max(0, int(record.expires_at - time.time()))
        return {
            "token": record.token,
            "token_type": "Bearer",
            "user_id": record.user_id,
            "phone": record.phone,
            "conversation_id": record.conversation_id,
            "user_name": record.user_name,
            "role": record.role,
            "grade_or_department": record.grade_or_department,
            "created_at": record.created_at,
            "expires_at": record.expires_at,
            "expires_in": remaining_seconds,
        }


auth_service = AuthService()
