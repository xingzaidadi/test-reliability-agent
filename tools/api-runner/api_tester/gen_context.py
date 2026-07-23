#!/usr/bin/env python3
"""
gen_context.py — Track I (ai-api-tester)
整合 detect + locate 结果，生成 context_package.json。
context_package 是 Mify workflow 第一个节点的输入。
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from detect import detect
from locate import locate


def gen_context(
    project_root: str,
    issue_id: str,
    target_env: str = "test",
    base_url: str = "",
    extra: dict = None,
) -> dict:
    project_info = detect(project_root)
    endpoint_info = locate(project_root)

    context = {
        "multica_issue_id": issue_id,
        "target_env":       target_env,
        "base_url":         base_url,
        "generated_at":     datetime.now().isoformat(),
        "project": {
            "root":          project_info.get("project_root"),
            "primary_type":  project_info.get("primary_type", "unknown"),
            "detected_types":project_info.get("detected_types", []),
            "has_openapi":   project_info.get("has_openapi", False),
            "controller_files": project_info.get("controller_files", [])[:10],
        },
        "endpoints": {
            "total":   endpoint_info.get("total", 0),
            "summary": endpoint_info.get("endpoints", [])[:50],
        },
        "scope_hint": {
            "description": f"{project_info.get('primary_type','unknown')} 项目，共 {endpoint_info.get('total',0)} 个 API 端点",
            "suggested_priority": "P0" if endpoint_info.get("total", 0) > 0 else "P1",
        },
    }

    if extra:
        context.update(extra)

    return context


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="gen_context", description="生成 context_package.json")
    parser.add_argument("project_root",         nargs="?", default=".")
    parser.add_argument("--issue",    required=True)
    parser.add_argument("--env",      default="test")
    parser.add_argument("--base-url", default="", dest="base_url")
    parser.add_argument("--output",   default=None)
    args = parser.parse_args()

    ctx = gen_context(
        project_root=args.project_root,
        issue_id=args.issue,
        target_env=args.env,
        base_url=args.base_url,
    )
    out = json.dumps(ctx, ensure_ascii=False, indent=2)
    print(out)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"[gen_context] 写入: {args.output}", file=sys.stderr)
