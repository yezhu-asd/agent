"""验证 gap fix 方案所需的 Milvus 语法"""
import asyncio
import sys
import os

os.chdir(r"E:\wu\xidian\job\java\agent\CampusCare")
sys.path.insert(0, os.getcwd())

from pymilvus import MilvusClient

def test():
    client = MilvusClient(uri="http://localhost:19530")
    cn = "campus_medical_knowledge"
    of = ["id", "content", "ask", "answer", "keywords", "category", "department", "title", "source"]

    # 测试 1: id in [...] 过滤
    print("=== Test 1: id in [...] ===")
    try:
        r = client.query(
            collection_name=cn,
            filter='id in ["vec_0", "vec_112000", "vec_99999"]',
            output_fields=["id"],
            limit=10,
        )
        print(f"OK: {len(r)} results: {[x['id'] for x in r]}")
    except Exception as e:
        print(f"ERROR: {str(e)[:100]}")

    # 测试 2: 复杂 AND/OR 过滤
    print("\n=== Test 2: OR 复杂过滤 ===")
    try:
        # 构造 3 个 gap 范围的 OR
        r = client.query(
            collection_name=cn,
            filter='(id >= "vec_112000" && id <= "vec_113999") || (id >= "vec_138000" && id <= "vec_139999")',
            output_fields=["id"],
            limit=5,
        )
        print(f"OK: {len(r)} results")
    except Exception as e:
        print(f"ERROR: {str(e)[:100]}")

    # 测试 3: 单个 gap 范围 (2000 条，在 16384 以内)
    print("\n=== Test 3: single gap range ===")
    try:
        r = client.query(
            collection_name=cn,
            filter='id >= "vec_112000" && id <= "vec_113999"',
            output_fields=["id"],
            limit=3000,
        )
        nums = sorted([int(x["id"].split("_")[1]) for x in r])
        print(f"OK: {len(r)} results, range {nums[0]}-{nums[-1]}")
        # 检查是否有非目标ID混入了
        out_of_range = [n for n in nums if not (112000 <= n <= 113999)]
        print(f"out of range: {out_of_range[:5]} ({len(out_of_range)} total)")
    except Exception as e:
        print(f"ERROR: {str(e)[:100]}")

    # 测试 4: id in большого 列表 (2000 个)
    print("\n=== Test 4: id in large list ===")
    try:
        ids = [f"vec_{i}" for i in range(112000, 114000)]
        id_list = ", ".join(f'"{i}"' for i in ids)
        r = client.query(
            collection_name=cn,
            filter=f'id in [{id_list}]',
            output_fields=["id"],
            limit=3000,
        )
        nums = sorted([int(x["id"].split("_")[1]) for x in r])
        print(f"OK: {len(r)} results, range {nums[0]}-{nums[-1]}")
        # 检查完整性
        expected = set(range(112000, 114000))
        actual = set(nums)
        missing = expected - actual
        print(f"missing: {len(missing)} (e.g., {sorted(missing)[:5]})")
    except Exception as e:
        print(f"ERROR: {str(e)[:100]}")

test()
