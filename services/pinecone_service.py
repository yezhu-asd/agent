"""
Pinecone 向量数据库服务

封装 Pinecone SDK，提供向量存储和相似度搜索能力。
通过 PINECONE_API_KEY 环境变量控制启用/禁用。

使用方式：
    service = PineconeService()
    await service.initialize()
    await service.upsert([{"id": "doc_1", "values": [...], "metadata": {...}}])
    results = await service.query(query_vector, top_k=5)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class PineconeService:
    """Pinecone 向量数据库封装"""

    def __init__(self):
        self.api_key = settings.PINECONE_API_KEY
        self.index_name = settings.PINECONE_INDEX_NAME
        self.enabled = bool(self.api_key)
        self._index = None
        self._dimension: Optional[int] = None

    async def initialize(self) -> None:
        """初始化 Pinecone 连接和索引"""
        if not self.enabled:
            logger.info("Pinecone 未配置，跳过初始化")
            return

        try:
            from pinecone import Pinecone, ServerlessSpec

            self._pc = Pinecone(api_key=self.api_key)

            # 检查或创建索引
            existing_indexes = self._pc.list_indexes()
            existing_names = [idx.name for idx in (existing_indexes or [])]

            if self.index_name not in existing_names:
                # 需要先获取 embedding 维度
                if self._dimension is None:
                    self._dimension = self._detect_dimension()

                logger.info("创建 Pinecone 索引: %s (dim=%d)", self.index_name, self._dimension)
                self._pc.create_index(
                    name=self.index_name,
                    dimension=self._dimension,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1",
                    ),
                )

            self._index = self._pc.Index(self.index_name)
            logger.info("✅ Pinecone 初始化完成，索引: %s", self.index_name)

        except Exception as e:
            logger.error("Pinecone 初始化失败: %s", e)
            self.enabled = False
            self._index = None

    def _detect_dimension(self) -> int:
        """通过 sample embedding 检测向量维度"""
        try:
            from services.text_embedding import embed_input
            sample_vec = embed_input("dimension test")
            return len(sample_vec)
        except Exception:
            return 1536  # OpenAI text-embedding-ada-002 / text-embedding-3 默认

    async def upsert(
        self,
        vectors: List[Dict[str, Any]],
        namespace: str = "default",
    ) -> bool:
        """
        批量 upsert 向量到 Pinecone

        Args:
            vectors: [{"id": "doc_1", "values": [0.1, 0.2, ...], "metadata": {...}}, ...]
            namespace: 命名空间
        """
        if not self.enabled or self._index is None:
            logger.debug("Pinecone 不可用，跳过 upsert")
            return False

        try:
            self._index.upsert(vectors=vectors, namespace=namespace)
            logger.debug("Pinecone upsert: %d vectors", len(vectors))
            return True
        except Exception as e:
            logger.error("Pinecone upsert 失败: %s", e)
            return False

    async def query(
        self,
        vector: List[float],
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        namespace: str = "default",
    ) -> List[Dict[str, Any]]:
        """
        向量相似度搜索

        Args:
            vector: 查询向量
            top_k: 返回数量
            filter: 元数据过滤条件，如 {"category": "预防"}
            namespace: 命名空间

        Returns:
            [{"id": "doc_1", "score": 0.95, "metadata": {...}}, ...]
        """
        if not self.enabled or self._index is None:
            return []

        try:
            results = self._index.query(
                vector=vector,
                top_k=top_k,
                filter=filter or None,
                namespace=namespace,
                include_metadata=True,
            )

            matches = []
            for match in results.get("matches", []):
                matches.append({
                    "id": match.get("id", ""),
                    "score": match.get("score", 0.0),
                    "metadata": match.get("metadata", {}),
                })
            return matches

        except Exception as e:
            logger.error("Pinecone query 失败: %s", e)
            return []

    async def delete(self, ids: List[str], namespace: str = "default") -> bool:
        """删除向量"""
        if not self.enabled or self._index is None:
            return False

        try:
            self._index.delete(ids=ids, namespace=namespace)
            logger.debug("Pinecone delete: %d ids", len(ids))
            return True
        except Exception as e:
            logger.error("Pinecone delete 失败: %s", e)
            return False

    async def describe_index(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        if not self.enabled or self._index is None:
            return {"enabled": False}

        try:
            stats = self._index.describe_index_stats()
            return {
                "enabled": True,
                "index_name": self.index_name,
                "total_vector_count": stats.get("total_vector_count", 0),
                "namespaces": stats.get("namespaces", {}),
            }
        except Exception as e:
            logger.error("Pinecone describe 失败: %s", e)
            return {"enabled": True, "error": str(e)}
