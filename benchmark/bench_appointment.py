"""
预约流程 Benchmark — 评估预约信息解析质量

指标：
1. 科室提取准确率：用户说的科室是否正确提取（project）
2. 性别提取准确率：用户说的性别是否正确提取（gender）
3. 字段臆造率：用户没提供的信息是否被错误填充（关键：JSON Mode 效果）
4. 时间识别准确率：有时间的用例是否正确识别

用法：
    python benchmark/bench_appointment.py
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
    path = Path(__file__).parent / "data" / "appointment_cases.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


async def eval_appointment(cases):
    """用 InputParser 跑预约解析，对比提取结果与期望"""
    from agents.appointment_agent import AppointmentAgent

    results = []
    for i, case in enumerate(cases):
        conv = f"bench_apt_{i}"
        agent = AppointmentAgent(user_id="bench_user", conversation_id=conv)
        parser = agent.input_parser
        chat = agent._get_chat_history(f"apt_sess_{i}")

        try:
            ai = ""
            for token in parser.parse_stream(case["query"], chat):
                ai += token
            data = parser.parse_data(ai)

            result = {
                "query": case["query"],
                "project": data.get("project", "未知"),
                "gender": data.get("gender", "未知"),
                "start_time": data.get("start_time", "未知"),
            }
            results.append(result)
        except Exception as e:
            results.append({"query": case["query"], "error": str(e)})

    return results


def evaluate(results, cases):
    """评估提取质量"""
    eval = []
    for r, case in zip(results, cases):
        if "error" in r:
            eval.append({"query": r["query"], "correct": False, "reason": f"错误: {r['error']}"})
            continue

        issues = []

        # 1. 科室提取
        exp_project = case.get("expected_project")
        if exp_project:
            if r["project"] != exp_project:
                issues.append(f"科室: 期望{exp_project}, 实际{r['project']}")

        # 2. 性别提取
        exp_gender = case.get("expected_gender")
        if exp_gender:
            if r["gender"] != exp_gender:
                issues.append(f"性别: 期望{exp_gender}, 实际{r['gender']}")

        # 3. 字段臆造：期望为 null 的字段（用户没提供）不应被填充
        if case.get("expected_project") is None and r["project"] != "未知":
            issues.append(f"臆造科室: {r['project']}")
        if case.get("expected_gender") is None and r["gender"] != "未知":
            issues.append(f"臆造性别: {r['gender']}")

        # 4. 时间识别
        if case.get("has_time") and r["start_time"] == "未知":
            issues.append("漏识别时间")
        if not case.get("has_time") and r["start_time"] != "未知":
            issues.append(f"臆造时间: {r['start_time']}")

        eval.append({
            "query": r["query"],
            "correct": len(issues) == 0,
            "issues": issues,
            "extracted": {"project": r["project"], "gender": r["gender"], "start_time": r["start_time"]},
        })
    return eval


def build_report(eval_results):
    lines = []
    sep = "=" * 60
    lines.append(sep)
    lines.append("预约流程 Benchmark 报告")
    lines.append(sep)

    total = len(eval_results)
    correct = sum(1 for r in eval_results if r["correct"])
    lines.append(f"\n📅 预约信息解析准确率")
    lines.append(f"  总体: {correct}/{total} = {correct/total*100:.1f}%")

    # 臆造统计
    hallucination = [r for r in eval_results if any("臆造" in i for i in r.get("issues", []))]
    lines.append(f"\n🧠 字段臆造率: {len(hallucination)}/{total} = {len(hallucination)/total*100:.1f}%")
    for r in hallucination:
        lines.append(f"    ❌ '{r['query'][:20]}' → {r['issues']}")

    # 错误详情
    errors = [r for r in eval_results if not r["correct"]]
    lines.append(f"\n❌ 提取错误 ({len(errors)} 条):")
    for r in errors:
        lines.append(f"    '{r['query'][:20]}' → {r['issues']}")

    lines.append("\n📋 提取明细:")
    for r in eval_results:
        mark = "✅" if r["correct"] else "❌"
        e = r.get("extracted", {})
        lines.append(f"  {mark} '{r['query'][:18]}' → 科室={e.get('project','?')} 性别={e.get('gender','?')} 时间={e.get('start_time','?')}")

    lines.append("\n" + sep)
    return "\n".join(lines)


async def main():
    print("📋 加载预约用例...")
    cases = load_cases()
    print(f"  共 {len(cases)} 条")

    print("\n📅 模块: 预约信息解析...")
    results = await eval_appointment(cases)

    eval_results = evaluate(results, cases)
    report = build_report(eval_results)
    print(report)

    from utils.reporter import save_report
    save_report("appointment", report, {
        "case_count": len(cases),
        "results": eval_results,
    })


if __name__ == "__main__":
    asyncio.run(main())
