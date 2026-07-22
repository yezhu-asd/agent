"""Step 7 测试：验证知识库服务改造后的接口"""
import asyncio
import sys
import os

os.chdir(r"E:\wu\xidian\job\java\agent\CampusCare")
sys.path.insert(0, os.getcwd())

from services.milvus_service import MilvusService

async def test():
    # 1) 验证 MilvusService.get_entity_count()
    svc = MilvusService()
    await svc.initialize(dim=1024)
    count = svc.get_entity_count()
    print(f"[Test] get_entity_count: {count}")
    assert isinstance(count, int) and count > 0

    # 2) 验证 get_documents_count 调用链（不触发全量 BM25 构建）
    from services.knowledge_service import KnowledgeService
    ks = KnowledgeService()
    ks.vector_db_type = "milvus"
    ks.milvus = svc
    ks.initialized = True
    # 不调用全量 initialize()（避免 BM25 全量构建），直接测试计数
    doc_count = ks.get_documents_count()
    print(f"[Test] knowledge.get_documents_count: {doc_count}")
    assert doc_count == count, f"计数不一致: milvus={count}, knowledge={doc_count}"

    print("[Test] Step 7 PASSED")

asyncio.run(test())
