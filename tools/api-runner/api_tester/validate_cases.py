#!/usr/bin/env python3
"""
validate_cases.py — Track I (ai-api-tester)
校验 api_cases.yaml 格式合法性，输出 validation_report.json。
规则：
  - 每个 case 必须有 id, name, method, path
  - assertions 中 type 必须是已知类型
  - priority 必须是 P0/P1/P2
"""

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("错误：缺少 pyyaml，请执行 pip install pyyaml", file=sys.stderr)
    sys.exit(1)

REQUIRED_FIELDS = {"id", "name", "method", "path"}
VALID_METHODS   = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
VALID_PRIORITIES = {"P0", "P1", "P2"}
VALID_ASSERTION_TYPES = {
    "status_code", "json_path", "response_time_ms",
    "header", "body_contains", "body_not_contains",
}


def validate_case(case: dict, idx: int) -> list:
    errors = []
    case_id = case.get("id", f"case[{idx}]")

    for field in REQUIRED_FIELDS:
        if field not in case:
            errors.append(f"{case_id}: 缺少必要字段 '{field}'")

    method = str(case.get("method", "")).upper()
    if method and method not in VALID_METHODS:
        errors.append(f"{case_id}: method '{method}' 不是有效 HTTP 方法")

    priority = case.get("priority", "P1")
    if priority not in VALID_PRIORITIES:
        errors.append(f"{case_id}: priority '{priority}' 应为 P0/P1/P2")

    for a_idx, assertion in enumerate(case.get("assertions", [])):
        a_type = assertion.get("type", "")
        if a_type not in VALID_ASSERTION_TYPES:
            errors.append(
                f"{case_id}: assertion[{a_idx}] type '{a_type}' "
                f"不是已知类型 {sorted(VALID_ASSERTION_TYPES)}"
            )
        if a_type == "json_path" and "path" not in assertion:
            errors.append(f"{case_id}: assertion[{a_idx}] json_path 缺少 'path' 字段")

    return errors


def validate(cases_yaml: str) -> dict:
    path = Path(cases_yaml)
    if not path.exists():
        return {"valid": False, "errors": [f"文件不存在: {cases_yaml}"], "cases_count": 0}

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        return {"valid": False, "errors": [f"YAML 解析失败: {e}"], "cases_count": 0}

    cases = data if isinstance(data, list) else data.get("cases", [])
    if not cases:
        return {"valid": False, "errors": ["未找到用例列表（根节点应为列表或含 'cases' 键的字典）"], "cases_count": 0}

    all_errors = []
    for idx, case in enumerate(cases):
        all_errors.extend(validate_case(case, idx))

    # id 唯一性检查
    ids = [c.get("id") for c in cases if c.get("id")]
    seen = set()
    for cid in ids:
        if cid in seen:
            all_errors.append(f"重复的 case id: '{cid}'")
        seen.add(cid)

    return {
        "valid":       len(all_errors) == 0,
        "cases_count": len(cases),
        "error_count": len(all_errors),
        "errors":      all_errors,
        "cases_file":  str(path),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="validate_cases", description="校验 api_cases.yaml")
    parser.add_argument("cases_yaml")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    result = validate(args.cases_yaml)
    out = json.dumps(result, ensure_ascii=False, indent=2)
    print(out)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")

    sys.exit(0 if result["valid"] else 1)
