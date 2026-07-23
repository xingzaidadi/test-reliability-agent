#!/usr/bin/env python3
"""
V2 端到端 demo:autopilot触发 → DAG任务(依赖) → squad委派 → 并发/依赖执行。
展示 V2 全部新能力:Task依赖DAG + Squad委派 + Autopilot触发。
全本地、不出网。

用法: python orchestrator/demo_run_v2.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core import Runtime, Worker, Task, Squad
from skills import build_default_registry
from orchestrator import Orchestrator, Workspace
from autopilot import Autopilot, AutopilotRegistry


def main():
    print("=" * 58)
    print(" 多Agent测试编排器 V2 — DAG + Squad + Autopilot")
    print("=" * 58)

    rt = Runtime("local-1")
    codex = Worker("codex-1", "codex", rt)
    codex2 = Worker("codex-2", "codex", rt)   # 第二个员工,演示squad多成员

    ws = Workspace("target-system-v2")
    orch = Orchestrator(ws)

    print("\n[1] 登记员工 + 小队:")
    orch.register_worker(codex)
    orch.register_worker(codex2)
    # Squad:归因队(两个codex成员,leader委派)
    squad = Squad("归因队", members=[codex, codex2])
    orch.register_squad(squad)

    # [2] Autopilot:manual触发,生成一条 DAG 链
    #   T1(归因缺陷A) 和 T2(归因缺陷B) 无依赖 → 并发
    #   T3(汇总) 依赖 T1+T2 → 等它俩完成,拿它们产出
    print("\n[2] 定义 Autopilot(生成DAG任务链):")

    def task_factory():
        t1 = Task(id="T1", type="analyze_defect", skill="analyze_defect",
                  assigned_to="归因队",
                  payload={"failure_info": "TC_A: HTTP=200但header.code=400,断言期望HTTP400,FAIL"})
        t2 = Task(id="T2", type="analyze_defect", skill="analyze_defect",
                  assigned_to="归因队",
                  payload={"failure_info": "TC_B: 连接超时,status_code=0,error=timeout"})
        # T3 依赖 T1、T2:汇总两条归因(拿它们的产出)
        t3 = Task(id="T3", type="analyze_defect", skill="analyze_defect",
                  assigned_to="codex-1",
                  depends_on=["T1", "T2"],
                  payload={"failure_info": "汇总上面两条归因结论,用一句话概括本轮测试的主要风险"})
        return [t1, t2, t3]

    ap_reg = AutopilotRegistry()
    ap = Autopilot(name="daily_defect_triage", trigger="manual",
                   task_factory=task_factory,
                   description="触发一轮缺陷归因(演示DAG+并发+依赖)")
    ap_reg.register(ap)

    print("\n[3] 触发 Autopilot:")
    ap.fire(orch)

    print("\n[4] DAG 执行(T1/T2并发 → T3依赖它俩):")
    orch.run(max_workers=2)

    print("\n[5] 汇总:")
    summary = orch.summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n[6] T3(依赖T1+T2的汇总任务)拿到的上游产出:")
    t3 = next(t for t in orch.tasks if t.id == "T3")
    deps = t3.payload.get("deps", {})
    for k, v in deps.items():
        print(f"  ← {k}: {str(v).strip()[:90]}")
    print(f"\n[T3 汇总产出]:\n{t3.result.strip()[:300]}")

    ws.save_artifact("_v2_summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n汇总已存: {ws.dir}/_v2_summary.json")


if __name__ == "__main__":
    main()
