#!/usr/bin/env python3
"""
diff_detect.py — Track I (ai-api-tester)
对比两次执行结果，输出新增/消失/状态变化的用例。
用于持续测试中的增量接口检测（回归对比）。
"""

import json
import sys
from pathlib import Path


def _case_key(case: dict) -> str:
    return case.get("case_id", "")


def _case_map(result_data: dict) -> dict:
    return {_case_key(c): c for c in result_data.get("cases", [])}


def diff(
    baseline_json: str,
    current_json: str,
) -> dict:
    baseline_path = Path(baseline_json)
    current_path  = Path(current_json)

    if not baseline_path.exists():
        return {"error": f"基准文件不存在: {baseline_json}"}
    if not current_path.exists():
        return {"error": f"当前结果文件不存在: {current_json}"}

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    current  = json.loads(current_path.read_text(encoding="utf-8"))

    base_map = _case_map(baseline)
    curr_map = _case_map(current)

    base_ids = set(base_map)
    curr_ids = set(curr_map)

    new_cases     = []  # 新增（当前有，基准无）
    removed_cases = []  # 消失（基准有，当前无）
    regressions   = []  # 回归：基准 passed，当前 failed
    fixes         = []  # 修复：基准 failed，当前 passed

    for cid in curr_ids - base_ids:
        new_cases.append(curr_map[cid])

    for cid in base_ids - curr_ids:
        removed_cases.append(base_map[cid])

    for cid in base_ids & curr_ids:
        b_status = base_map[cid].get("status")
        c_status = curr_map[cid].get("status")
        if b_status == "passed" and c_status == "failed":
            regressions.append({
                "case_id": cid,
                "name":    curr_map[cid].get("name", ""),
                "baseline_status": b_status,
                "current_status":  c_status,
                "current_error":   curr_map[cid].get("error"),
            })
        elif b_status == "failed" and c_status == "passed":
            fixes.append({
                "case_id": cid,
                "name":    curr_map[cid].get("name", ""),
            })

    return {
        "baseline":    str(baseline_path),
        "current":     str(current_path),
        "summary": {
            "new_cases":     len(new_cases),
            "removed_cases": len(removed_cases),
            "regressions":   len(regressions),
            "fixes":         len(fixes),
        },
        "regressions":   regressions,
        "fixes":         fixes,
        "new_cases":     [c.get("case_id") for c in new_cases],
        "removed_cases": [c.get("case_id") for c in removed_cases],
        "has_regression": len(regressions) > 0,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="diff_detect",
                                     description="对比两次 API 执行结果")
    parser.add_argument("baseline", help="基准结果 JSON 路径")
    parser.add_argument("current",  help="当前结果 JSON 路径")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    result = diff(args.baseline, args.current)
    out = json.dumps(result, ensure_ascii=False, indent=2)
    print(out)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")

    sys.exit(0 if not result.get("has_regression", False) else 1)
