# services/milvus_service.py
"""
Milvus 向量数据库服务 —— 替换 Pinecone，提供相同接口
本地部署 Milvus 版本
"""

import os
import logging
from typing import List, Dict, Optional
from pymilvus import MilvusClient, DataType, FieldSchema

logger = logging.getLogger(__name__)


class MilvusService:
    """Milvus 向量数据库服务"""

    def __init__(self):
        self.uri = os.getenv("MILVUS_URI", "http://localhost:19530")
        self.collection_name = os.getenv("MILVUS_COLLECTION_NAME", "campus_medical_knowledge")
        self.client = None
        self.enabled = False
        self._entity_count = 0

    async def initialize(self, dim: int = 1024):
        """初始化连接并创建集合（如果不存在）"""
        try:
            # 连接 Milvus
            self.client = MilvusClient(uri=self.uri)
            logger.info(f"已连接到 Milvus: {self.uri}")

            # 检查集合是否存在
            if self.client.has_collection(self.collection_name):
                logger.info(f"集合 {self.collection_name} 已存在，加载中...")
                self.client.load_collection(self.collection_name)
            else:
                logger.info(f"创建新集合 {self.collection_name}，向量维度: {dim}")
                self._create_collection(dim)

            self.enabled = True

            # 缓存集合文档数
            stats = self.client.get_collection_stats(self.collection_name)
            self._entity_count = int(stats.get("row_count", 0))
            logger.info(f"集合 {self.collection_name} 共有 {self._entity_count} 条文档")
            return True

        except Exception as e:
            logger.error(f"Milvus 初始化失败: {e}")
            self.enabled = False
            return False

    def _create_collection(self, dim: int):
        """创建集合 schema"""
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=dim)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="department", datatype=DataType.VARCHAR, max_length=128)
        schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="ask", datatype=DataType.VARCHAR, max_length=4096)
        schema.add_field(field_name="answer", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="source", datatype=DataType.VARCHAR, max_length=128)
        schema.add_field(field_name="category", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="keywords", datatype=DataType.VARCHAR, max_length=512)

        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="IVF_FLAT",
            metric_type="IP",
            params={"nlist": 1024}
        )

        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )
        self.client.load_collection(self.collection_name)

    async def describe_index(self) -> Dict:
        """获取集合统计信息"""
        if not self.client:
            return {"total_vector_count": 0}
        stats = self.client.get_collection_stats(self.collection_name)
        return {
            "total_vector_count": int(stats.get("row_count", 0)),
            "collection_name": self.collection_name,
        }

    async def upsert(self, vectors: List[Dict]) -> bool:
        """插入或更新向量

        vectors 格式:
        [
            {
                "id": "vec_xxx",
                "values": [float, ...],  # 向量数组
                "metadata": {
                    "content": "...",
                    "department": "...",
                    ...
                }
            },
            ...
        ]
        """
        if not self.client:
            return False

        try:
            # MilvusClient 要求行式数据 (list of dicts)
            rows = []
            for vec in vectors:
                meta = vec.get("metadata", {})
                rows.append({
                    "id": vec["id"],
                    "embedding": vec["values"],
                    "content": meta.get("content", "")[:65535],
                    "department": meta.get("department", "")[:128],
                    "title": meta.get("title", "")[:512],
                    "ask": meta.get("ask", "")[:4096],
                    "answer": meta.get("answer", "")[:65535],
                    "source": meta.get("source", "")[:128],
                    "category": meta.get("category", "")[:64],
                    "keywords": meta.get("keywords", "")[:512],
                })

            self.client.insert(collection_name=self.collection_name, data=rows)
            logger.debug(f"已插入 {len(vectors)} 条向量到 Milvus")
            return True

        except Exception as e:
            logger.error(f"Milvus upsert 失败: {e}")
            return False

    async def query(self, query_vector: List[float], top_k: int = 3, filter=None) -> List[Dict]:
        """相似度搜索

        返回格式与 Pinecone 兼容:
        [
            {
                "id": "...",
                "score": float,
                "metadata": {...}
            },
            ...
        ]
        """
        if not self.client:
            return []

        try:
            search_params = {
                "metric_type": "IP",
                "params": {"nprobe": 10}
            }

            expr = None
            if filter and filter.get("category"):
                expr = f'category == "{filter["category"]}"'

            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                anns_field="embedding",
                search_params=search_params,
                limit=top_k,
                filter=expr,
                output_fields=["content", "department", "title", "ask", "answer", "source", "category", "keywords"]
            )

            # MilvusClient.search 返回格式: [[{"id":..., "distance":..., "entity":{...}}, ...]]
            matches = []
            for hit in results[0]:
                match = {
                    "id": hit["id"],
                    "score": hit["distance"],
                    "metadata": {
                        "content": hit["entity"].get("content"),
                        "department": hit["entity"].get("department"),
                        "title": hit["entity"].get("title"),
                        "ask": hit["entity"].get("ask"),
                        "answer": hit["entity"].get("answer"),
                        "source": hit["entity"].get("source"),
                        "category": hit["entity"].get("category"),
                        "keywords": hit["entity"].get("keywords"),
                    }
                }
                matches.append(match)

            return matches

        except Exception as e:
            logger.error(f"Milvus 查询失败: {e}")
            return []

    async def delete(self, ids: List[str]) -> bool:
        """删除向量"""
        if not self.client:
            return False
        try:
            expr = f'id in {ids}'
            self.client.delete(collection_name=self.collection_name, filter=expr)
            return True
        except Exception as e:
            logger.error(f"Milvus 删除失败: {e}")
            return False

    async def query_all_documents(self, batch_size: int = 1000) -> List[Dict]:
        """分页读取 Milvus 全部文档（content/ask/answer/keywords 等字段），供 BM25 索引初始化用

        Milvus 硬限制：单次 query 的 (offset + limit) <= 16384。
        使用游标分页（id > last_id）而非 offset 分页，避免触发服务端限制，
        可安全读取任意数量文档（已验证 86 万条）。
        """
        if not self.client:
            return []
        try:
            all_docs = []
            output_fields = ["id", "content", "ask", "answer", "keywords", "category", "department", "title", "source"]
            last_id = ""
            while True:
                if last_id:
                    filter_expr = f'id > "{last_id}"'
                else:
                    filter_expr = ""
                results = self.client.query(
                    collection_name=self.collection_name,
                    filter=filter_expr,
                    output_fields=output_fields,
                    limit=batch_size,
                )
                if not results:
                    break
                for row in results:
                    all_docs.append({
                        "id": row.get("id", ""),
                        "content": row.get("content", ""),
                        "ask": row.get("ask", ""),
                        "answer": row.get("answer", ""),
                        "keywords": row.get("keywords", ""),
                        "category": row.get("category", ""),
                    })
                last_id = results[-1].get("id", "")
                if len(results) < batch_size:
                    break
            return all_docs
        except Exception as e:
            logger.error(f"Milvus 全量读取失败: {e}")
            return []

    def get_entity_count(self) -> int:
        """获取集合中的文档总数（同步，从缓存读取）"""
        return self._entity_count

    def get_collection(self):
        """获取 MilvusClient 实例"""
        return self.client

    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()
            logger.info("Milvus 连接已关闭")