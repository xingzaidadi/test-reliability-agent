#!/usr/bin/env python3
"""
E2eExecutionTool — E2E 业务链路执行器
把多个有序 API 步骤串成一条业务链路,步骤间可传递上下文(extract → 下一步用)。
任一步失败则整条链路中止并判失败。复用 api_execution_tool 的 run_case(含X5签名)。

价格中心无UI,故E2E走纯API多步链路(真实可跑)。
用法:
  python e2e_execution_tool.py --issue ISSUE-001 --flow outputs/runs/ISSUE-001/e2e_flow.yaml
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 复用 api_execution_tool 的能力(签名/请求/断言/JSONPath)
sys.path.insert(0, str(Path(__file__).parent))
from api_execution_tool import run_case, _json_path_get, _load_yaml


def run_e2e(flow_yaml: Path, issue_id: str, run_dir: Path,
            env_overrides: dict | None = None) -> dict:
    base_url = os.environ.get("TARGET_SYSTEM_BASE_URL", "").rstrip("/")
    token    = os.environ.get("TARGET_SYSTEM_TOKEN", "")
    if not base_url:
        raise RuntimeError("TARGET_SYSTEM_BASE_URL 未设置")

    flow = _load_yaml(flow_yaml)
    steps = flow.get("steps", [])
    flow_name = flow.get("name", "E2E链路")

    # 链路上下文:extract 出来的值存这里,供后续步骤 {{key}} 引用
    context = dict(env_overrides or {})

    print(f"[e2e] 链路「{flow_name}」共 {len(steps)} 步,base_url={base_url}")

    step_results = []
    chain_status = "passed"
    for i, step in enumerate(steps):
        sid = step.get("step_id", f"S{i+1}")
        name = step.get("name", "")
        print(f"  [E2E] {sid} {name}", end=" ... ", flush=True)

        # run_case 复用:step 结构兼容 case(path/method/headers/body/assertions)
        # 用 context 做变量替换(env_overrides 会注入到 headers/body 的 {{}})
        r = run_case(step, base_url, token, env_overrides=context)
        passed = r["status"] == "passed"

        # 提取值进上下文(供下一步)
        extracted = {}
        if passed and step.get("extract"):
            body = r.get("response_body", {})
            for key, jpath in step["extract"].items():
                val = _json_path_get(body, jpath)
                if val is not None:
                    context[key] = str(val)
                    extracted[key] = str(val)

        step_results.append({
            "step_id": sid, "name": name,
            "status": r["status"], "status_code": r["status_code"],
            "duration_ms": r["duration_ms"],
            "extracted": extracted,
            "failed_assertions": [a for a in r.get("assertions", []) if not a.get("passed", True)],
        })

        icon = "PASS" if passed else "FAIL"
        extra = f" → 提取{extracted}" if extracted else ""
        print(f"{icon} ({r['duration_ms']}ms){extra}")

        if not passed:
            chain_status = "failed"
            print(f"[e2e] 步骤 {sid} 失败,链路中止(后续步骤不执行)")
            break

    executed = len(step_results)
    passed_steps = sum(1 for s in step_results if s["status"] == "passed")

    output = {
        "issue_id": issue_id,
        "executed_at": datetime.now().isoformat(),
        "flow_name": flow_name,
        "base_url": base_url,
        "chain_status": chain_status,
        "summary": {
            "total_steps": len(steps),
            "executed_steps": executed,
            "passed_steps": passed_steps,
            "failed_steps": executed - passed_steps,
            "skipped_steps": len(steps) - executed,
        },
        "steps": step_results,
    }
    out_path = run_dir / "e2e_execution_result.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[e2e] 链路状态: {chain_status} ({passed_steps}/{len(steps)} 步通过)")
    print(f"[e2e] 结果已写入: {out_path}")
    return output


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="e2e_execution_tool")
    ap.add_argument("--issue", required=True)
    ap.add_argument("--flow", default=None)
    ap.add_argument("--run-dir", default=None, dest="run_dir")
    args = ap.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else Path("outputs/runs") / args.issue
    flow = Path(args.flow) if args.flow else run_dir / "e2e_flow.yaml"

    try:
        result = run_e2e(flow, args.issue, run_dir)
        sys.exit(0 if result["chain_status"] == "passed" else 1)
    except Exception as e:
        print(f"[e2e] ERROR: {e}", file=sys.stderr)
        sys.exit(2)
