import asyncio, sys, io
from pathlib import Path

# 设置输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv; load_dotenv()
from services.milvus_service import MilvusService
from services.text_embedding import embed_input

TEST_QUERIES = [
    "嗓子疼怎么办",
    "感冒发烧吃什么药",
    "肚子疼是什么原因",
    "咳嗽有痰吃什么药",
    "头疼怎么缓解",
    "牙疼怎么办",
    "失眠怎么治疗",
    "运动损伤怎么处理",
    "学校医务室开门时间",
    "心理健康咨询",
]

async def main():
    svc = MilvusService()
    ok = await svc.initialize(dim=768)
    if not ok:
        print("[FAIL] Milvus 连接失败"); return
    print("[OK] Milvus 连接成功\n")

    for q in TEST_QUERIES:
        print(f"=" * 60)
        print(f"查询: {q}")
        print(f"=" * 60)
        query_vec = embed_input(q)
        matches = await svc.query(query_vec, top_k=3)
        for i, m in enumerate(matches):
            meta = m.get("metadata", {})
            ask = meta.get("ask", "") or ""
            answer = meta.get("answer", "") or ""
            title = meta.get("title", "") or ""
            keywords = meta.get("keywords", "") or ""
            print(f"\n  [{i+1}] 分数={m['score']:.4f}")
            if title:
                print(f"      标题: {title[:80]}")
            print(f"      问: {ask[:120]}")
            print(f"      答: {answer[:150]}")
            if keywords:
                print(f"      关键词: {keywords[:80]}")
        print()

    svc.close()

asyncio.run(main())
