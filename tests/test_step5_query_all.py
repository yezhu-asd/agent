"""Step 5 测试：验证 query_all_documents 完整读取 Milvus 全量"""
import asyncio
import sys
import os
import time

os.chdir(r"E:\wu\xidian\就业\java\agent项目\smart-appointment-ai-agent-master")
sys.path.insert(0, os.getcwd())

from services.milvus_service import MilvusService

async def test():
    svc = MilvusService()
    await svc.initialize(dim=1024)

    stats = await svc.describe_index()
    print(f"[Test] collection row_count: {stats['total_vector_count']}")

    print("[Test] loading all documents (batch_size=1000)...")
    t0 = time.time()
    docs = await svc.query_all_documents(batch_size=1000)
    elapsed = time.time() - t0

    print(f"[Test] loaded {len(docs)} docs in {elapsed:.1f}s")

    assert len(docs) > 0, "应加载到文档"

    # 验证无重复
    ids = [d["id"] for d in docs]
    unique_ids = set(ids)
    assert len(ids) == len(unique_ids), f"有重复! total={len(ids)}, unique={len(unique_ids)}"

    # 随机抽查：确认 cursor 没有遗漏 Milvus 中存在的 ID
    import random
    random.seed(42)
    from pymilvus import MilvusClient
    client = MilvusClient(uri="http://localhost:19530")
    test_nums = random.sample(range(0, 866500), 100)
    missed = 0
    for n in test_nums:
        r = client.query(
            collection_name="campus_medical_knowledge",
            filter=f'id in ["vec_{n}"]',
            output_fields=["id"], limit=1
        )
        if r and n not in {int(d["id"].split("_")[1]) for d in docs}:
            missed += 1
    assert missed == 0, f"cursor 遗漏了 {missed} 条 Milvus 中存在的 ID"

    print(f"[Test] Step 5 PASSED: cursor loaded all {len(docs)} existing docs, no duplicates, no misses")

asyncio.run(test())
