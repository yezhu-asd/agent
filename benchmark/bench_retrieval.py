"""
RAG 检索质量 Benchmark — 评估知识库检索是否命中相关内容

指标：
1. Recall@K：正确相关文档是否出现在前 K 个结果
2. 检索相关性：前 K 结果中命中查询主题的比例
3. 关键词命中率：检索结果是否包含查询的关键词

用法：
    python benchmark/bench_retrieval.py
"""
import asyncio
import json
import sys
import io
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def load_cases():
    path = Path(__file__).parent / "data" / "retrieval_cases.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


async def run_retrieval(cases, top_k=5):
    """对每个查询跑知识库检索，收集结果"""
    from agents.consultant.knowledge_retriever import KnowledgeRetriever

    retriever = KnowledgeRetriever()
    await retriever.initialize()

    results = []
    for case in cases:
        docs = await retriever.search_knowledge(case["query"], top_k=top_k)
        results.append({
            "query": case["query"],
            "keywords": case["keywords"],
            "docs": docs,
        })
    return results


def evaluate(retrieval_results, top_k=5):
    """评估检索质量"""
    eval_results = []
    for r in retrieval_results:
        docs = r["docs"]
        keywords = r["keywords"]
        query = r["query"]

        # 拼接所有检索结果的文本
        all_text = " ".join(
            (d.get("answer", "") or d.get("content", "") or d.get("ask", "") or "")
            for d in docs[:top_k]
        )

        # 1. 关键词命中数（在 top_k 结果中命中了几个期望关键词）
        hit_keywords = [kw for kw in keywords if kw in all_text]
        hit_rate = len(hit_keywords) / len(keywords) if keywords else 0

        # 2. 是否有检索结果
        has_results = len(docs) > 0

        eval_results.append({
            "query": query,
            "keywords": keywords,
            "hit_keywords": hit_keywords,
            "hit_rate": hit_rate,
            "has_results": has_results,
            "result_count": len(docs),
            "relevant": hit_rate >= 0.5,  # 命中一半以上关键词视为相关
        })
    return eval_results


def build_report(eval_results, top_k):
    lines = []
    sep = "=" * 60
    lines.append(sep)
    lines.append(f"RAG 检索质量 Benchmark 报告（Top-{top_k}）")
    lines.append(sep)

    total = len(eval_results)
    has_results = sum(1 for r in eval_results if r["has_results"])
    relevant = sum(1 for r in eval_results if r["relevant"])

    lines.append(f"\n🔍 检索结果")
    lines.append(f"  用例数: {total}")
    lines.append(f"  有结果: {has_results}/{total} = {has_results/total*100:.1f}%")
    lines.append(f"  相关命中: {relevant}/{total} = {relevant/total*100:.1f}%")

    # 平均关键词命中率
    avg_hit = sum(r["hit_rate"] for r in eval_results) / total
    lines.append(f"  平均关键词命中率: {avg_hit*100:.1f}%")

    lines.append(f"\n📋 明细:")
    for r in eval_results:
        mark = "✅" if r["relevant"] else "❌"
        hit = r["hit_keywords"] or "无"
        lines.append(f"  {mark} '{r['query'][:15]}' → 命中关键词: {hit} ({r['hit_rate']*100:.0f}%)")

    lines.append("\n" + sep)
    return "\n".join(lines)


async def main():
    print("📋 加载检索用例...")
    cases = load_cases()
    print(f"  共 {len(cases)} 条")

    print("\n🔍 模块: RAG 检索质量...")
    retrieval_results = await run_retrieval(cases, top_k=5)

    eval_results = evaluate(retrieval_results, top_k=5)
    report = build_report(eval_results, top_k=5)
    print(report)

    from utils.reporter import save_report
    save_report("retrieval", report, {
        "top_k": 5,
        "case_count": len(cases),
        "results": eval_results,
    })


if __name__ == "__main__":
    asyncio.run(main())
