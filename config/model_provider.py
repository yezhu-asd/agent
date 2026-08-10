"""Model provider factory for chat LLMs and embeddings.

Supports Azure OpenAI and OpenAI-compatible providers such as Qwen,
DeepSeek, Zhipu, and OpenAI by switching environment variables.
"""

from __future__ import annotations

import os
import logging

from dotenv import load_dotenv
from langchain_openai import (
    AzureChatOpenAI,
    AzureOpenAIEmbeddings,
    ChatOpenAI,
    OpenAIEmbeddings,
)
from pydantic import SecretStr

load_dotenv()

logger = logging.getLogger(__name__)

CHAT_PROVIDERS = {"openai", "qwen", "deepseek", "zhipu", "openai-compatible", "volcengine"}
EMBEDDING_PROVIDERS = {"openai", "qwen", "zhipu", "openai-compatible", "volcengine"}


# Langfuse 可观测性（全局单例）
_LANGFUSE_HANDLER = None


def get_langfuse_handler():
    """获取 Langfuse CallbackHandler（未配置 key 时返回 None，优雅降级）"""
    global _LANGFUSE_HANDLER
    if _LANGFUSE_HANDLER is not None:
        return _LANGFUSE_HANDLER
    pk = _env("LANGFUSE_PUBLIC_KEY", "")
    sk = _env("LANGFUSE_SECRET_KEY", "")
    # 未配置或仍是占位符 → 跳过
    if not pk or not sk or "你的" in pk or "你的" in sk:
        logger.info("未配置有效的 LANGFUSE key，跳过可观测性集成")
        _LANGFUSE_HANDLER = False
        return None
    try:
        from langfuse.langchain import CallbackHandler
        # langfuse 4.x 自动从 LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST 环境变量读取配置
        _LANGFUSE_HANDLER = CallbackHandler()
        logger.info("Langfuse 可观测性已启用")
        return _LANGFUSE_HANDLER
    except Exception as e:
        logger.warning(f"Langfuse 初始化失败，跳过: {e}")
        _LANGFUSE_HANDLER = False
        return None


def _attach_langfuse(model):
    """为 LLM 实例绑定默认的 Langfuse callback（若已配置）"""
    handler = get_langfuse_handler()
    if handler:
        try:
            model.callbacks = [handler]
        except Exception:
            pass
    return model


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def get_model_provider() -> str:
    """Return configured provider, defaulting to Azure for backward compatibility."""
    return (_env("MODEL_PROVIDER", "azure") or "azure").strip().lower()


def create_chat_model(temperature: float = 0):
    """Create a chat model from environment configuration.

    Azure-compatible env vars:
        MODEL_PROVIDER=azure
        AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT,
        AZURE_OPENAI_VERSION

    OpenAI-compatible env vars:
        MODEL_PROVIDER=qwen|deepseek|zhipu|openai|openai-compatible
        LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
    """
    provider = get_model_provider()

    if provider == "azure":
        model = AzureChatOpenAI(
            azure_deployment=_env("AZURE_OPENAI_DEPLOYMENT"),
            api_version=_env("AZURE_OPENAI_VERSION"),
            temperature=temperature,
            azure_endpoint=_env("AZURE_OPENAI_ENDPOINT"),
            api_key=SecretStr(_env("AZURE_OPENAI_API_KEY", "") or ""),
        )
        return _attach_langfuse(model)

    if provider in CHAT_PROVIDERS:
        model_name = _env("LLM_MODEL", "qwen-plus") or "qwen-plus"
        model_kwargs = {}
        # DeepSeek-V4 思考模式默认开启，但思考模式下不支持 JSON Mode / tool_choice
        # 显式关闭思考模式，保证结构化输出（预约解析等）可用
        if model_name.startswith("deepseek"):
            model_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        model = ChatOpenAI(
            model=model_name,
            api_key=SecretStr(_env("LLM_API_KEY", "") or ""),
            base_url=_env("LLM_BASE_URL"),
            temperature=temperature,
            model_kwargs=model_kwargs,
        )
        return _attach_langfuse(model)

    raise ValueError(
        f"Unsupported MODEL_PROVIDER={provider!r}. "
        "Use azure, qwen, deepseek, zhipu, openai, openai-compatible, or volcengine."
    )


_EMBEDDING_CACHE = {}


def create_embedding_model():
    """Create an embedding model from environment configuration（带缓存，避免每次调用都重新加载）"""
    provider = (_env("EMBEDDING_PROVIDER") or get_model_provider()).strip().lower()

    if provider in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[provider]

    if provider == "azure":
        instance = AzureOpenAIEmbeddings(
            azure_deployment=_env("AZURE_OPENAI_DEPLOYMENT_EMBEDDING"),
            api_key=SecretStr(_env("AZURE_OPENAI_API_KEY", "") or ""),
            api_version=_env("AZURE_OPENAI_EMBEDDING_VERSION", "2023-05-15"),
            azure_endpoint=_env("AZURE_OPENAI_ENDPOINT_EMBEDDING"),
        )
        _attach_langfuse(instance)
        _EMBEDDING_CACHE[provider] = instance
        return instance

    if provider in EMBEDDING_PROVIDERS:
        instance = OpenAIEmbeddings(
            model=_env("EMBEDDING_MODEL", "text-embedding-v3") or "text-embedding-v3",
            api_key=SecretStr(_env("EMBEDDING_API_KEY") or _env("LLM_API_KEY", "") or ""),
            base_url=_env("EMBEDDING_BASE_URL") or _env("LLM_BASE_URL"),
            # OpenAI-compatible providers like DashScope (Qwen) only accept raw
            # strings; disable token-id batching to send plain text.
            check_embedding_ctx_length=False,
        )
        _attach_langfuse(instance)
        _EMBEDDING_CACHE[provider] = instance
        return instance

    if provider == "local":
        from FlagEmbedding import BGEM3FlagModel
        model_name = _env("LOCAL_EMBEDDING_MODEL", "BAAI/bge-m3") or "BAAI/bge-m3"
        device = _env("LOCAL_EMBEDDING_DEVICE", "cpu") or "cpu"
        use_fp16 = (device == "cuda")
        model = BGEM3FlagModel(model_name, use_fp16=use_fp16, device=device)

        class LocalEmbeddings:
            def embed_query(self, text: str) -> list:
                result = model.encode(text, max_length=512)
                return result['dense_vecs'].tolist()

            def embed_documents(self, texts: list) -> list:
                result = model.encode(texts, max_length=512)
                return result['dense_vecs'].tolist()

        instance = LocalEmbeddings()
        _EMBEDDING_CACHE[provider] = instance
        return instance

    raise ValueError(
        f"Unsupported EMBEDDING_PROVIDER={provider!r}. "
        "Use azure, qwen, zhipu, openai, openai-compatible, or volcengine."
    )