"""Step 5 测试：用不同 batch_size 验证缺失规律"""
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
    total = stats["total_vector_count"]
    print(f"total: {total}")

    for bs in [100, 500, 1000, 2000]:
        t0 = time.time()
        docs = await svc.query_all_documents(batch_size=bs)
        elapsed = time.time() - t0
        missing = total - len(docs)
        print(f"batch_size={bs}: loaded {len(docs)}, missing {missing}, {elapsed:.1f}s")

asyncio.run(test())
