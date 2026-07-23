#!/usr/bin/env python3
"""
analyze_failures.py — Track I (ai-api-tester)
分析 api_execution_result.json 中的失败用例，
输出 failure_analysis.json（精简版，聚焦 API 失败模式分类）。
与 defect_analyzer.py 互补：本模块专注 AI 可修复的失败，
defect_analyzer 处理全链路根因分类。
"""

import json
import sys
from pathlib import Path


_PATTERNS = [
    # (category, matcher)
    ("AUTH_FAILURE",     lambda c: c.get("status_code") in (401, 403)),
    ("NOT_FOUND",        lambda c: c.get("status_code") == 404),
    ("SERVER_ERROR",     lambda c: c.get("status_code") in (500, 502, 503, 504)),
    ("TIMEOUT",          lambda c: "timeout" in (c.get("error") or "").lower() or
                                    c.get("status_code") == 0),
    ("ASSERTION_MISMATCH", lambda c: any(
                                    not a.get("passed", True) and "expected" in a.get("detail","")
                                    for a in c.get("assertions", []))),
    ("EMPTY_RESPONSE",   lambda c: c.get("response_body") in (None, {}, "", "null")),
    ("UNKNOWN",          lambda c: True),
]


def _classify(case: dict) -> str:
    for cat, fn in _PATTERNS:
        try:
            if fn(case):
                return cat
        except Exception:
            pass
    return "UNKNOWN"


def _ai_hint(category: str, case: dict) -> str:
    hints = {
        "AUTH_FAILURE":      "检查 token/cookie 是否过期，重新获取后更新环境变量",
        "NOT_FOUND":         f"路径 {case.get('request_body',{}).get('path','?')} 可能不存在，检查 URL 拼写和版本前缀",
        "SERVER_ERROR":      "服务端异常，查看服务日志；如是测试数据问题则修复数据后重跑",
        "TIMEOUT":           "接口响应超时，检查环境负载；若是慢接口可在 case 配置更大 timeout_seconds",
        "ASSERTION_MISMATCH":"断言期望值与实际不符，可能需要更新 expected 值或修复业务逻辑",
        "EMPTY_RESPONSE":    "响应体为空，检查请求参数合法性或服务端是否正常返回",
        "UNKNOWN":           "无法自动分类，需要人工查看完整错误信息",
    }
    return hints.get(category, "")


def analyze(result_json: str) -> dict:
    path = Path(result_json)
    if not path.exists():
        return {"error": f"文件不存在: {result_json}", "failures": []}

    data = json.loads(path.read_text(encoding="utf-8"))
    failures = [c for c in data.get("cases", []) if c.get("status") == "failed"]

    analyzed = []
    by_cat = {}
    for case in failures:
        cat = _classify(case)
        by_cat[cat] = by_cat.get(cat, 0) + 1
        analyzed.append({
            "case_id":    case.get("case_id"),
            "name":       case.get("name"),
            "category":   cat,
            "status_code": case.get("status_code"),
            "error":      case.get("error"),
            "ai_hint":    _ai_hint(cat, case),
            "fixable":    cat in ("AUTH_FAILURE", "ASSERTION_MISMATCH", "TIMEOUT"),
        })

    return {
        "source_file":  str(path),
        "total_failed": len(failures),
        "by_category":  by_cat,
        "fixable_count": sum(1 for a in analyzed if a["fixable"]),
        "failures":     analyzed,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="analyze_failures",
                                     description="分析 API 失败用例")
    parser.add_argument("result_json", nargs="?", default="api_execution_result.json")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    result = analyze(args.result_json)
    out = json.dumps(result, ensure_ascii=False, indent=2)
    print(out)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")

    sys.exit(0 if result.get("total_failed", 0) == 0 else 1)
