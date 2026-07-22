"""诊断：找出缺失的具体 ID"""
import asyncio
import sys
import os

os.chdir(r"E:\wu\xidian\job\java\agent\CampusCare")
sys.path.insert(0, os.getcwd())

from services.milvus_service import MilvusService

async def test():
    svc = MilvusService()
    await svc.initialize(dim=1024)

    docs = await svc.query_all_documents(batch_size=1000)
    ids = [d["id"] for d in docs]
    nums = sorted([int(i.split("_")[1]) for i in ids])

    # 找出缺失的数字
    all_expected = set(range(0, 866500))
    actual = set(nums)
    missing = sorted(all_expected - actual)
    print(f"loaded {len(docs)}, missing {len(missing)}")
    print(f"missing range: {missing[0]} - {missing[-1]}")

    # 按万位分组看缺失规律
    missing_by_10k = {}
    for m in missing:
        bucket = m // 10000
        missing_by_10k.setdefault(bucket, 0)
        missing_by_10k[bucket] += 1
    print(f"missing by 10k buckets: {missing_by_10k}")

    # 看连续缺失的段落
    gaps = []
    start = missing[0]
    prev = missing[0]
    for m in missing[1:]:
        if m != prev + 1:
            gaps.append((start, prev))
            start = m
        prev = m
    gaps.append((start, prev))
    print(f"missing segments: {len(gaps)}")
    for s, e in gaps[:10]:
        print(f"  {s} - {e} ({e-s+1} records)")
    if len(gaps) > 10:
        print(f"  ... and {len(gaps)-10} more segments")

asyncio.run(test())
