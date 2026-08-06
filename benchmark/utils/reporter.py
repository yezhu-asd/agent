"""
Benchmark 公共报告工具 — 统一报告生成与保存逻辑

所有 benchmark 脚本通过 save_report() 保存结果，命名规则：
  reports/<bench_type>_<时间戳>.md   (人类可读报告)
  reports/<bench_type>_<时间戳>.json (结构化数据)
"""
import json
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path(__file__).parent.parent / "reports"


def save_report(bench_type: str, report_text: str, summary: dict):
    """保存 benchmark 报告到 reports/ 目录

    Args:
        bench_type: 基准类型（classify/appointment/followup/retrieval）
        report_text: Markdown 报告文本
        summary: 结构化数据 dict
    """
    REPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    md_file = REPORTS_DIR / f"{bench_type}_{ts}.md"
    json_file = REPORTS_DIR / f"{bench_type}_{ts}.json"

    md_file.write_text(report_text, encoding="utf-8")
    summary["timestamp"] = datetime.now().isoformat()
    summary["bench_type"] = bench_type
    json_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n💾 报告已保存:")
    print(f"  {md_file}")
    print(f"  {json_file}")
    return md_file, json_file
