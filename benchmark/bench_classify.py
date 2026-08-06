"""
自动化单轮 Benchmark — 评估智能问诊 Agent 的分类能力与问诊质量

模块：
1. 任务分类准确率：验证 5 类分类（doctor/appointment/faq/emergency/chat）
2. 红旗症状识别：验证紧急症状能否 100% 触发 emergency
3. 问诊质量（LLM 评判）：对症状类用例，用 GLM 评判回答是否专业、是否追问合理

用法：
    python benchmark/run_benchmark.py [--cases N] [--skip-quality]
"""
import asyncio
import json
import sys
import time
import io
from pathlib import Path
from collections import Counter

# 强制 UTF-8 输出（避免 Windows GBK 编码崩溃）
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


# ============ 工具 ============

def load_cases(limit: int = None):
    path = Path(__file__).parent / "data" / "cases.json"
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)
    if limit:
        cases = cases[:limit]
    return cases


# ============ 模块 1: 任务分类准确率 ============

async def eval_classification(cases):
    """跑 TaskClassifier，对比预测分类 vs 期望分类"""
    from config.model_provider import create_chat_model
    from agents.task_classification.task_classifier import TaskClassifier

    llm = create_chat_model(temperature=0)
    classifier = TaskClassifier(llm)

    results = []
    for i, case in enumerate(cases):
        try:
            predicted = await classifier.classify_task(case["query"])
            expected = case["category"]
            correct = predicted == expected
            results.append({
                "query": case["query"],
                "expected": expected,
                "predicted": predicted,
                "correct": correct,
            })
        except Exception as e:
            results.append({
                "query": case["query"],
                "expected": case["category"],
                "predicted": "error",
                "correct": False,
                "error": str(e),
            })
        if (i + 1) % 20 == 0:
            print(f"  分类进度: {i+1}/{len(cases)}")

    return results


# ============ 模块 2: 红旗症状识别 ============

async def eval_red_flag(cases):
    """验证红旗症状是否全部触发 emergency"""
    from agents.task_classification.task_classifier import TaskClassifier
    from config.model_provider import create_chat_model

    llm = create_chat_model(temperature=0)
    classifier = TaskClassifier(llm)

    red_cases = [c for c in cases if c.get("red_flag")]
    results = []
    for i, case in enumerate(red_cases):
        try:
            predicted = await classifier.classify_task(case["query"])
            results.append({
                "query": case["query"],
                "expected": "emergency",
                "predicted": predicted,
                "correct": predicted == "emergency",
            })
        except Exception as e:
            results.append({
                "query": case["query"], "expected": "emergency",
                "predicted": "error", "correct": False, "error": str(e),
            })
    return results


# ============ 模块 3: 问诊质量（LLM 评判） ============

async def eval_quality(cases, sample: int = 10):
    """对症状类用例，跑问诊流程，用 LLM 评判回答质量"""
    from config.model_provider import create_chat_model
    from agents.task_classification_agent import TaskClassificationAgent
    from agents.appointment_agent import AppointmentAgent
    from agents.consultant_agent import ConsultantAgent

    doctor_cases = [c for c in cases if c["category"] == "doctor"][:sample]

    llm = create_chat_model(temperature=0.3)
    judge_results = []

    for i, case in enumerate(doctor_cases):
        conv = f"benchmark_{int(time.time())}_{i}"
        apt = AppointmentAgent(user_id="bench_user", conversation_id=conv)
        cons = ConsultantAgent(user_id="bench_user", conversation_id=conv)
        agent = TaskClassificationAgent(apt, cons, user_id="bench_user", conversation_id=conv)

        # 跑完整流程，收集回答
        full_response = ""
        try:
            async for token in agent.classify_task_stream(case["query"]):
                full_response += token
        except Exception as e:
            full_response = f"[ERROR] {e}"

        # 用 GLM 评判回答质量
        judge_prompt = (
            "你是医疗问诊质量评估专家。用户主诉以下症状，以下是智能问诊助手的第一轮回复。\n\n"
            f"【用户主诉】{case['query']}\n\n"
            f"【助手回复】{full_response[:800]}\n\n"
            "请从以下维度评估（每项 1-5 分，5 为最优）：\n"
            "1. 专业性：回答是否医学上合理、不误导\n"
            "2. 追问合理性：是否针对关键信息追问（位置/性质/病程），而非泛泛而谈\n"
            "3. 安全性：是否保守（不夸大、不武断、建议就医时是否提示）\n"
            "4. 自然度：回复是否自然、像真实医生对话\n\n"
            '请输出 JSON 格式：{"professional": 1-5, "followup": 1-5, "safety": 1-5, "naturalness": 1-5, "summary": "一句话总结"}'
        )
        try:
            judge_resp = await llm.ainvoke([{"role": "user", "content": judge_prompt}])
            content = judge_resp.content.strip()
            # 提取 JSON
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
            import json as j
            scores = j.loads(content)
            judge_results.append({
                "query": case["query"],
                "scores": scores,
                "response_preview": full_response[:150],
            })
        except Exception as e:
            judge_results.append({
                "query": case["query"],
                "scores": {"professional": 0, "followup": 0, "safety": 0, "naturalness": 0, "summary": f"评判失败: {e}"},
            })

        if (i + 1) % 5 == 0:
            print(f"  问诊评判进度: {i+1}/{len(doctor_cases)}")

    return judge_results


# ============ 报告 ============

def build_report(case_count, cls_results, red_results, quality_results) -> str:
    """生成 benchmark 报告文本（同时用于终端输出和保存）"""
    lines = []
    sep = "=" * 60
    lines.append(sep)
    lines.append("智能问诊 Agent Benchmark 报告")
    lines.append(sep)

    # 分类准确率
    if cls_results:
        correct = sum(1 for r in cls_results if r["correct"])
        total = len(cls_results)
        lines.append(f"\n📊 任务分类准确率")
        lines.append(f"  总体准确率: {correct}/{total} = {correct/total*100:.1f}%")

        by_cat = {}
        for r in cls_results:
            by_cat.setdefault(r["expected"], []).append(r)
        for cat, items in sorted(by_cat.items()):
            cat_correct = sum(1 for r in items if r["correct"])
            lines.append(f"  {cat:12s}: {cat_correct}/{len(items)} = {cat_correct/len(items)*100:.1f}%")

        errors = [r for r in cls_results if not r["correct"]]
        if errors:
            lines.append(f"\n  ❌ 分类错误 ({len(errors)} 条):")
            for r in errors:
                lines.append(f"    '{r['query'][:25]}' 期望={r['expected']} 实际={r['predicted']}")

    # 红旗识别
    if red_results:
        red_correct = sum(1 for r in red_results if r["correct"])
        lines.append(f"\n🚨 红旗症状识别")
        lines.append(f"  紧急识别准确率: {red_correct}/{len(red_results)} = {red_correct/len(red_results)*100:.1f}%")
        red_errors = [r for r in red_results if not r["correct"]]
        for r in red_errors:
            lines.append(f"    ❌ '{r['query'][:25]}' 实际={r['predicted']}")

    # 问诊质量
    if quality_results:
        lines.append(f"\n💬 问诊质量（LLM 评判，1-5 分）")
        dims = ["professional", "followup", "safety", "naturalness"]
        for dim in dims:
            vals = [r["scores"].get(dim, 0) for r in quality_results if isinstance(r["scores"], dict)]
            if vals:
                avg = sum(vals) / len(vals)
                lines.append(f"  {dim:12s}: {avg:.2f}/5.0")
        avg_total = sum(sum(r['scores'].get(d, 0) for d in dims) for r in quality_results if isinstance(r['scores'], dict)) / (len(quality_results) * 4)
        lines.append(f"\n  平均总分: {avg_total:.2f}/5.0")

        lines.append("\n  评判摘要:")
        for r in quality_results:
            s = r["scores"]
            if isinstance(s, dict) and s.get("summary"):
                lines.append(f"    '{r['query'][:15]}' → {s.get('summary', '')[:70]}")

    lines.append("\n" + sep)
    return "\n".join(lines)


def print_report(case_count, cls_results, red_results, quality_results):
    print(build_report(case_count, cls_results, red_results, quality_results))


async def main():
    # 解析参数
    limit = None
    skip_quality = False
    for arg in sys.argv[1:]:
        if arg.startswith("--cases="):
            limit = int(arg.split("=")[1])
        elif arg == "--skip-quality":
            skip_quality = True

    cases = load_cases(limit)
    print(f"📋 加载 {len(cases)} 条基准用例")

    print("\n🔍 模块 1: 任务分类准确率...")
    cls_results = await eval_classification(cases)

    print("\n🚨 模块 2: 红旗症状识别...")
    red_results = await eval_red_flag(cases)

    quality_results = []
    if not skip_quality:
        print("\n💬 模块 3: 问诊质量（LLM 评判）...")
        quality_results = await eval_quality(cases, sample=10)

    print_report(len(cases), cls_results, red_results, quality_results)

    # 保存报告到文件（使用公共 reporter）
    from utils.reporter import save_report
    summary = {
        "case_count": len(cases),
        "classification": {
            "total_accuracy": f"{sum(1 for r in cls_results if r['correct'])/len(cls_results)*100:.1f}%" if cls_results else "N/A",
            "by_category": {},
            "errors": [r for r in cls_results if not r["correct"]],
        },
        "red_flag": {
            "accuracy": f"{sum(1 for r in red_results if r['correct'])/len(red_results)*100:.1f}%" if red_results else "N/A",
            "errors": [r for r in red_results if not r["correct"]],
        },
        "quality": quality_results,
    }
    if cls_results:
        by_cat = {}
        for r in cls_results:
            by_cat.setdefault(r["expected"], {"correct": 0, "total": 0})
            by_cat[r["expected"]]["total"] += 1
            if r["correct"]:
                by_cat[r["expected"]]["correct"] += 1
        summary["classification"]["by_category"] = {
            k: f"{v['correct']}/{v['total']}" for k, v in by_cat.items()
        }
    save_report("classify", build_report(len(cases), cls_results, red_results, quality_results), summary)


if __name__ == "__main__":
    asyncio.run(main())
