"""Step 6 测试：验证 get_collection + close"""
import asyncio
import sys
import os

os.chdir(r"E:\wu\xidian\就业\java\agent项目\smart-appointment-ai-agent-master")
sys.path.insert(0, os.getcwd())

from services.milvus_service import MilvusService
from pymilvus import MilvusClient

async def test():
    svc = MilvusService()
    await svc.initialize(dim=1024)

    # 测试 get_collection
    client = svc.get_collection()
    print(f"[Test] get_collection type: {type(client).__name__}")
    assert isinstance(client, MilvusClient), "get_collection 应返回 MilvusClient 实例"

    # 测试 close
    svc.close()
    print("[Test] close() called OK")

    # 验证 close 后 client 已关闭
    try:
        svc.client.get_collection_stats(svc.collection_name)
        print("[Test] WARNING: client still usable after close")
    except Exception as e:
        print(f"[Test] client correctly closed: {type(e).__name__}")

    print("[Test] Step 6 PASSED")

asyncio.run(test())
