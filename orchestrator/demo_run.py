#!/usr/bin/env python3
"""
V1 端到端 demo:老板(Orchestrator)派活给员工(codex worker),用技能(Skill)完成任务。
全本地、不出网。验证编排器骨架真跑通。

用法:
  python orchestrator/demo_run.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core import Runtime, Worker, Task
from skills import build_default_registry
from orchestrator import Orchestrator, Workspace


def main():
    print("=" * 55)
    print(" 多Agent测试编排器 V1 — 端到端 demo")
    print("=" * 55)

    # 1. 建运行时 + 员工(检测本机CLI)
    rt = Runtime("local-1")
    print(f"\n[1] 本机CLI: {rt.detect_clis()}")

    codex = Worker("codex-1", "codex", rt)
    claude = Worker("claude-1", "claude", rt)

    # 2. 建工作区 + 老板
    ws = Workspace("target-system")   # 按项目隔离
    orch = Orchestrator(ws)
    print(f"\n[2] 工作区: {ws.dir}")

    # 3. 登记员工
    print("\n[3] 登记员工:")
    orch.register_worker(codex)
    orch.register_worker(claude)

    # 4. 派活:一个真实的缺陷归因任务(输入短、能快速验证编排链路)
    print("\n[4] 派活:")
    orch.submit(Task(
        id="TASK-001",
        type="analyze_defect",
        skill="analyze_defect",
        payload={"failure_info":
                 "用例TC_DEFECT_001: 请求参数为空数组,HTTP状态码=200,"
                 "但响应体 header.code=400 desc='请求参数不能为空'。断言期望HTTP=400,实际200,FAIL。"},
    ))

    # 5. 老板调度执行(串行)
    print("\n[5] 执行:")
    orch.run()

    # 6. 汇总
    print("\n[6] 汇总:")
    summary = orch.summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # 7. 打印员工产出
    for t in orch.tasks:
        if t.result:
            print(f"\n[员工产出 {t.id}]:\n{t.result.strip()[:500]}")

    ws.save_artifact("_summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n汇总已存: {ws.dir}/_summary.json")


if __name__ == "__main__":
    main()
