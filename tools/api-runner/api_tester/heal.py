#!/usr/bin/env python3
"""
heal.py — Track I (ai-api-tester)
根据 failure_analysis.json 自动修复可修复的用例。
支持：
  - ASSERTION_MISMATCH：用实际返回值更新 expected
  - TIMEOUT：增大 timeout_seconds
输出：修复后的 api_cases.yaml（在原文件旁写 api_cases.healed.yaml）
"""

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("错误：缺少 pyyaml，请执行 pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def _heal_assertion_mismatch(case_dict: dict, execution_case: dict) -> bool:
    """用实际 actual 值更新 expected。"""
    healed = False
    for assertion in case_dict.get("assertions", []):
        if assertion.get("type") != "json_path":
            continue
        path = assertion.get("path", "")
        # 从 execution result 找对应断言的 actual
        for exec_a in execution_case.get("assertions", []):
            if exec_a.get("type") == "json_path" and not exec_a.get("passed", True):
                detail = exec_a.get("detail", "")
                if path in detail and "actual=" in detail:
                    actual_str = detail.split("actual=")[-1].strip()
                    assertion["expected"] = actual_str
                    healed = True
    return healed


def _heal_timeout(case_dict: dict) -> bool:
    """把 timeout_seconds 增大 50%。"""
    current = case_dict.get("timeout_seconds", 30)
    case_dict["timeout_seconds"] = int(current * 1.5)
    return True


def heal(
    cases_yaml: str,
    failure_analysis_json: str,
    exec_result_json: str = None,
) -> dict:
    cases_path    = Path(cases_yaml)
    analysis_path = Path(failure_analysis_json)

    if not cases_path.exists():
        return {"error": f"用例文件不存在: {cases_yaml}"}
    if not analysis_path.exists():
        return {"error": f"失败分析文件不存在: {failure_analysis_json}"}

    # 加载
    raw = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    cases = raw if isinstance(raw, list) else raw.get("cases", [])
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))

    # exec result 映射（用于 assertion mismatch 修复）
    exec_map = {}
    if exec_result_json and Path(exec_result_json).exists():
        exec_data = json.loads(Path(exec_result_json).read_text(encoding="utf-8"))
        exec_map = {c.get("case_id"): c for c in exec_data.get("cases", [])}

    # 构建待修复 case_id 集合
    fixable_ids = {
        f["case_id"]: f
        for f in analysis.get("failures", [])
        if f.get("fixable")
    }

    healed_count = 0
    changes = []

    cases_by_id = {c.get("id"): c for c in cases}
    for case_id, failure in fixable_ids.items():
        case = cases_by_id.get(case_id)
        if not case:
            continue
        category = failure.get("category")
        if category == "ASSERTION_MISMATCH" and case_id in exec_map:
            if _heal_assertion_mismatch(case, exec_map[case_id]):
                healed_count += 1
                changes.append({"case_id": case_id, "action": "updated_expected"})
        elif category == "TIMEOUT":
            _heal_timeout(case)
            healed_count += 1
            changes.append({"case_id": case_id, "action": "increased_timeout",
                            "new_timeout": case["timeout_seconds"]})

    # 写修复后的文件
    healed_path = cases_path.parent / (cases_path.stem + ".healed" + cases_path.suffix)
    out_data = cases if isinstance(raw, list) else {**raw, "cases": cases}
    healed_path.write_text(
        yaml.dump(out_data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    return {
        "original":      str(cases_path),
        "healed":        str(healed_path),
        "healed_count":  healed_count,
        "total_fixable": len(fixable_ids),
        "changes":       changes,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="heal", description="自动修复可修复的失败用例")
    parser.add_argument("--cases",    required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--exec-result", default=None, dest="exec_result")
    parser.add_argument("--output",   default=None)
    args = parser.parse_args()

    result = heal(args.cases, args.analysis, args.exec_result)
    out = json.dumps(result, ensure_ascii=False, indent=2)
    print(out)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
