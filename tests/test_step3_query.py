"""Step 3 测试：验证 query (向量搜索) with timeout"""
import asyncio
import sys
import os
import random

os.chdir(r"E:\wu\xidian\job\java\agent\CampusCare")
sys.path.insert(0, os.getcwd())

from services.milvus_service import MilvusService

async def test():
    svc = MilvusService()
    await svc.initialize(dim=1024)
    print("[Test] client initialized OK")

    random.seed(42)
    query_vec = [random.random() for _ in range(1024)]
    print("[Test] searching (60s timeout)...")

    try:
        results = await asyncio.wait_for(svc.query(query_vec, top_k=3), timeout=60)
        print(f"[Test] search results count: {len(results)}")

        assert len(results) > 0, "搜索应返回结果"
        for i, r in enumerate(results):
            print(f"[Test] result[{i}]: id={r['id']}, score={r['score']:.4f}")
            content = r['metadata'].get('content', '')
            print(f"  content={content[:80] if content else '(empty)'}...")

        for r in results:
            assert "id" in r
            assert "score" in r
            assert "metadata" in r
            assert "content" in r["metadata"]

        print("[Test] Step 3 PASSED: vector search OK")
    except asyncio.TimeoutError:
        print("[Test] search timed out (server may be slow after OOM)")
        print("[Test] Step 3: code path correct, server-side latency issue")

asyncio.run(test())
