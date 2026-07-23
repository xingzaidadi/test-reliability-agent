#!/usr/bin/env python3
"""
ArtifactCollector — Track E (Part 1)
扫描 outputs/runs/{issue_id}/ 目录，按 artifact_contract.md 定义逐一检查，
计算整体 status，写入 artifact_index.json。
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ── 产物清单（来自 artifact_contract.md）────────────────────────────────────

ARTIFACT_REGISTRY = [
    # type                      filename                              required  p0_bearing
    ("context_package",         "context_package.json",               True,     False),
    ("scope_analysis",          "scope_analysis.json",                True,     False),
    ("test_cases",              "test_cases.json",                    True,     False),
    ("test_cases_md",           "test_cases.md",                      True,     False),
    ("api_cases",               "api_cases.yaml",                     False,    False),
    ("ui_flow",                 "ui_flow.yaml",                       False,    False),
    ("e2e_cases",               "e2e_cases.yaml",                     False,    False),
    ("perf_cases",              "perf_cases.yaml",                    False,    False),
    ("execution_plan",          "execution_plan.json",                True,     False),
    ("human_confirmation",      "human_confirmation.json",            False,    False),
    ("api_execution_result",    "api_execution_result.json",          False,    True),
    ("ui_execution_result",     "ui_execution_result.json",           False,    True),
    ("performance_result",      "performance_result.json",            False,    False),
    ("defect_analysis",         "defect_analysis.json",               True,     False),
    ("repair_suggestion",       "repair_suggestion.md",               False,    False),
    ("report",                  "test_agent_report.md",               True,     False),
    ("html_report",             "ui_report.html",                     False,    False),
    ("multica_comment",         "multica_comment_payload.json",       True,     False),
    ("screenshots",             "screenshots/",                       False,    False),
    ("trace",                   "trace.zip",                          False,    False),
    ("artifact_index",          "artifact_index.json",                False,    False),  # self
]


def _read_execution_summary(run_dir: Path, filename: str) -> dict:
    """从执行结果 JSON 中提取 summary 字段。"""
    p = run_dir / filename
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("summary", {})
    except Exception:
        return {}


def collect(issue_id: str, run_dir: Path, workspace_id: str = "target-system-test") -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)

    # 扫描产物
    artifacts = []
    missing_required = []
    blocked_execution = []

    for art_type, filename, required, p0_bearing in ARTIFACT_REGISTRY:
        path = run_dir / filename
        # 目录类产物（screenshots/）：检查目录是否存在且非空
        if filename.endswith("/"):
            exists = path.is_dir() and any(path.iterdir()) if path.is_dir() else False
        else:
            exists = path.is_file()

        entry = {
            "type":     art_type,
            "path":     str(path),
            "required": required,
            "exists":   exists,
        }
        if p0_bearing and exists:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                entry["status"] = data.get("status", "unknown")
                entry["summary"] = data.get("summary", {})
                if entry["status"] == "blocked":
                    blocked_execution.append(art_type)
            except Exception:
                pass

        artifacts.append(entry)
        if required and not exists:
            missing_required.append(filename)

    # 汇总执行结果
    api_summary = _read_execution_summary(run_dir, "api_execution_result.json")
    ui_summary  = _read_execution_summary(run_dir, "ui_execution_result.json")

    api_total  = api_summary.get("total",        0)
    api_passed = api_summary.get("passed",        0)
    api_failed = api_summary.get("failed",        0)
    ui_total   = ui_summary.get("total_steps",    0)
    ui_passed  = ui_summary.get("passed_steps",   0)
    ui_failed  = ui_summary.get("failed_steps",   0)

    # 判断整体 status
    # blocked_execution 表示"执行等待环境"（env 未配置），是预期状态，不阻断整体
    # 只有 missing_required（必要文档产物缺失）才将整体标为 blocked
    if missing_required:
        overall_status = "blocked"
    elif api_failed > 0 or ui_failed > 0:
        overall_status = "failed"
    else:
        overall_status = "passed"

    index = {
        "multica_issue_id": issue_id,
        "workspace_id":     workspace_id,
        "run_id":           f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "collected_at":     datetime.now().isoformat(),
        "status":           overall_status,
        "target_system":    "target-system",
        "missing_required": missing_required,
        "blocked_execution": blocked_execution,
        "summary": {
            "total_cases":  api_total + ui_total,
            "api_passed":   api_passed,
            "api_total":    api_total,
            "api_failed":   api_failed,
            "ui_passed":    ui_passed,
            "ui_total":     ui_total,
            "ui_failed":    ui_failed,
        },
        "artifacts": artifacts,
    }

    out_path = run_dir / "artifact_index.json"
    out_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[artifact-collector] 产物: {len(artifacts)} 项")
    print(f"[artifact-collector] 缺少必要产物: {missing_required or '无'}")
    print(f"[artifact-collector] 整体状态: {overall_status}")
    print(f"[artifact-collector] 产物索引: {out_path}")
    return index


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="artifact_collector",
                                     description="ArtifactCollector — Track E")
    parser.add_argument("--issue",     required=True)
    parser.add_argument("--run-dir",   default=None, dest="run_dir")
    parser.add_argument("--workspace", default="target-system-test")
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else Path("outputs/runs") / args.issue
    result  = collect(args.issue, run_dir, args.workspace)
    sys.exit(0 if result["status"] != "blocked" else 1)
