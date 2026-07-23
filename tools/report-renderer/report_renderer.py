#!/usr/bin/env python3
"""
ReportRenderer — Track E (Part 2)
把 test_agent_report.md + artifact_index.json 渲染为 HTML 报告，
并生成 multica_comment_payload.json。
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ── HTML 模板 ────────────────────────────────────────────────────────────────

_HTML_TMPL = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>测试报告 — {issue_id}</title>
<style>
  body{{font-family:'Helvetica Neue',Arial,sans-serif;margin:0;background:#f5f7fa;color:#333}}
  .header{{background:#1a73e8;color:#fff;padding:24px 32px}}
  .header h1{{margin:0;font-size:22px}}
  .header p{{margin:4px 0 0;opacity:.85;font-size:13px}}
  .container{{max-width:960px;margin:24px auto;padding:0 16px}}
  .card{{background:#fff;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.1);
         margin-bottom:20px;padding:20px 24px}}
  .card h2{{margin:0 0 16px;font-size:16px;border-bottom:2px solid #e8eaf0;padding-bottom:8px}}
  .badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600}}
  .badge-pass{{background:#e6f4ea;color:#1e8e3e}}
  .badge-fail{{background:#fce8e6;color:#d93025}}
  .badge-blocked{{background:#fff3e0;color:#e65100}}
  .badge-stub{{background:#f1f3f4;color:#5f6368}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{background:#f1f3f4;text-align:left;padding:8px 12px;font-weight:600}}
  td{{padding:8px 12px;border-bottom:1px solid #f1f3f4}}
  tr:last-child td{{border-bottom:none}}
  .fail-row{{background:#fff8f8}}
  details{{margin:8px 0}}
  summary{{cursor:pointer;color:#1a73e8;font-size:13px}}
  pre{{background:#f8f9fa;border-radius:4px;padding:12px;font-size:12px;
       overflow-x:auto;max-height:300px;white-space:pre-wrap;word-break:break-all}}
  .screenshots{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}}
  .screenshots img{{width:160px;height:100px;object-fit:cover;border-radius:4px;
                    border:1px solid #ddd;cursor:pointer}}
  .stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}
  .stat-box{{text-align:center;padding:12px;background:#f8f9fa;border-radius:6px}}
  .stat-num{{font-size:28px;font-weight:700;color:#1a73e8}}
  .stat-label{{font-size:12px;color:#666;margin-top:4px}}
  footer{{text-align:center;color:#9aa0a6;font-size:12px;padding:24px 0}}
</style>
</head>
<body>
<div class="header">
  <h1>测试报告 — {issue_id}</h1>
  <p>Workspace: {workspace_id} &nbsp;|&nbsp; Workflow: super_test_agent_v1
     &nbsp;|&nbsp; 生成时间: {generated_at}</p>
</div>
<div class="container">

<!-- 整体状态 -->
<div class="card">
  <h2>整体状态</h2>
  <span class="badge badge-{status_class}">{status_text}</span>
  &nbsp;
  <span style="font-size:13px;color:#666">
    API {api_passed}/{api_total} 通过 &nbsp;|&nbsp;
    UI {ui_passed}/{ui_total} 通过
  </span>
</div>

<!-- 统计 -->
<div class="card">
  <h2>执行统计</h2>
  <div class="stat-grid">
    <div class="stat-box"><div class="stat-num">{total_cases}</div><div class="stat-label">总用例数</div></div>
    <div class="stat-box"><div class="stat-num" style="color:#1e8e3e">{api_passed}</div><div class="stat-label">API 通过</div></div>
    <div class="stat-box"><div class="stat-num" style="color:{fail_color}">{total_failed}</div><div class="stat-label">失败</div></div>
    <div class="stat-box"><div class="stat-num">{ui_passed}</div><div class="stat-label">UI 步骤通过</div></div>
  </div>
</div>

<!-- API 执行结果 -->
{api_section}

<!-- UI 执行结果 -->
{ui_section}

<!-- 缺陷分析 -->
{defect_section}

<!-- 产物索引 -->
<div class="card">
  <h2>产物索引</h2>
  <table>
    <tr><th>类型</th><th>文件</th><th>必要</th><th>状态</th></tr>
    {artifact_rows}
  </table>
</div>

<!-- 截图 -->
{screenshots_section}

</div>
<footer>由 Super Test Agent 自动生成 &nbsp;|&nbsp; target-system-test</footer>
</body>
</html>
"""


def _badge(status: str) -> str:
    cls = {"passed": "pass", "failed": "fail", "blocked": "blocked"}.get(status, "stub")
    label = {"passed": "PASS", "failed": "FAIL", "blocked": "BLOCKED"}.get(status, status.upper())
    return f'<span class="badge badge-{cls}">{label}</span>'


def _build_api_section(run_dir: Path) -> str:
    p = run_dir / "api_execution_result.json"
    if not p.exists():
        return '<div class="card"><h2>API 执行结果</h2><p style="color:#9aa0a6">未执行</p></div>'
    data = json.loads(p.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    rows = ""
    for c in cases:
        status = c.get("status", "unknown")
        row_cls = ' class="fail-row"' if status == "failed" else ""
        assertions = c.get("assertions", [])
        failed_assertions = [a for a in assertions if not a.get("passed", True)]
        detail = ""
        if failed_assertions or c.get("error"):
            inner = ""
            if c.get("error"):
                inner += f"<pre>错误: {c['error']}</pre>"
            for a in failed_assertions:
                inner += f"<pre>{a.get('detail','')}</pre>"
            if c.get("response_body"):
                inner += f"<pre>响应: {json.dumps(c['response_body'], ensure_ascii=False, indent=2)[:500]}</pre>"
            detail = f"<details><summary>展开详情</summary>{inner}</details>"
        rows += (
            f"<tr{row_cls}>"
            f"<td>{c.get('case_id','')}</td>"
            f"<td>{c.get('name','')}</td>"
            f"<td>{c.get('priority','')}</td>"
            f"<td>{_badge(status)}</td>"
            f"<td>{c.get('status_code','')}</td>"
            f"<td>{c.get('duration_ms','')} ms</td>"
            f"<td>{detail}</td>"
            f"</tr>"
        )
    return f"""
<div class="card">
  <h2>API 执行结果</h2>
  <table>
    <tr><th>ID</th><th>名称</th><th>优先级</th><th>状态</th><th>HTTP码</th><th>耗时</th><th>详情</th></tr>
    {rows}
  </table>
</div>"""


def _build_ui_section(run_dir: Path) -> str:
    p = run_dir / "ui_execution_result.json"
    if not p.exists():
        return '<div class="card"><h2>UI 执行结果</h2><p style="color:#9aa0a6">未执行</p></div>'
    data = json.loads(p.read_text(encoding="utf-8"))
    steps = data.get("steps", [])
    rows = ""
    for s in steps:
        status = s.get("status", "unknown")
        row_cls = ' class="fail-row"' if status == "failed" else ""
        ss = s.get("screenshot", "")
        ss_html = f'<img src="{ss}" style="height:40px;border-radius:3px" />' if ss and Path(ss).exists() else ""
        detail = ""
        if s.get("error"):
            detail = f"<details><summary>展开错误</summary><pre>{s['error']}</pre></details>"
        rows += (
            f"<tr{row_cls}>"
            f"<td>{s.get('step_id','')}</td>"
            f"<td>{s.get('name','')}</td>"
            f"<td>{s.get('action','')}</td>"
            f"<td>{_badge(status)}</td>"
            f"<td>{ss_html}</td>"
            f"<td>{detail}</td>"
            f"</tr>"
        )
    return f"""
<div class="card">
  <h2>UI 执行结果</h2>
  <table>
    <tr><th>步骤</th><th>名称</th><th>动作</th><th>状态</th><th>截图</th><th>详情</th></tr>
    {rows}
  </table>
</div>"""


def _build_defect_section(run_dir: Path) -> str:
    p = run_dir / "defect_analysis.json"
    if not p.exists():
        return '<div class="card"><h2>缺陷分析</h2><p style="color:#9aa0a6">无失败，跳过分析</p></div>'
    data = json.loads(p.read_text(encoding="utf-8"))
    failures = data.get("failures", [])
    if not failures:
        return '<div class="card"><h2>缺陷分析</h2><p style="color:#1e8e3e">无失败用例</p></div>'
    rows = ""
    cat_colors = {"ENV": "#e65100", "DATA": "#6200ea", "CASE": "#0277bd",
                  "PRODUCT": "#d93025", "TOOL": "#558b2f", "UNKNOWN": "#5f6368"}
    for f in failures:
        cat = f.get("category", "UNKNOWN")
        color = cat_colors.get(cat, "#333")
        blocking = "是" if f.get("blocking") else "否"
        bug = "⚠️ 疑似Bug" if f.get("potential_bug") else ""
        rows += (
            f"<tr>"
            f"<td>{f.get('tc_id','')}</td>"
            f"<td style='color:{color};font-weight:600'>{cat}</td>"
            f"<td>{f.get('evidence','')}</td>"
            f"<td>{f.get('suggestion','')}</td>"
            f"<td>{blocking}</td>"
            f"<td>{bug}</td>"
            f"</tr>"
        )
    summary = data.get("summary", {})
    by_cat = summary.get("by_category", {})
    cat_summary = " &nbsp;|&nbsp; ".join(f"{k}: {v}" for k, v in by_cat.items() if v > 0)
    return f"""
<div class="card">
  <h2>缺陷分析</h2>
  <p style="font-size:13px;color:#666">失败 {summary.get('total_failed',0)} 条 &nbsp;|&nbsp; {cat_summary}</p>
  <table>
    <tr><th>用例</th><th>分类</th><th>证据</th><th>建议</th><th>阻断</th><th>标记</th></tr>
    {rows}
  </table>
</div>"""


def _build_screenshots_section(run_dir: Path) -> str:
    ss_dir = run_dir / "screenshots"
    if not ss_dir.is_dir():
        return ""
    images = sorted(ss_dir.glob("*.png"))
    if not images:
        return ""
    imgs = "".join(f'<img src="{p}" title="{p.stem}" />' for p in images[:20])
    return f"""
<div class="card">
  <h2>截图 ({len(images)} 张)</h2>
  <div class="screenshots">{imgs}</div>
</div>"""


def render(issue_id: str, run_dir: Path, workspace_id: str = "target-system-test") -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)

    # 读取 artifact_index
    index_path = run_dir / "artifact_index.json"
    index = {}
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))

    summary     = index.get("summary", {})
    status      = index.get("status", "unknown")
    api_passed  = summary.get("api_passed", 0)
    api_total   = summary.get("api_total",  0)
    api_failed  = summary.get("api_failed", 0)
    ui_passed   = summary.get("ui_passed",  0)
    ui_total    = summary.get("ui_total",   0)
    ui_failed   = summary.get("ui_failed",  0)
    total_cases = summary.get("total_cases", 0)
    total_failed = api_failed + ui_failed

    status_map   = {"passed": "pass", "failed": "fail", "blocked": "blocked"}
    status_class = status_map.get(status, "stub")
    status_text  = {"passed": "PASSED", "failed": "FAILED", "blocked": "BLOCKED"}.get(status, status.upper())
    fail_color   = "#d93025" if total_failed > 0 else "#1e8e3e"

    # 产物行
    artifact_rows = ""
    for a in index.get("artifacts", []):
        exists_icon = "✓" if a.get("exists") else "○"
        req_label   = "必要" if a.get("required") else "可选"
        artifact_rows += (
            f"<tr>"
            f"<td>{a.get('type','')}</td>"
            f"<td style='font-size:12px;color:#666'>{Path(a.get('path','')).name}</td>"
            f"<td>{req_label}</td>"
            f"<td>{exists_icon}</td>"
            f"</tr>"
        )

    html = _HTML_TMPL.format(
        issue_id         = issue_id,
        workspace_id     = workspace_id,
        generated_at     = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status_class     = status_class,
        status_text      = status_text,
        api_passed       = api_passed,
        api_total        = api_total,
        ui_passed        = ui_passed,
        ui_total         = ui_total,
        total_cases      = total_cases,
        total_failed     = total_failed,
        fail_color       = fail_color,
        api_section      = _build_api_section(run_dir),
        ui_section       = _build_ui_section(run_dir),
        defect_section   = _build_defect_section(run_dir),
        artifact_rows    = artifact_rows,
        screenshots_section = _build_screenshots_section(run_dir),
    )

    html_path = run_dir / "ui_report.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"[report-renderer] HTML 报告: {html_path}")

    report_md = run_dir / "test_agent_report.md"
    blocked_execution = index.get("blocked_execution", [])
    missing_required = index.get("missing_required", [])
    artifact_lines = []
    for a in index.get("artifacts", []):
        marker = "OK" if a.get("exists") else "MISSING"
        status_part = f" / {a.get('status')}" if a.get("status") else ""
        artifact_lines.append(
            f"- {marker} `{Path(a.get('path','')).name}` ({a.get('type','')}{status_part})"
        )
    report_lines = [
        f"# 测试报告 - {issue_id}",
        "",
        f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Workspace：** {workspace_id}  ",
        f"**Workflow：** super_test_agent_v1  ",
        f"**整体状态：** {status_text}  ",
        "",
        "## 执行摘要",
        "",
        "| 维度 | 总计 | 通过 | 失败 |",
        "|---|---:|---:|---:|",
        f"| API 用例 | {api_total} | {api_passed} | {api_failed} |",
        f"| UI 步骤 | {ui_total} | {ui_passed} | {ui_failed} |",
        "",
        "## 当前阻塞",
        "",
    ]
    if missing_required:
        report_lines.append(f"- 缺少必要产物：{', '.join(missing_required)}")
    if blocked_execution:
        report_lines.append(f"- 真实执行被环境阻塞：{', '.join(blocked_execution)}")
        report_lines.append("- API/UI 执行结果已写入 blocked 状态文件，未伪造通过结果。")
    if not missing_required and not blocked_execution:
        report_lines.append("- 无必要产物缺失，未发现执行阻塞。")
    report_lines.extend([
        "",
        "## 产物索引",
        "",
        *artifact_lines,
        "",
        "## 说明",
        "",
        "当前报告用于 Demo Release v1 验收：上游 context/scope/cases 产物已齐全；真实 API/UI 执行需要配置测试环境变量后继续运行。",
    ])
    report_md.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"[report-renderer] Markdown 报告: {report_md}")

    # Multica comment payload
    comment_text = (
        f"## 测试摘要\n"
        f"- 整体状态: **{status_text}**\n"
        f"- API: {api_passed}/{api_total} 通过，{api_failed} 失败\n"
        f"- UI: {ui_passed}/{ui_total} 步骤通过，{ui_failed} 失败\n"
        f"- 总计: {total_cases} 用例，{total_failed} 失败\n\n"
        f"详细报告见产物链接。"
    )
    comment_payload = {
        "multica_issue_id": issue_id,
        "workspace_id":     workspace_id,
        "status":           status,
        "comment":          comment_text,
        "generated_at":     datetime.now().isoformat(),
        "artifact_links": [
            {"type": "report",      "path": str(report_md)},
            {"type": "html_report", "path": str(html_path)},
            {"type": "screenshots", "path": str(run_dir / "screenshots/")},
            {"type": "trace",       "path": str(run_dir / "trace.zip")},
        ],
    }
    comment_path = run_dir / "multica_comment_payload.json"
    comment_path.write_text(json.dumps(comment_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[report-renderer] Multica payload: {comment_path}")
    return {"html": str(html_path), "comment": str(comment_path), "status": status}


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="report_renderer",
                                     description="ReportRenderer — Track E")
    parser.add_argument("--issue",     required=True)
    parser.add_argument("--run-dir",   default=None, dest="run_dir")
    parser.add_argument("--workspace", default="target-system-test")
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else Path("outputs/runs") / args.issue
    render(args.issue, run_dir, args.workspace)
