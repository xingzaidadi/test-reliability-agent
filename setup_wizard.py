#!/usr/bin/env python3
"""
上手向导 —— 让新用户/同事不用教就能跑起来。
做三件事:①环境自检 ②交互式配置(生成.env) ③给出下一步命令。

用法:
  python setup_wizard.py            # 交互式配置
  python setup_wizard.py --check    # 只自检,不配置
"""

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent
GREEN, RED, YELLOW, CYAN, BOLD, RST = "\033[32m","\033[31m","\033[33m","\033[36m","\033[1m","\033[0m"
def c(color, s): return f"{color}{s}{RST}" if sys.platform != "win32" else s
def ok(s): print(f"  [OK]   {s}")
def bad(s): print(f"  [MISS] {s}")
def warn(s): print(f"  [WARN] {s}")


def check_env():
    """环境自检:Python版本、依赖、LLM CLI。返回是否全通过。"""
    print("\n=== 环境自检 ===")
    all_ok = True

    # Python 版本
    v = sys.version_info
    if v >= (3, 9):
        ok(f"Python {v.major}.{v.minor}")
    else:
        bad(f"Python {v.major}.{v.minor}(需 >=3.9)"); all_ok = False

    # 依赖
    for mod in ("yaml", "playwright"):
        try:
            __import__(mod); ok(f"依赖 {mod}")
        except ImportError:
            if mod == "playwright":
                warn(f"依赖 {mod} 未装(仅UI测试需要,可跳过)")
            else:
                bad(f"依赖 {mod} 未装 → 运行: pip install pyyaml"); all_ok = False

    # LLM CLI(生成/编排需要)
    found = []
    for cli in ("codex", "claude"):
        if shutil.which(cli):
            ok(f"LLM CLI: {cli}"); found.append(cli)
    if not found:
        warn("未检测到 codex/claude CLI(用例生成/编排需要;仅执行现成用例可不装)")

    return all_ok


def wizard():
    """交互式配置,生成 .env。"""
    print("\n=== 配置向导 ===")
    print("(直接回车用默认值/占位;敏感值只写进本地.env,不进git)\n")

    fields = [
        ("TARGET_SYSTEM_BASE_URL", "目标系统测试环境 base url", "https://your-host.example.com/api"),
        ("TARGET_SYSTEM_APPKEY",   "网关签名 appkey(如需)", ""),
        ("TARGET_SYSTEM_SOURCE_PATH", "目标系统源码路径(需求推导/单测生成需要)", ""),
    ]
    lines = ["# 本文件由 setup_wizard.py 生成。已在 .gitignore 中,不会提交。\n"]
    for key, desc, default in fields:
        try:
            val = input(f"  {desc}\n    {key} [{default or '留空'}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            val = ""
        lines.append(f"{key}={val or default}")

    env_path = ROOT / ".env"
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n  已生成: {env_path}")
    print("  用前先加载: (bash) export $(cat .env | xargs)   或手动 export")


def next_steps():
    print("\n=== 下一步 ===")
    print("  1. 加载配置:  export $(grep -v '^#' .env | xargs)")
    print("  2. 一键全流程: python pipeline.py --issue ISSUE-001")
    print("  3. 单独跑某段:")
    print("     - 需求驱动:  python orchestrator/demo_requirement.py")
    print("     - 充分性:    python tools/sufficiency/sufficiency_pipeline.py --spec ... --cases ... --patterns ...")
    print("     - 执行:      python cli/test_squad.py run-api --issue ISSUE-001")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只自检")
    args = ap.parse_args()

    print(f"\n{'='*50}")
    print("  测试可靠性平台 — 上手向导")
    print(f"{'='*50}")

    env_ok = check_env()
    if args.check:
        print(f"\n{'环境就绪' if env_ok else '有缺失项,按提示补齐'}")
        return 0 if env_ok else 1

    wizard()
    next_steps()
    print(f"\n{'='*50}\n  配置完成,可以开跑了\n{'='*50}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
