#!/usr/bin/env python3
"""
需求驱动 demo:给平台一个业务需求(不指定接口),让它自己分析→设计测试。
对标 VAF 的需求入口(P阶段)。全本地、codex worker 真执行。

链路(DAG):
  REQ-ANALYZE(需求可测性分析,推导接口) → REQ-DESIGN(测试设计,依赖分析结果)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core import Runtime, Worker, Task
from orchestrator import Orchestrator, Workspace


def main():
    print("=" * 55)
    print(" 需求驱动测试 demo — 给它一个需求,不给接口")
    print("=" * 55)

    # 读需求单
    req_path = Path("outputs/runs/REQ-001/requirement.md")
    requirement = req_path.read_text(encoding="utf-8")
    print(f"\n[输入] 需求单: {req_path}")
    print(f"       (需求方只描述业务,不点接口名)")

    # 给codex提供源码里的真实接口清单(让它能把需求关联到接口)
    # 这些来自 ApiX5Controller 真实源码
    source_apis = (
        "源码 ApiX5Controller 里的X5接口清单:\n"
        "- /x5/api/pullPrice (拉取价格模型,入参purchaseOrg/objectCode/vendorCode/priceType)\n"
        "- /x5/api/getPrice (获取价格,入参同上)\n"
        "- /x5/api/getQty (查询数量)\n"
        "- /x5/api/occupyReleaseQty (数量占用/释放,写操作)\n"
        "priceType枚举: MVAFee/sampleFee/ODMOwnedFee/materialBSFee/commissionFee/materialFee/COST"
    )

    rt = Runtime("local-1")
    ws = Workspace("REQ-001")
    orch = Orchestrator(ws)
    orch.register_worker(Worker("codex-1", "codex", rt))

    # 任务1:需求可测性分析
    orch.submit(Task(
        id="REQ-ANALYZE",
        type="analyze_requirement",
        skill="analyze_requirement",
        payload={"requirement": requirement + "\n\n" + source_apis},
    ))

    # 任务2:测试设计(依赖任务1的产出)
    orch.submit(Task(
        id="REQ-DESIGN",
        type="design_test",
        skill="design_test",
        payload={},                    # analysis 由 DAG 从依赖注入
        depends_on=["REQ-ANALYZE"],
    ))

    print("\n[执行] 编排器调度(DAG:分析→设计)...\n")
    # 先跑分析
    orch.tasks[0].status = orch.tasks[0].status  # noqa
    from core import TaskStatus
    orch._run_one(orch.tasks[0])
    # 把分析结果衔接给设计任务(展示"前置产出喂后续")
    if orch.tasks[0].status == TaskStatus.DONE:
        orch.tasks[1].payload["analysis"] = orch.tasks[0].result
        orch._run_one(orch.tasks[1])

    # DAG 会把 REQ-ANALYZE 的结果放进 REQ-DESIGN 的 payload['deps'],
    # 但 design_test 的 prompt 用 {{analysis}},这里手动衔接一下展示效果
    print("\n" + "=" * 55)
    for t in orch.tasks:
        print(f"\n[产出 {t.id}] status={t.status.value} ({t.duration_ms()}ms)")
        if t.result:
            print(t.result.strip()[:800])

    print("\n" + "=" * 55)
    print(json.dumps(orch.summary(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
