"""Step 4 测试：验证 delete"""
import asyncio
import sys
import os

os.chdir(r"E:\wu\xidian\就业\java\agent项目\smart-appointment-ai-agent-master")
sys.path.insert(0, os.getcwd())

from services.milvus_service import MilvusService

async def test():
    svc = MilvusService()
    await svc.initialize(dim=1024)

    # 测试删除不存在的 ID（不应该报错）
    ok = await svc.delete(["nonexistent_id_12345"])
    print(f"[Test] delete nonexistent id returned: {ok}")
    assert ok is True, "删除不存在的 ID 应返回 True（不报错）"

    # 测试删除空列表
    ok = await svc.delete([])
    print(f"[Test] delete empty list returned: {ok}")
    assert ok is True, "删除空列表应返回 True"

    print("[Test] Step 4 PASSED: delete OK")

asyncio.run(test())
