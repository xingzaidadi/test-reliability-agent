#!/usr/bin/env python3
"""
DefectAnalyzer — Track F
读取 api_execution_result.json + ui_execution_result.json，
对每条失败用例做根因分类（ENV/DATA/CASE/PRODUCT/TOOL/UNKNOWN），
输出 defect_analysis.json + repair_suggestion.md。
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# ── 根因分类规则 ──────────────────────────────────────────────────────────────

# (分类, 优先级, 匹配条件函数)
# 条件函数接受 (case_result: dict) -> bool
_API_RULES = [
    ("ENV",     1, lambda c: c.get("status_code") == 0 or
                             any(x in (c.get("error") or "")
                                 for x in ["Connection refused", "timeout", "Network", "未设置",
                                            "urlopen error", "Name or service not known",
                                            "certificate", "SSL"])),
    ("ENV",     1, lambda c: c.get("status_code") in (502, 503, 504)),
    ("TOOL",    2, lambda c: c.get("status_code") == 0 and
                             any(x in (c.get("error") or "")
                                 for x in ["JSONDecodeError", "AttributeError", "TypeError",
                                            "KeyError", "ValueError"])),
    ("DATA",    3, lambda c: c.get("status_code") == 200 and
                             _resp_code(c) in ("FAIL", "PART_SUCCESS") and
                             _looks_like_data_issue(c)),
    ("CASE",    4, lambda c: _has_wrong_assertion(c)),
    # HTTP状态码与业务状态码不一致:HTTP=200 但业务码是错误码(400/500等)。
    # 这是真实接口设计问题——只看HTTP码的监控会漏报失败。
    ("PRODUCT", 5, lambda c: _http_biz_code_mismatch(c)),
    ("PRODUCT", 5, lambda c: c.get("status_code") == 200 and
                             _resp_code(c) in ("FAIL", "PART_SUCCESS")),
    ("PRODUCT", 5, lambda c: c.get("status_code") not in (None, 0, 200, 400, 401, 403,
                                                            404, 502, 503, 504)),
]

_UI_RULES = [
    ("ENV",     1, lambda s: any(x in (s.get("error") or "")
                                 for x in ["TimeoutError", "net::", "SSL", "CERT",
                                            "ERR_CONNECTION", "ERR_NAME", "navigation"])),
    ("ENV",     1, lambda s: "登录" in (s.get("name") or "") and s.get("status") == "failed"),
    ("DATA",    3, lambda s: any(x in (s.get("name") or "")
                                 for x in ["列表", "数据"]) and s.get("status") == "failed"),
    ("TOOL",    2, lambda s: any(x in (s.get("error") or "")
                                 for x in ["playwright", "Playwright", "Protocol error",
                                            "Target closed", "Page closed"])),
    ("CASE",    4, lambda s: _has_wrong_ui_assertion(s)),
    ("PRODUCT", 5, lambda s: s.get("status") == "failed"),
]


def _resp_code(case: dict) -> str:
    body = case.get("response_body", {})
    if isinstance(body, dict):
        data = body.get("data", {})
        if isinstance(data, dict):
            return data.get("code", "")
    return ""


def _biz_code(case: dict):
    """提取业务状态码,兼容多种响应结构:header.code / body.code / code。"""
    body = case.get("response_body", {})
    if not isinstance(body, dict):
        return None
    for path in (("header", "code"), ("body", "code"), ("code",)):
        cur = body
        ok = True
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok and isinstance(cur, int):
            return cur
    return None


def _http_biz_code_mismatch(case: dict) -> bool:
    """HTTP状态码与业务码不一致:HTTP=2xx 但业务码是错误码(>=400)。
    典型的接口设计问题——只看HTTP码的监控/告警会漏报失败。"""
    http = case.get("status_code")
    biz = _biz_code(case)
    if http is None or biz is None:
        return False
    return (200 <= http < 300) and (biz >= 400)


def _looks_like_data_issue(case: dict) -> bool:
    body = case.get("response_body", {})
    text = json.dumps(body, ensure_ascii=False)
    data_keywords = ["不存在", "未找到", "无效", "objectCode", "TEST_OBJECT_CODE",
                     "NONEXISTENT", "no data", "empty"]
    return any(k in text for k in data_keywords)


def _has_wrong_assertion(case: dict) -> bool:
    for a in case.get("assertions", []):
        if not a.get("passed", True):
            detail = a.get("detail", "")
            # 期望与实际都是已知合理值但不匹配 → 可能是 CASE 问题
            if "expected" in detail and "!=" in detail:
                return True
    return False


def _has_wrong_ui_assertion(step: dict) -> bool:
    for a in step.get("assertions", []):
        if not a.get("passed", True):
            detail = a.get("detail", "")
            if "expected" in detail.lower():
                return True
    return False


def _classify_api_failure(case: dict) -> tuple[str, str, bool, bool]:
    """返回 (category, evidence, blocking, potential_bug)"""
    for cat, _, condition in _API_RULES:
        try:
            if condition(case):
                evidence = _build_api_evidence(case, cat)
                blocking = cat in ("ENV", "DATA")
                potential_bug = cat == "PRODUCT"
                return cat, evidence, blocking, potential_bug
        except Exception:
            pass
    return "UNKNOWN", f"status_code={case.get('status_code')} error={case.get('error','无')}", False, False


def _classify_ui_failure(step: dict) -> tuple[str, str, bool, bool]:
    for cat, _, condition in _UI_RULES:
        try:
            if condition(step):
                evidence = _build_ui_evidence(step, cat)
                blocking = cat in ("ENV", "DATA")
                potential_bug = cat == "PRODUCT"
                return cat, evidence, blocking, potential_bug
        except Exception:
            pass
    return "UNKNOWN", f"step={step.get('step_id')} error={step.get('error','无')}", False, False


def _build_api_evidence(case: dict, cat: str) -> str:
    parts = []
    if case.get("error"):
        parts.append(f"error: {case['error'][:200]}")
    if case.get("status_code") is not None:
        parts.append(f"status_code: {case['status_code']}")
    body = case.get("response_body", {})
    resp_text = json.dumps(body, ensure_ascii=False)[:200] if body else ""
    if resp_text:
        parts.append(f"response: {resp_text}")
    failed_a = [a for a in case.get("assertions", []) if not a.get("passed", True)]
    for a in failed_a[:2]:
        parts.append(f"assertion: {a.get('detail','')}")
    return " | ".join(parts) or f"{cat} 分类匹配"


def _build_ui_evidence(step: dict, cat: str) -> str:
    parts = []
    if step.get("error"):
        parts.append(f"error: {step['error'][:200]}")
    parts.append(f"step: {step.get('step_id','')} {step.get('name','')}")
    return " | ".join(parts) or f"{cat} 分类匹配"


_SUGGESTION_MAP = {
    "ENV": (
        "检查 TARGET_SYSTEM_BASE_URL / TARGET_SYSTEM_UI_URL 是否正确设置，"
        "确认测试环境 http://your-test-host.example.com/price 可达，"
        "运行 test-squad doctor 确认全部环境检查通过后重跑。"
    ),
    "DATA": (
        "确认测试用例使用的 objectCode / priceDocCode 在测试环境存在有效数据。"
        "建议联系 developer 获取当前测试环境中可查到价格的有效编码，"
        "替换 api_cases.yaml 中的 {{TEST_OBJECT_CODE}} 占位符后重跑。"
    ),
    "CASE": (
        "审查失败用例的断言条件，确认 expected 值与测试环境实际返回一致。"
        "对于 status_code 不确定的用例（如 TC_005），建议先手动调用接口确认实际返回后更新断言。"
    ),
    "PRODUCT": (
        "接口返回与预期不符且已排除环境/数据/用例问题。"
        "建议：1) 手动调用接口二次确认复现；2) 查看服务端日志；"
        "3) 在 Multica issue 中添加 potential_bug 标签并 @ 开发同学确认。"
    ),
    "TOOL": (
        "api_runner / ui_runner 工具本身报错。"
        "检查 Python 版本 (>=3.9) 和 pyyaml/playwright 版本，"
        "若是 Playwright 问题运行 playwright install chromium 重新安装浏览器。"
    ),
    "UNKNOWN": (
        "暂时无法自动判断根因，需要人工介入。"
        "建议：1) 查看完整错误信息；2) 手动复现；"
        "3) 在 Multica issue 中描述现象并 @ developer 确认。"
    ),
}


def analyze(issue_id: str, run_dir: Path) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    failures = []
    by_cat = {"ENV": 0, "DATA": 0, "CASE": 0, "PRODUCT": 0, "TOOL": 0, "UNKNOWN": 0}

    # API 失败
    api_path = run_dir / "api_execution_result.json"
    if api_path.exists():
        api_data = json.loads(api_path.read_text(encoding="utf-8"))
        for case in api_data.get("cases", []):
            if case.get("status") == "failed":
                cat, evidence, blocking, potential_bug = _classify_api_failure(case)
                by_cat[cat] = by_cat.get(cat, 0) + 1
                entry = {
                    "tc_id":        case.get("case_id", ""),
                    "source":       "api",
                    "category":     cat,
                    "evidence":     evidence,
                    "suggestion":   _SUGGESTION_MAP.get(cat, ""),
                    "blocking":     blocking,
                }
                if potential_bug:
                    entry["potential_bug"] = True
                failures.append(entry)

    # UI 失败
    ui_path = run_dir / "ui_execution_result.json"
    if ui_path.exists():
        ui_data = json.loads(ui_path.read_text(encoding="utf-8"))
        for step in ui_data.get("steps", []):
            if step.get("status") == "failed":
                cat, evidence, blocking, potential_bug = _classify_ui_failure(step)
                by_cat[cat] = by_cat.get(cat, 0) + 1
                entry = {
                    "tc_id":      f"UI-{step.get('step_id','')}",
                    "source":     "ui",
                    "category":   cat,
                    "evidence":   evidence,
                    "suggestion": _SUGGESTION_MAP.get(cat, ""),
                    "blocking":   blocking,
                }
                if potential_bug:
                    entry["potential_bug"] = True
                failures.append(entry)

    analysis = {
        "issue_id":    issue_id,
        "analyzed_at": datetime.now().isoformat(),
        "summary": {
            "total_failed": len(failures),
            "by_category":  by_cat,
            "blocking_count": sum(1 for f in failures if f.get("blocking")),
        },
        "failures": failures,
    }

    out_path = run_dir / "defect_analysis.json"
    out_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[defect-analyzer] {len(failures)} 条失败，已分类")
    print(f"[defect-analyzer] 分类分布: {by_cat}")
    print(f"[defect-analyzer] 结果: {out_path}")

    # repair_suggestion.md
    _write_repair_suggestion(issue_id, run_dir, failures, by_cat)
    return analysis


def _write_repair_suggestion(issue_id: str, run_dir: Path, failures: list, by_cat: dict):
    if not failures:
        lines = [
            f"# 修复建议 — {issue_id}",
            "",
            "所有用例通过，无需修复。",
        ]
    else:
        blocking = [f for f in failures if f.get("blocking")]
        non_blocking = [f for f in failures if not f.get("blocking")]

        lines = [
            f"# 修复建议 — {issue_id}",
            "",
            f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"失败总数：{len(failures)}  ",
            f"阻断项：{len(blocking)}  ",
            "",
            "## 修复优先级",
            "",
            "**先修复阻断项（ENV/DATA），再重跑，再看 PRODUCT/CASE。**",
            "",
        ]

        if blocking:
            lines += ["## 阻断项（必须先修复）", ""]
            for f in blocking:
                lines += [
                    f"### {f['tc_id']} [{f['category']}]",
                    f"",
                    f"**证据：** {f['evidence']}  ",
                    f"**建议：** {f['suggestion']}  ",
                    "",
                ]

        if non_blocking:
            lines += ["## 非阻断失败", ""]
            for f in non_blocking:
                tag = " ⚠️ 疑似Bug" if f.get("potential_bug") else ""
                lines += [
                    f"### {f['tc_id']} [{f['category']}]{tag}",
                    f"",
                    f"**证据：** {f['evidence']}  ",
                    f"**建议：** {f['suggestion']}  ",
                    "",
                ]

        lines += [
            "## 修复后行动",
            "",
            "```powershell",
            f"# 修复后重跑",
            f"test-squad run-api --issue {issue_id} --priority P0",
            f"test-squad run-ui  --issue {issue_id}",
            f"test-squad report  --issue {issue_id}",
            "```",
        ]

    rep_path = run_dir / "repair_suggestion.md"
    rep_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[defect-analyzer] 修复建议: {rep_path}")


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="defect_analyzer",
                                     description="DefectAnalyzer — Track F")
    parser.add_argument("--issue",   required=True)
    parser.add_argument("--run-dir", default=None, dest="run_dir")
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else Path("outputs/runs") / args.issue
    result  = analyze(args.issue, run_dir)
    sys.exit(0 if result["summary"]["blocking_count"] == 0 else 1)
