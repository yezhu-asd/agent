"""Step 8 全集成测试：验证服务启动 + Milvus 文档加载 + 搜索"""
import asyncio
import sys
import os
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

os.chdir(r"E:\wu\xidian\job\java\agent\CampusCare")
sys.path.insert(0, os.getcwd())

from services.knowledge_service import KnowledgeService

async def test():
    print("[Test] Initializing KnowledgeService...")
    t0 = time.time()
    ks = KnowledgeService()
    await ks.initialize()
    elapsed = time.time() - t0
    print(f"[Test] Initialized in {elapsed:.1f}s")

    # 关键验证
    assert ks.vector_db_type == "milvus", f"应为 milvus, 得到 {ks.vector_db_type}"

    bm25_count = len(ks.bm25_corpus)
    print(f"[Test] bm25_corpus size: {bm25_count}")
    assert bm25_count > 10, f"BM25 应包含 Milvus 文档, 但只有 {bm25_count} 条"
    print(f"[Test] BM25 loaded {bm25_count} docs (10 seed + {bm25_count - 10} from Milvus)")

    # 搜索测试
    results = await ks.search("嗓子疼怎么办", top_k=3)
    print(f"[Test] search results: {len(results)}")
    assert len(results) > 0, "搜索应返回结果"
    print(f"[Test] top result score={results[0].get('score', 0):.4f}")
    print(f"[Test] top result content={str(results[0].get('content', results[0].get('answer', '')))[:80]}...")

    print(f"[Test] Step 8 PASSED: full integration OK ({elapsed:.1f}s)")

asyncio.run(test())
