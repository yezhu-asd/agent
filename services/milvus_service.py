# services/milvus_service.py
"""
Milvus 向量数据库服务 —— 替换 Pinecone，提供相同接口
本地部署 Milvus 版本
"""

import os
import logging
from typing import List, Dict, Optional
from pymilvus import connections, utility, Collection, CollectionSchema, FieldSchema, DataType

logger = logging.getLogger(__name__)


class MilvusService:
    """Milvus 向量数据库服务"""

    def __init__(self):
        self.uri = os.getenv("MILVUS_URI", "http://localhost:19530")
        self.collection_name = os.getenv("MILVUS_COLLECTION_NAME", "campus_medical_knowledge")
        self.user = os.getenv("MILVUS_USER", "")
        self.password = os.getenv("MILVUS_PASSWORD", "")
        self.collection = None
        self.enabled = False

    async def initialize(self, dim: int = 1024):
        """初始化连接并创建集合（如果不存在）"""
        try:
            # 连接 Milvus
            connect_kwargs = {
                "uri": self.uri,
            }
            if self.user and self.password:
                connect_kwargs["user"] = self.user
                connect_kwargs["password"] = self.password

            connections.connect(**connect_kwargs)
            logger.info(f"已连接到 Milvus: {self.uri}")

            # 检查集合是否存在
            if utility.has_collection(self.collection_name):
                logger.info(f"集合 {self.collection_name} 已存在，加载中...")
                self.collection = Collection(self.collection_name)
                self.collection.load()
            else:
                logger.info(f"创建新集合 {self.collection_name}，向量维度: {dim}")
                self._create_collection(dim)

            self.enabled = True
            return True

        except Exception as e:
            logger.error(f"Milvus 初始化失败: {e}")
            self.enabled = False
            return False

    def _create_collection(self, dim: int):
        """创建集合 schema"""
        # 定义字段
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="department", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="ask", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="answer", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),  # 用于种子数据
            FieldSchema(name="keywords", dtype=DataType.VARCHAR, max_length=512),  # 用于种子数据
        ]

        schema = CollectionSchema(fields=fields, description="校园医学知识库向量")
        self.collection = Collection(name=self.collection_name, schema=schema)

        # 创建索引（IVF_FLAT 适合中小规模数据，可根据数据量调整）
        index_params = {
            "metric_type": "IP",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        self.collection.create_index(field_name="embedding", index_params=index_params)
        self.collection.load()

    async def describe_index(self) -> Dict:
        """获取集合统计信息"""
        if not self.collection:
            return {"total_vector_count": 0}
        return {
            "total_vector_count": self.collection.num_entities,
            "collection_name": self.collection_name,
            "schema": str(self.collection.schema)
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
        if not self.collection:
            return False

        try:
            # Milvus 要求按列组织数据
            ids = []
            embeddings = []
            contents = []
            departments = []
            titles = []
            asks = []
            answers = []
            sources = []
            categories = []
            keywordses = []

            for vec in vectors:
                ids.append(vec["id"])
                embeddings.append(vec["values"])
                meta = vec.get("metadata", {})
                contents.append(meta.get("content", "")[:65535])
                departments.append(meta.get("department", "")[:128])
                titles.append(meta.get("title", "")[:512])
                asks.append(meta.get("ask", "")[:4096])
                answers.append(meta.get("answer", "")[:65535])
                sources.append(meta.get("source", "")[:128])
                categories.append(meta.get("category", "")[:64])
                keywordses.append(meta.get("keywords", "")[:512])

            insert_data = [
                ids,
                embeddings,
                contents,
                departments,
                titles,
                asks,
                answers,
                sources,
                categories,
                keywordses,
            ]

            mr = self.collection.insert(insert_data)
            self.collection.flush()
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
        if not self.collection:
            return []

        try:
            # 构搜索条件
            search_params = {
                "metric_type": "IP",
                "params": {"nprobe": 10}
            }

            expr = None
            if filter and filter.get("category"):
                expr = f'category == "{filter["category"]}"'

            results = self.collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["content", "department", "title", "ask", "answer", "source", "category", "keywords"]
            )

            matches = []
            for hits in results:
                for hit in hits:
                    match = {
                        "id": hit.id,
                        "score": hit.score,
                        "metadata": {
                            "content": hit.entity.get("content"),
                            "department": hit.entity.get("department"),
                            "title": hit.entity.get("title"),
                            "ask": hit.entity.get("ask"),
                            "answer": hit.entity.get("answer"),
                            "source": hit.entity.get("source"),
                            "category": hit.entity.get("category"),
                            "keywords": hit.entity.get("keywords"),
                        }
                    }
                    matches.append(match)

            return matches

        except Exception as e:
            logger.error(f"Milvus 查询失败: {e}")
            return []

    async def delete(self, ids: List[str]) -> bool:
        """删除向量"""
        if not self.collection:
            return False
        try:
            expr = f'id in {ids}'
            self.collection.delete(expr)
            return True
        except Exception as e:
            logger.error(f"Milvus 删除失败: {e}")
            return False

    async def query_all_documents(self, batch_size: int = 50000) -> List[Dict]:
        """分页读取 Milvus 全部文档（content/ask/answer/keywords 等字段），供 BM25 索引初始化用

        Milvus 硬限制：(offset + limit) 必须 <= maximumQueryResultWindow（已配置为 1000000）。
        使用 limit=50000 大批次，约 21 次请求即可加载 100 万条文档（1-2 分钟内完成）。
        """
        if not self.collection:
            return []
        try:
            all_docs = []
            offset = 0
            batch_size = min(batch_size, 50000)
            output_fields = ["content", "ask", "answer", "keywords", "category", "department", "title", "source"]
            max_window = 1000000  # 与 docker-compose 中配置的 maximumQueryResultWindow 一致
            fetched_in_window = 0
            while True:
                limit = min(batch_size, max_window - offset)
                if limit <= 0:
                    # 当前 offset 到达窗口上限，重置 offset = 已加载数，继续下一页
                    if fetched_in_window == 0:
                        break  # 真正取不到数据才退出
                    offset = len(all_docs)
                    fetched_in_window = 0
                    continue
                results = self.collection.query(
                    expr="",
                    output_fields=output_fields,
                    offset=offset,
                    limit=limit,
                )
                if not results:
                    # 空结果：尝试跳到下一窗口（offset 重置为已加载总数）
                    if fetched_in_window == 0:
                        break
                    offset = len(all_docs)
                    fetched_in_window = 0
                    continue
                for row in results:
                    all_docs.append({
                        "id": row.get("id", ""),
                        "content": row.get("content", ""),
                        "ask": row.get("ask", ""),
                        "answer": row.get("answer", ""),
                        "keywords": row.get("keywords", ""),
                        "category": row.get("category", ""),
                    })
                fetched_in_window += len(results)
                if len(results) < limit:
                    # 本批次结果不足，处于窗口末端，跳到下一窗口
                    offset = len(all_docs)
                    fetched_in_window = 0
                else:
                    offset += len(results)
            return all_docs
        except Exception as e:
            logger.error(f"Milvus 全量读取失败: {e}")
            return []

    def get_collection(self):
        """获取原始 collection 对象"""
        return self.collection

    def close(self):
        """关闭连接"""
        connections.disconnect("default")
        logger.info("Milvus 连接已关闭")