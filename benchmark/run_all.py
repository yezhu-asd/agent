"""
Benchmark 统一入口 — 依次运行所有 benchmark

用法：
    python benchmark/run_all.py [--skip-quality] [--quick]

    --skip-quality  跳过问诊质量 LLM 评判（classify 模块）
    --quick         只跑分类 + 预约（快），跳过追问和 RAG
"""
import asyncio
import subprocess
import sys
import io
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BENCH_DIR = Path(__file__).parent


def run_script(name: str, extra_args=None):
    """运行单个 benchmark 脚本"""
    args = [sys.executable, str(BENCH_DIR / name)]
    if extra_args:
        args.extend(extra_args)
    print(f"\n{'='*60}")
    print(f"▶ 运行 {name}")
    print(f"{'='*60}")
    result = subprocess.run(args, cwd=str(BENCH_DIR))
    return result.returncode


def main():
    skip_quality = "--skip-quality" in sys.argv
    quick = "--quick" in sys.argv

    scripts = ["bench_classify.py", "bench_appointment.py"]
    if not quick:
        scripts.extend(["bench_followup.py", "bench_retrieval.py"])

    exit_codes = []
    for script in scripts:
        extra = ["--skip-quality"] if (script == "bench_classify.py" and skip_quality) else None
        code = run_script(script, extra)
        exit_codes.append((script, code))

    print(f"\n{'='*60}")
    print("Benchmark 全部完成")
    print(f"{'='*60}")
    for script, code in exit_codes:
        status = "✅" if code == 0 else "❌"
        print(f"  {status} {script}")


if __name__ == "__main__":
    main()
