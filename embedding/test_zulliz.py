# test_zulliz.py —— 验证 Milvus 检索连通性
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv; load_dotenv()
from services.milvus_service import MilvusService
from services.text_embedding import embed_input

async def main():
    svc = MilvusService()
    ok = await svc.initialize(dim=768)
    if not ok:
        print("[FAIL] Milvus 连接失败"); return
    print("[OK] Milvus 连接成功")

    # 测试向量检索
    print("\n=== 向量检索测试 ===")
    print("正在加载 BGE-M3 模型（CPU 上约需 1-2 分钟）...")
    from services.text_embedding import create_embedding_model
    m = create_embedding_model()
    print(f"使用 embedding 模型: {m.__class__.__module__}")
    query_vec = embed_input("嗓子疼怎么办")
    print(f"查询向量维度: {len(query_vec)}")
    matches = await svc.query(query_vec, top_k=3)
    print(f"命中 {len(matches)} 条:")
    for m in matches:
        meta = m.get("metadata", {})
        ask = meta.get("ask", "") or meta.get("answer", "") or ""
        print(f"  [{m['score']:.4f}] {ask[:50]}")

    # 测试 TEXT_MATCH 关键词检索
    print("\n=== TEXT_MATCH 关键词检索测试 ===")
    text_results = await svc.text_match_search("嗓子疼", top_k=3)
    print(f"命中 {len(text_results)} 条:")
    for r in text_results:
        ask = r.get("ask", "") or r.get("answer", "") or ""
        print(f"  [{r['score']:.4f}] {ask[:50]}")

    svc.close()

asyncio.run(main())
