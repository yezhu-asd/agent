"""验证缺失的 ID 是否真实存在于 Milvus 中"""
import sys, os
os.chdir(r"E:\wu\xidian\就业\java\agent项目\smart-appointment-ai-agent-master")
sys.path.insert(0, os.getcwd())
from pymilvus import MilvusClient

def test():
    client = MilvusClient(uri="http://localhost:19530")
    cn = "campus_medical_knowledge"

    # 直接查缺失范围内的 ID 是否存在
    test_ids = ["vec_112000", "vec_113999", "vec_138000", "vec_664000", "vec_667999"]
    id_list = ", ".join(f'"{i}"' for i in test_ids)
    r = client.query(collection_name=cn, filter=f'id in [{id_list}]', output_fields=["id"], limit=10)
    print(f"Direct query for gap IDs: {len(r)} found: {[x['id'] for x in r]}")

    # 查存在的 ID 做对照
    ctrl_ids = ["vec_111999", "vec_114000", "vec_137999", "vec_140000", "vec_663999", "vec_668000"]
    id_list2 = ", ".join(f'"{i}"' for i in ctrl_ids)
    r2 = client.query(collection_name=cn, filter=f'id in [{id_list2}]', output_fields=["id"], limit=10)
    print(f"Direct query for existing IDs: {len(r2)} found: {[x['id'] for x in r2]}")

    # 用 cursor 方式读出 vec_111999 后面的内容，看实际是什么
    r3 = client.query(collection_name=cn, filter='id > "vec_111999"', output_fields=["id"], limit=10)
    print(f"\nAfter vec_111999 (first 10): {[x['id'] for x in r3]}")

    r4 = client.query(collection_name=cn, filter='id > "vec_113999"', output_fields=["id"], limit=10)
    print(f"After vec_113999 (first 10): {[x['id'] for x in r4]}")

    # 检查 vec_112 后面跟着什么
    r5 = client.query(collection_name=cn, filter='id > "vec_112"', output_fields=["id"], limit=15)
    print(f"After vec_112 (first 15): {[x['id'] for x in r5]}")

test()
