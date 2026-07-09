"""Step 1 测试：验证 MilvusClient 连接与初始化"""
import asyncio
import sys
import os

os.chdir(r"E:\wu\xidian\就业\java\agent项目\smart-appointment-ai-agent-master")
sys.path.insert(0, os.getcwd())

from services.milvus_service import MilvusService

async def test():
    svc = MilvusService()
    ok = await svc.initialize(dim=1024)
    print(f"[Test] initialize() returned: {ok}")
    print(f"[Test] enabled: {svc.enabled}")
    print(f"[Test] client type: {type(svc.client).__name__}")

    assert ok is True, "initialize 应该返回 True"
    assert svc.enabled is True, "enabled 应为 True"
    assert svc.client is not None, "client 不应为 None"
    # 验证 client 是 MilvusClient 实例
    from pymilvus import MilvusClient
    assert isinstance(svc.client, MilvusClient), "client 应是 MilvusClient 实例"
    print("[Test] Step 1 PASSED: MilvusClient connected OK")

asyncio.run(test())
