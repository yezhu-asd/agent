"""诊断：分析缺失的 500 条文档"""
import asyncio
import sys
import os

os.chdir(r"E:\wu\xidian\就业\java\agent项目\smart-appointment-ai-agent-master")
sys.path.insert(0, os.getcwd())

from services.milvus_service import MilvusService

async def test():
    svc = MilvusService()
    await svc.initialize(dim=1024)

    # 拉取所有文档
    docs = await svc.query_all_documents(batch_size=1000)
    print(f"loaded {len(docs)} docs")

    # 分析 ID 格式
    ids = [d["id"] for d in docs]
    print(f"first 5 ids: {ids[:5]}")
    print(f"last 5 ids: {ids[-5:]}")

    # 检查 ID 模式
    sample_ids = ids[:20]
    print(f"sample ids: {sample_ids}")

    # 检查是否有 vec_ 格式
    vec_ids = [i for i in ids if i.startswith("vec_")]
    print(f"vec_ format count: {len(vec_ids)}")

    # 检查 vec_99999 附近的 ID
    boundary_ids = [i for i in ids if "vec_999" in i or "vec_1000" in i]
    print(f"boundary ids (vec_999/vec_1000): {boundary_ids[:20]}")

    # 找到最后一个 vec_9xxxx 和第一个 vec_100000+
    vec_9_ids = [i for i in ids if i.startswith("vec_9")]
    vec_10plus_ids = [i for i in ids if i.startswith("vec_10")]
    print(f"vec_9xxxx count: {len(vec_9_ids)}")
    print(f"vec_10xxxx count: {len(vec_10plus_ids)}")
    if vec_9_ids:
        print(f"last vec_9xxxx: {vec_9_ids[-1]}")
    if vec_10plus_ids:
        print(f"first vec_10xxxx: {vec_10plus_ids[0]}")

asyncio.run(test())
