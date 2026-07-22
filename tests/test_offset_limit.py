"""验证 offset 分页在窗口限制内的行为"""
import asyncio
import sys
import os

os.chdir(r"E:\wu\xidian\job\java\agent\CampusCare")
sys.path.insert(0, os.getcwd())

from pymilvus import MilvusClient

async def test():
    client = MilvusClient(uri="http://localhost:19530")
    collection_name = "campus_medical_knowledge"

    # 测试不同 offset 下的查询
    for offset in [0, 1000, 16000, 16384]:
        try:
            results = client.query(
                collection_name=collection_name,
                filter="",
                output_fields=["id"],
                limit=1,
                offset=offset,
            )
            print(f"offset={offset}: OK, got {len(results)} results")
        except Exception as e:
            print(f"offset={offset}: ERROR - {str(e)[:80]}")

asyncio.run(test())
