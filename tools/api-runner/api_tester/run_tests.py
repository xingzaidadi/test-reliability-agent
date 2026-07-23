#!/usr/bin/env python3
"""
run_tests.py — Track I (ai-api-tester)
直接执行 api_cases.yaml 并输出结构化结果。
与 api_execution_tool.py 的区别：
  - 支持通过 detect/locate 自动获取 base_url
  - 支持 X5 协议 (protocol: x5)
  - 支持 Bearer token 和 cookie 两种认证方式
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("错误：缺少 pyyaml，请执行 pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def _json_path_get(obj, path: str):
    """最小 JSONPath 实现，支持 $.a.b.c 和 $.a[0].b"""
    if not path.startswith("$"):
        return None
    parts = path.lstrip("$.").split(".")
    current = obj
    for part in parts:
        if part == "":
            continue
        if "[" in part:
            name, idx_str = part.rstrip("]").split("[")
            if isinstance(current, dict):
                current = current.get(name)
            if isinstance(current, list):
                try:
                    current = current[int(idx_str)]
                except (IndexError, ValueError):
                    return None
        else:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
    return current


def _check_assertion(assertion: dict, response_body, status_code: int, duration_ms: float) -> dict:
    a_type = assertion.get("type", "")
    passed = False
    detail = ""

    if a_type == "status_code":
        expected = assertion.get("expected", 200)
        passed = status_code == expected
        detail = f"status_code: expected={expected}, actual={status_code}"

    elif a_type == "json_path":
        path = assertion.get("path", "")
        actual = _json_path_get(response_body, path)
        if "expected" in assertion:
            passed = str(actual) == str(assertion["expected"])
            detail = f"json_path {path}: expected={assertion['expected']}, actual={actual}"
        elif assertion.get("not_null"):
            passed = actual is not None
            detail = f"json_path {path}: not_null, actual={actual}"
        elif "length_gt" in assertion:
            passed = isinstance(actual, (list, str)) and len(actual) > assertion["length_gt"]
            detail = f"json_path {path}: length>{assertion['length_gt']}, actual={len(actual) if actual else 0}"
        else:
            passed = actual is not None
            detail = f"json_path {path}: actual={actual}"

    elif a_type == "response_time_ms":
        max_ms = assertion.get("max", 5000)
        passed = duration_ms <= max_ms
        detail = f"response_time: max={max_ms}ms, actual={duration_ms:.0f}ms"

    elif a_type == "body_contains":
        keyword = assertion.get("keyword", "")
        body_str = json.dumps(response_body, ensure_ascii=False)
        passed = keyword in body_str
        detail = f"body_contains '{keyword}': {'found' if passed else 'not found'}"

    elif a_type == "body_not_contains":
        keyword = assertion.get("keyword", "")
        body_str = json.dumps(response_body, ensure_ascii=False)
        passed = keyword not in body_str
        detail = f"body_not_contains '{keyword}': {'ok' if passed else 'found (unexpected)'}"

    return {"type": a_type, "passed": passed, "detail": detail}


def _run_single(case: dict, base_url: str, token: str, cookie: str = "") -> dict:
    case_id  = case.get("id", "unknown")
    method   = str(case.get("method", "POST")).upper()
    path     = case.get("path", "")
    protocol = case.get("protocol", "rest")
    headers  = dict(case.get("headers", {}))
    timeout  = case.get("timeout_seconds", 30)

    url = base_url.rstrip("/") + "/" + path.lstrip("/")

    # 认证
    if token:
        headers.setdefault("Authorization", f"Bearer {token}")
    if cookie:
        headers.setdefault("Cookie", cookie)
    headers.setdefault("Content-Type", "application/json")

    # 构造 body
    body_dict = case.get("body", {}) or {}
    if protocol == "x5":
        params = body_dict.get("params", [])
        if not isinstance(params, list):
            params = [body_dict]
        body_bytes = json.dumps({"params": params}, ensure_ascii=False).encode("utf-8")
    else:
        body_bytes = json.dumps(body_dict, ensure_ascii=False).encode("utf-8") if body_dict else None

    t_start = time.time()
    try:
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status_code = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        status_code = e.code
    except Exception as exc:
        duration_ms = (time.time() - t_start) * 1000
        return {
            "case_id": case_id, "name": case.get("name", ""),
            "status": "failed", "status_code": 0,
            "duration_ms": round(duration_ms, 1),
            "error": str(exc), "assertions": [], "response_body": None, "request_body": body_dict,
        }

    duration_ms = (time.time() - t_start) * 1000

    try:
        response_body = json.loads(raw)
    except Exception:
        response_body = {"raw": raw[:500]}

    assertions = [
        _check_assertion(a, response_body, status_code, duration_ms)
        for a in case.get("assertions", [])
    ]

    all_passed = all(a["passed"] for a in assertions)
    return {
        "case_id":       case_id,
        "name":          case.get("name", ""),
        "priority":      case.get("priority", "P1"),
        "status":        "passed" if all_passed else "failed",
        "status_code":   status_code,
        "duration_ms":   round(duration_ms, 1),
        "error":         None,
        "assertions":    assertions,
        "response_body": response_body,
        "request_body":  body_dict,
    }


def run(
    cases_yaml: str,
    issue_id: str,
    run_dir: str,
    base_url: str = "",
    token: str = "",
    cookie: str = "",
    priority_filter: str = None,
) -> dict:
    base_url = base_url or os.environ.get("TARGET_SYSTEM_BASE_URL", "")
    token    = token    or os.environ.get("TARGET_SYSTEM_TOKEN", "")
    cookie   = cookie   or os.environ.get("TARGET_SYSTEM_COOKIE", "")

    if not base_url:
        raise RuntimeError("BASE_URL 未设置，无法执行测试")

    data = yaml.safe_load(Path(cases_yaml).read_text(encoding="utf-8"))
    cases = data if isinstance(data, list) else data.get("cases", [])

    if priority_filter:
        cases = [c for c in cases if c.get("priority", "P1") == priority_filter]

    results = []
    for case in cases:
        r = _run_single(case, base_url, token, cookie)
        results.append(r)
        status_sym = "PASS" if r["status"] == "passed" else "FAIL"
        print(f"  [{status_sym}] {r['case_id']} {r['name']} ({r['duration_ms']}ms)")

    passed  = sum(1 for r in results if r["status"] == "passed")
    failed  = len(results) - passed
    output  = {
        "issue_id":    issue_id,
        "executed_at": datetime.now().isoformat(),
        "source":      "ai-api-tester/run_tests",
        "summary":     {"total": len(results), "passed": passed, "failed": failed},
        "cases":       results,
    }

    out_dir = Path(run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "api_execution_result.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[run_tests] {passed}/{len(results)} 通过  结果: {out_path}")
    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="run_tests", description="执行 API 测试用例")
    parser.add_argument("--cases",    required=True)
    parser.add_argument("--issue",    required=True)
    parser.add_argument("--run-dir",  default="outputs/runs", dest="run_dir")
    parser.add_argument("--base-url", default="", dest="base_url")
    parser.add_argument("--token",    default="")
    parser.add_argument("--priority", default=None)
    args = parser.parse_args()

    run_dir = str(Path(args.run_dir) / args.issue)
    result  = run(args.cases, args.issue, run_dir, args.base_url, args.token,
                  priority_filter=args.priority)
    sys.exit(0 if result["summary"]["failed"] == 0 else 1)
