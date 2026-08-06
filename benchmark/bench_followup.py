"""
多轮追问流程 Benchmark — 评估症状追问是否合理、能否收敛

指标：
1. 追问轮次：复杂症状应 2-3 轮，不应无限问或 0 轮就草率给建议
2. 流程收敛：是否在合理轮次内收集足够信息并给建议
3. 追问质量：追问是否针对鉴别诊断关键信息（位置/性质/时长）

用法：
    python benchmark/bench_followup.py
"""
import asyncio
import json
import sys
import io
import re
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def load_cases():
    path = Path(__file__).parent / "data" / "followup_cases.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def count_rounds(full_response: str) -> int:
    """统计追问轮次（通过问号数量粗略判断）"""
    return full_response.count("？") + full_response.count("?")


def has_followup(response: str) -> bool:
    """判断是否在追问（区分于给建议/总结）"""
    # 追问特征：问具体信息（位置/性质/时长/伴随）
    followup_markers = [
        "是哪", "是绞痛", "是胀痛", "是刺痛", "是干咳", "是有痰", "持续了多久",
        "持续多久", "哪个部位", "哪个位置", "左边还是右边", "伴随", "有没有",
        "是持续", "是入睡困难", "主要在哪", "主要在哪个", "是疼痛还是",
        "请告知", "请描述",
    ]
    # 建议/收敛特征
    give_advice = any(m in response for m in [
        "建议", "就医", "预约", "温馨提示", "祝你", "祝您",
        "需不需要我帮您预约", "感谢您的咨询",
    ])
    if give_advice:
        return False
    return any(m in response for m in followup_markers)


async def run_followup(case):
    """模拟一次完整追问对话，返回轮次记录"""
    from agents.consultant_agent import ConsultantAgent

    conv = f"bench_followup_{case['symptom']}"
    agent = ConsultantAgent(user_id="bench_user", conversation_id=conv)

    rounds = []
    # 第一轮：用户报症状
    responses = []
    async for token in agent.consult_stream(case["symptom"]):
        responses.append(token)
    first_resp = "".join(responses)
    rounds.append({"turn": "user_symptom", "bot": first_resp[:120]})

    # 后续轮：模拟用户回答追问
    for i, answer in enumerate(case["answers"]):
        responses = []
        async for token in agent.consult_stream(answer):
            responses.append(token)
        resp = "".join(responses)
        rounds.append({"turn": f"user_answer_{i+1}", "bot": resp[:120]})
        # 若不再追问（给建议/问预约），停止
        if not has_followup(resp):
            break

    return rounds


def evaluate(cases, all_rounds):
    """评估每例的追问质量"""
    eval_results = []
    for case, rounds in zip(cases, all_rounds):
        # 轮次 = 除第一轮外的 bot 回复数（每次追问算一轮）
        followup_rounds = max(0, len(rounds) - 1)
        # 是否收敛（最后一轮不再追问）
        converged = len(rounds) > 0 and not has_followup(rounds[-1]["bot"])

        eval_results.append({
            "symptom": case["symptom"],
            "rounds": followup_rounds,
            "converged": converged,
            "total_turns": len(rounds),
            "last_response": rounds[-1]["bot"][:80] if rounds else "",
        })
    return eval_results


def build_report(eval_results):
    lines = []
    sep = "=" * 60
    lines.append(sep)
    lines.append("多轮追问流程 Benchmark 报告")
    lines.append(sep)

    lines.append(f"\n💬 追问轮次统计")
    lines.append(f"  用例数: {len(eval_results)}")
    rounds_list = [r["rounds"] for r in eval_results]
    avg_rounds = sum(rounds_list) / len(rounds_list)
    lines.append(f"  平均追问轮次: {avg_rounds:.1f}")
    lines.append(f"  轮次分布: {dict(sorted({r: rounds_list.count(r) for r in set(rounds_list)}.items()))}")

    converged = sum(1 for r in eval_results if r["converged"])
    lines.append(f"\n🎯 流程收敛率: {converged}/{len(eval_results)} = {converged/len(eval_results)*100:.1f}%")

    # 轮次合理性（1-3 轮为合理）
    reasonable = [r for r in eval_results if 1 <= r["rounds"] <= 3]
    lines.append(f"\n✅ 轮次合理(1-3轮): {len(reasonable)}/{len(eval_results)} = {len(reasonable)/len(eval_results)*100:.1f}%")
    for r in eval_results:
        if r["rounds"] > 3:
            lines.append(f"  ⚠️ '{r['symptom']}' 追问过多: {r['rounds']} 轮")
        if r["rounds"] == 0:
            lines.append(f"  ⚠️ '{r['symptom']}' 未追问直接给建议")

    lines.append("\n📋 明细:")
    for r in eval_results:
        mark = "✅" if r["converged"] else "❌"
        lines.append(f"  {mark} '{r['symptom']}' → {r['rounds']}轮 收敛={r['converged']} | 末轮: {r['last_response'][:50]}")

    lines.append("\n" + sep)
    return "\n".join(lines)


async def main():
    print("📋 加载追问用例...")
    cases = load_cases()
    print(f"  共 {len(cases)} 条")

    print("\n💬 模块: 多轮追问流程...")
    all_rounds = []
    for i, case in enumerate(cases):
        rounds = await run_followup(case)
        all_rounds.append(rounds)
        print(f"  [{i+1}/{len(cases)}] {case['symptom']} 完成")

    eval_results = evaluate(cases, all_rounds)
    report = build_report(eval_results)
    print(report)

    from utils.reporter import save_report
    save_report("followup", report, {
        "case_count": len(cases),
        "results": eval_results,
    })


if __name__ == "__main__":
    asyncio.run(main())
