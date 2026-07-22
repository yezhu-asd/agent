"""最终验证：cursor 分页结果是否等于 Milvus 真实全量"""
import sys, os
os.chdir(r"E:\wu\xidian\job\java\agent\CampusCare")
sys.path.insert(0, os.getcwd())
from pymilvus import MilvusClient

def test():
    client = MilvusClient(uri="http://localhost:19530")
    cn = "campus_medical_knowledge"

    # 完整 cursor 分页
    all_docs = []
    last_id = ""
    batch_size = 1000
    of = ["id", "content", "ask", "answer", "keywords", "category", "department", "title", "source"]
    while True:
        filt = f'id > "{last_id}"' if last_id else ""
        results = client.query(collection_name=cn, filter=filt, output_fields=of, limit=batch_size)
        if not results:
            break
        all_docs.extend(results)
        last_id = results[-1].get("id", "")
        if len(results) < batch_size:
            break

    loaded_ids = set(int(d["id"].split("_")[1]) for d in all_docs)
    print(f"cursor loaded: {len(all_docs)}")

    # 多次随机抽查，确认没有遗漏可访问的 ID
    import random
    random.seed(42)
    test_nums = random.sample(range(0, 866500), 200)
    found = 0
    missing_in_milvus = []
    for n in test_nums:
        r = client.query(collection_name=cn, filter=f'id in ["vec_{n}"]', output_fields=["id"], limit=1)
        if r:
            found += 1
            if n not in loaded_ids:
                print(f"  FOUND but not in cursor results: vec_{n}")
        else:
            missing_in_milvus.append(n)

    print(f"random sample: {found}/200 exist in Milvus")
    print(f"IDs that exist in Milvus but missed by cursor: check above (should be 0)")
    print(f"IDs not in Milvus at all: {len(missing_in_milvus)}/200")
    print(f"  e.g., {missing_in_milvus[:10]}")

test()
