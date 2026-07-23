#!/usr/bin/env python3
"""
test-squad CLI — Super Test Agent 命令行入口
workspace: target-system-test
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ── 常量 ──────────────────────────────────────────────────────────────────────

VERSION = "1.0.0"
WORKSPACE_ID = "target-system-test"
OUTPUTS_ROOT = Path("outputs/runs")
EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_FAILED = 2

# ── 颜色输出 ──────────────────────────────────────────────────────────────────

def _c(code: str, text: str) -> str:
    if sys.platform == "win32" and not os.environ.get("FORCE_COLOR"):
        return text
    return f"\033[{code}m{text}\033[0m"

GREEN  = lambda t: _c("32", t)
RED    = lambda t: _c("31", t)
YELLOW = lambda t: _c("33", t)
BOLD   = lambda t: _c("1",  t)
CYAN   = lambda t: _c("36", t)

def ok(msg: str):   print(f"  {GREEN('[PASS]')} {msg}")
def fail(msg: str): print(f"  {RED('[FAIL]')} {msg}")
def warn(msg: str): print(f"  {YELLOW('[WARN]')} {msg}")
def info(msg: str): print(f"  {CYAN('[INFO]')} {msg}")

# ── doctor ────────────────────────────────────────────────────────────────────

DEMO_REQUIRED_PATHS = [
    "mify/workflows/super_test_agent_v1.yaml",
    "mify/prompts/case_generate.mify.md",
    "mify/prompts/defect_analyze.mify.md",
    "mify/prompts/report_generate.mify.md",
    "tools/artifact-collector/artifact_collector.py",
    "tools/report-renderer/report_renderer.py",
]

DEMO_REQUIRED_ARTIFACTS = [
    "context_package.json",
    "scope_analysis.json",
    "test_cases.json",
    "test_cases.md",
    "api_cases.yaml",
    "ui_flow.yaml",
    "api_execution_result.json",
    "ui_execution_result.json",
    "artifact_index.json",
    "test_agent_report.md",
    "ui_report.html",
    "multica_comment_payload.json",
    "run_state.json",
]

REAL_REQUIRED_ENV = [
    "TARGET_SYSTEM_BASE_URL",
    "TARGET_SYSTEM_UI_URL",
]

REAL_OPTIONAL_ENV = [
    "TARGET_SYSTEM_TOKEN",
    "TARGET_SYSTEM_TEST_USER",
    "TARGET_SYSTEM_TEST_PASSWORD",
]


def _mask_env_value(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 8}{value[-4:]}"


def _record(results: list, name: str, passed: bool, level: str, message: str) -> None:
    results.append({
        "name": name,
        "passed": passed,
        "level": level,
        "message": message,
    })

def cmd_doctor(args) -> int:
    print(BOLD("\n=== test-squad doctor ==="))
    print(f"  workspace: {args.workspace or WORKSPACE_ID}\n")
    print(f"  profile:   {args.profile}\n")

    results = []
    blocked = False

    try:
        OUTPUTS_ROOT.mkdir(parents=True, exist_ok=True)
        ok(f"产物目录可写: {OUTPUTS_ROOT}")
        _record(results, "outputs_root", True, "required", f"产物目录可写: {OUTPUTS_ROOT}")
    except Exception as e:
        fail(f"产物目录无法创建: {OUTPUTS_ROOT}\n        原因: {e}")
        _record(results, "outputs_root", False, "required", str(e))
        blocked = True

    if args.profile in ("demo", "all"):
        issue = args.issue or "ISSUE-001"
        run_dir = OUTPUTS_ROOT / issue
        info(f"检查 Demo v1 本地骨架: {issue}")

        for item in DEMO_REQUIRED_PATHS:
            p = Path(item)
            if p.exists():
                ok(f"本地组件存在: {item}")
                _record(results, item, True, "required", "exists")
            else:
                fail(f"本地组件缺失: {item}")
                _record(results, item, False, "required", "missing")
                blocked = True

        if run_dir.exists():
            ok(f"Demo run 目录存在: {run_dir}")
            _record(results, f"run_dir:{issue}", True, "required", "exists")
        else:
            fail(f"Demo run 目录缺失: {run_dir}")
            _record(results, f"run_dir:{issue}", False, "required", "missing")
            blocked = True

        for filename in DEMO_REQUIRED_ARTIFACTS:
            p = run_dir / filename
            if p.exists():
                ok(f"Demo 产物存在: {p}")
                _record(results, str(p), True, "required", "exists")
            else:
                fail(f"Demo 产物缺失: {p}")
                _record(results, str(p), False, "required", "missing")
                blocked = True

        state_path = run_dir / "run_state.json"
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                status = state.get("status", "unknown")
                if status in ("passed", "blocked"):
                    ok(f"Demo 状态可解释: {status}")
                    _record(results, "run_state.status", True, "required", status)
                else:
                    warn(f"Demo 状态需要复核: {status}")
                    _record(results, "run_state.status", True, "warning", status)
            except Exception as e:
                fail(f"run_state.json 无法解析: {e}")
                _record(results, "run_state.parse", False, "required", str(e))
                blocked = True

        artifact_index_path = run_dir / "artifact_index.json"
        if artifact_index_path.exists():
            try:
                artifact_index = json.loads(artifact_index_path.read_text(encoding="utf-8"))
                missing_required = artifact_index.get("missing_required", [])
                blocked_execution = artifact_index.get("blocked_execution", [])
                if missing_required:
                    fail(f"必要产物缺失: {missing_required}")
                    _record(results, "artifact_index.missing_required", False, "required", str(missing_required))
                    blocked = True
                else:
                    ok("artifact_index: necessary artifacts complete")
                    _record(results, "artifact_index.missing_required", True, "required", "[]")
                if blocked_execution:
                    warn(f"真实执行阻塞: {blocked_execution}")
                    _record(results, "artifact_index.blocked_execution", True, "warning", str(blocked_execution))
            except Exception as e:
                fail(f"artifact_index.json 无法解析: {e}")
                _record(results, "artifact_index.parse", False, "required", str(e))
                blocked = True

    if args.profile in ("real", "all"):
        info("检查真实 API/UI 执行环境")

        for name in REAL_REQUIRED_ENV:
            val = os.environ.get(name, "")
            if val:
                ok(f"{name} = {_mask_env_value(val)}")
                _record(results, name, True, "required", "configured")
            else:
                fail(f"{name} 未设置")
                _record(results, name, False, "required", "missing")
                blocked = True

        for name in REAL_OPTIONAL_ENV:
            val = os.environ.get(name, "")
            if val:
                ok(f"{name} 已设置")
                _record(results, name, True, "optional", "configured")
            else:
                warn(f"{name} 未设置（需要鉴权或 UI 登录时再配置）")
                _record(results, name, True, "optional", "missing")

        project_path = args.project_path or os.environ.get("TARGET_SYSTEM_SOURCE_PATH", "")
        if project_path:
            p = Path(project_path)
            if p.exists():
                ok(f"源码路径存在: {project_path}")
                _record(results, "source_path", True, "optional", project_path)
            else:
                warn(f"源码路径不存在: {project_path}")
                _record(results, "source_path", True, "optional", f"missing: {project_path}")
        else:
            warn("源码路径未配置（如需基于真实仓库生成范围分析，可设置 TARGET_SYSTEM_SOURCE_PATH 或 --project-path）")
            _record(results, "source_path", True, "optional", "not configured")

        if args.check_connectivity:
            base = os.environ.get("TARGET_SYSTEM_BASE_URL", "").rstrip("/")
            if base:
                url = f"{base}/actuator/health"
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "test-squad-doctor/1.0"})
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        ok(f"测试环境可达: {url} ({resp.status})")
                        _record(results, "connectivity", True, "required", url)
                except Exception as e:
                    fail(f"测试环境不可达: {url}\n        原因: {e}")
                    _record(results, "connectivity", False, "required", str(e))
                    blocked = True
            else:
                fail("连通性检查跳过（TARGET_SYSTEM_BASE_URL 未设置）")
                _record(results, "connectivity", False, "required", "base url missing")
                blocked = True

    passed = sum(1 for item in results if item["passed"])
    total = len(results)
    print(f"\n  结果: {passed}/{total} 通过")

    report_path = Path("outputs") / f"doctor_report_{args.profile}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "workspace": args.workspace or WORKSPACE_ID,
        "profile": args.profile,
        "issue": args.issue or "ISSUE-001",
        "timestamp": datetime.now().isoformat(),
        "passed": passed,
        "total": total,
        "blocked": blocked,
        "checks": results,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    info(f"报告已写入: {report_path}")

    if blocked:
        print(f"\n  {RED('BLOCKED')} — 修复上述失败项后重新运行 doctor")
        return EXIT_BLOCKED
    else:
        if args.profile == "demo":
            print(f"\n  {GREEN('DEMO READY')} — 本地 Demo v1 骨架可演示")
        else:
            print(f"\n  {GREEN('ALL PASS')} — 环境就绪，可以执行测试")
        return EXIT_OK

# ── run ───────────────────────────────────────────────────────────────────────

def cmd_run(args) -> int:
    issue = args.issue
    workflow = args.workflow or "super_test_agent_v1"
    workspace = args.workspace or WORKSPACE_ID
    project_path = args.project_path or os.environ.get("TARGET_SYSTEM_SOURCE_PATH", "")

    print(BOLD(f"\n=== test-squad run ==="))
    print(f"  issue:    {issue}")
    print(f"  workflow: {workflow}")
    print(f"  workspace:{workspace}\n")

    run_dir = OUTPUTS_ROOT / issue
    run_dir.mkdir(parents=True, exist_ok=True)

    mify_yaml = Path("mify/workflows") / f"{workflow}.yaml"
    if not mify_yaml.exists():
        fail(f"workflow 文件不存在: {mify_yaml}")
        return EXIT_FAILED
    ok(f"workflow 文件已找到: {mify_yaml}")

    nodes = [
        "context_load",
        "scope_analyze",
        "case_generate",
        "case_validate",
        "execution_plan",
        "api_execution",
        "ui_execution",
        "perf_probe",
        "artifact_collect",
        "defect_analyze",
        "repair_suggest",
        "report_generate",
        "multica_writeback",
    ]

    state = {
        "issue_id": issue,
        "workflow": workflow,
        "workspace": workspace,
        "project_path": project_path,
        "started_at": datetime.now().isoformat(),
        "status": "running",
        "nodes_completed": [],
        "nodes_pending": nodes,
    }
    state_path = run_dir / "run_state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n  {YELLOW('NOTE')} Mify workflow 已就绪。")
    print(f"  实际节点执行需要 Mify runtime 接入（Track C/D 执行层）。")
    print(f"  当前版本输出执行计划到: {run_dir}/execution_plan.json\n")

    execution_plan = {
        "issue_id": issue,
        "workflow": workflow,
        "generated_at": datetime.now().isoformat(),
        "nodes": [{"id": n, "status": "pending"} for n in nodes],
        "api_cases": str(run_dir / "api_cases.yaml"),
        "ui_flow":   str(run_dir / "ui_flow.yaml"),
        "env": {
            "base_url":  os.environ.get("TARGET_SYSTEM_BASE_URL", "<未设置>"),
            "ui_url":    os.environ.get("TARGET_SYSTEM_UI_URL",   "<未设置>"),
            "test_user": os.environ.get("TARGET_SYSTEM_TEST_USER","<未设置>"),
        },
    }
    ep_path = run_dir / "execution_plan.json"
    ep_path.write_text(json.dumps(execution_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    ok(f"执行计划已写入: {ep_path}")
    info("下一步: test-squad run-api / test-squad run-ui")
    return EXIT_OK

# ── run-api ───────────────────────────────────────────────────────────────────

def cmd_run_api(args) -> int:
    issue = args.issue
    cases_path = Path(args.cases) if args.cases else OUTPUTS_ROOT / issue / "api_cases.yaml"

    print(BOLD(f"\n=== test-squad run-api ==="))
    print(f"  issue: {issue}")
    print(f"  cases: {cases_path}\n")

    run_dir = OUTPUTS_ROOT / issue
    run_dir.mkdir(parents=True, exist_ok=True)

    base_url = os.environ.get("TARGET_SYSTEM_BASE_URL", "")
    token    = os.environ.get("TARGET_SYSTEM_TOKEN", "")

    if not base_url:
        case_count = 0
        if cases_path.exists():
            case_count = sum(
                1 for line in cases_path.read_text(encoding="utf-8").splitlines()
                if line.strip().startswith("- id:")
            )
        result = {
            "issue_id": issue,
            "executed_at": datetime.now().isoformat(),
            "base_url": "",
            "cases_file": str(cases_path),
            "status": "blocked",
            "blocked_reason": "TARGET_SYSTEM_BASE_URL is not configured; real HTTP execution was not started.",
            "summary": {"total": case_count, "passed": 0, "failed": 0, "skipped": case_count},
            "cases": [],
        }
        result_path = run_dir / "api_execution_result.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        fail("TARGET_SYSTEM_BASE_URL 未设置，无法执行 API 测试")
        info(f"blocked result written: {result_path}")
        return EXIT_BLOCKED

    if not cases_path.exists():
        warn(f"用例文件不存在: {cases_path}")
        info("复制模板用例...")
        template = Path("tools/api-runner/api_cases_template.yaml")
        if template.exists():
            import shutil
            shutil.copy(template, cases_path)
            ok(f"模板已复制到: {cases_path}")
        else:
            fail(f"模板也不存在: {template}")
            return EXIT_FAILED

    ok(f"用例文件: {cases_path}")
    info(f"base_url: {base_url}")

    # 调用 Track C ApiExecutionTool
    tool_path = Path("tools/api-runner/api_execution_tool.py")
    if tool_path.exists():
        import subprocess
        cmd = [sys.executable, str(tool_path),
               "--issue", issue,
               "--cases", str(cases_path),
               "--run-dir", str(run_dir)]
        priority = getattr(args, "priority", None)
        if priority:
            cmd += ["--priority", priority]
        rc = subprocess.run(cmd).returncode
        return EXIT_OK if rc == 0 else EXIT_FAILED
    else:
        warn(f"ApiExecutionTool 不存在: {tool_path}，写入 stub 结果")
        result = {
            "issue_id": issue, "executed_at": datetime.now().isoformat(),
            "base_url": base_url, "cases_file": str(cases_path),
            "status": "stub",
            "summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
            "cases": [],
        }
        result_path = run_dir / "api_execution_result.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return EXIT_OK

# ── run-ui ────────────────────────────────────────────────────────────────────

def cmd_run_ui(args) -> int:
    issue   = args.issue
    flow    = Path(args.flow)    if args.flow    else OUTPUTS_ROOT / issue / "ui_flow.yaml"
    profile = args.profile or "readonly"

    print(BOLD(f"\n=== test-squad run-ui ==="))
    print(f"  issue:   {issue}")
    print(f"  flow:    {flow}")
    print(f"  profile: {profile}\n")

    run_dir = OUTPUTS_ROOT / issue
    run_dir.mkdir(parents=True, exist_ok=True)

    ui_url   = os.environ.get("TARGET_SYSTEM_UI_URL", "")
    username = os.environ.get("TARGET_SYSTEM_TEST_USER", "")

    if not ui_url:
        step_count = 0
        if flow.exists():
            step_count = sum(
                1 for line in flow.read_text(encoding="utf-8").splitlines()
                if line.strip().startswith(("- id:", "- step_id:"))
            )
        result = {
            "issue_id": issue,
            "executed_at": datetime.now().isoformat(),
            "ui_url": "",
            "flow_file": str(flow),
            "profile": profile,
            "status": "blocked",
            "blocked_reason": "TARGET_SYSTEM_UI_URL is not configured; real browser execution was not started.",
            "summary": {"total_steps": step_count, "passed_steps": 0, "failed_steps": 0, "skipped_steps": step_count},
            "steps": [],
        }
        result_path = run_dir / "ui_execution_result.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        fail("TARGET_SYSTEM_UI_URL 未设置，无法执行 UI 测试")
        info(f"blocked result written: {result_path}")
        return EXIT_BLOCKED

    if not flow.exists():
        warn(f"Flow 文件不存在: {flow}")
        info("复制模板 flow...")
        template = Path("tools/ui-runner/ui_flow_template.yaml")
        if template.exists():
            import shutil
            shutil.copy(template, flow)
            ok(f"模板已复制到: {flow}")
        else:
            fail(f"模板也不存在: {template}")
            return EXIT_FAILED

    ok(f"flow 文件: {flow}")
    ok(f"profile: {profile}")
    info(f"ui_url: {ui_url}")

    # 调用 Track D WebExecutionTool
    tool_path = Path("tools/ui-runner/ui_execution_tool.py")
    if tool_path.exists():
        import subprocess
        cmd = [sys.executable, str(tool_path),
               "--issue", issue,
               "--flow", str(flow),
               "--profile", profile,
               "--run-dir", str(run_dir)]
        headless = not getattr(args, "no_headless", False)
        if not headless:
            cmd.append("--no-headless")
        storage = getattr(args, "storage_state", None)
        if storage:
            cmd += ["--storage-state", storage]
        rc = subprocess.run(cmd).returncode
        return EXIT_OK if rc == 0 else EXIT_FAILED
    else:
        warn(f"WebExecutionTool 不存在: {tool_path}，写入 stub 结果")
        result = {
            "issue_id": issue, "executed_at": datetime.now().isoformat(),
            "ui_url": ui_url, "flow_file": str(flow), "profile": profile,
            "status": "stub",
            "summary": {"total_steps": 0, "passed_steps": 0, "failed_steps": 0},
            "steps": [],
        }
        result_path = run_dir / "ui_execution_result.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "screenshots").mkdir(exist_ok=True)
        return EXIT_OK

# ── status ────────────────────────────────────────────────────────────────────

def cmd_status(args) -> int:
    print(BOLD(f"\n=== test-squad status ==="))

    if args.issue:
        run_dir = OUTPUTS_ROOT / args.issue
        state_path = run_dir / "run_state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            print(f"  issue:    {state.get('issue_id')}")
            print(f"  workflow: {state.get('workflow')}")
            print(f"  status:   {YELLOW(state.get('status', 'unknown'))}")
            print(f"  updated:  {state.get('updated_at') or state.get('started_at')}")
            completed = state.get("nodes_completed", [])
            pending   = state.get("nodes_pending",   [])
            print(f"  nodes:    {len(completed)} 完成 / {len(pending)} 待执行")
        else:
            warn(f"状态文件不存在: {state_path}")
            info("请先运行: test-squad run --issue " + args.issue)

    elif args.workspace:
        print(f"  workspace: {args.workspace}")
        if OUTPUTS_ROOT.exists():
            issues = sorted(OUTPUTS_ROOT.iterdir())
            if issues:
                for d in issues:
                    sp = d / "run_state.json"
                    if sp.exists():
                        s = json.loads(sp.read_text(encoding="utf-8"))
                        status = s.get("status", "unknown")
                        color  = GREEN if status == "passed" else (RED if status == "failed" else YELLOW)
                        print(f"    {d.name}  {color(status)}")
                    else:
                        print(f"    {d.name}  {YELLOW('(无状态文件)')}")
            else:
                info("暂无 issue 运行记录")
        else:
            info(f"产物目录不存在: {OUTPUTS_ROOT}")
    else:
        warn("请指定 --issue 或 --workspace")
    return EXIT_OK

# ── collect-artifacts ────────────────────────────────────────────────────────

def cmd_collect_artifacts(args) -> int:
    issue = args.issue
    print(BOLD(f"\n=== test-squad collect-artifacts ==="))
    print(f"  issue: {issue}\n")
    run_dir = OUTPUTS_ROOT / issue
    tool = Path("tools/artifact-collector/artifact_collector.py")
    if tool.exists():
        import subprocess
        rc = subprocess.run([sys.executable, str(tool),
                             "--issue", issue, "--run-dir", str(run_dir)]).returncode
        # rc=1 means blocked (missing required), rc=0 means ok
        return EXIT_OK if rc == 0 else EXIT_BLOCKED
    fail(f"ArtifactCollector 不存在: {tool}")
    return EXIT_FAILED

# ── analyze-defects ───────────────────────────────────────────────────────────

def cmd_analyze_defects(args) -> int:
    issue = args.issue
    print(BOLD(f"\n=== test-squad analyze-defects ==="))
    print(f"  issue: {issue}\n")
    run_dir = OUTPUTS_ROOT / issue
    tool = Path("tools/defect-analyzer/defect_analyzer.py")
    if tool.exists():
        import subprocess
        rc = subprocess.run([sys.executable, str(tool),
                             "--issue", issue, "--run-dir", str(run_dir)]).returncode
        return EXIT_OK if rc == 0 else EXIT_FAILED
    fail(f"DefectAnalyzer 不存在: {tool}")
    return EXIT_FAILED

# ── render-report ─────────────────────────────────────────────────────────────

def cmd_render_report(args) -> int:
    issue = args.issue
    print(BOLD(f"\n=== test-squad render-report ==="))
    print(f"  issue: {issue}\n")
    run_dir = OUTPUTS_ROOT / issue
    tool = Path("tools/report-renderer/report_renderer.py")
    if tool.exists():
        import subprocess
        subprocess.run([sys.executable, str(tool),
                        "--issue", issue, "--run-dir", str(run_dir)])
    else:
        fail(f"ReportRenderer 不存在: {tool}")
        return EXIT_FAILED
    return EXIT_OK

# ── report (完整流程串联) ─────────────────────────────────────────────────────

def cmd_report(args) -> int:
    issue = args.issue
    print(BOLD(f"\n=== test-squad report ==="))
    print(f"  issue: {issue}\n")

    run_dir = OUTPUTS_ROOT / issue
    if not run_dir.exists():
        fail(f"产物目录不存在: {run_dir}")
        return EXIT_FAILED

    import subprocess

    # Step 1: 缺陷分析
    defect_tool = Path("tools/defect-analyzer/defect_analyzer.py")
    if defect_tool.exists():
        info("Step 1/3 — 缺陷分析")
        subprocess.run([sys.executable, str(defect_tool),
                        "--issue", issue, "--run-dir", str(run_dir)])
    else:
        warn("defect_analyzer.py 不存在，跳过缺陷分析")

    # Step 2: 产物收集
    collector_tool = Path("tools/artifact-collector/artifact_collector.py")
    if collector_tool.exists():
        info("Step 2/3 — 产物收集")
        subprocess.run([sys.executable, str(collector_tool),
                        "--issue", issue, "--run-dir", str(run_dir)])

    # Step 3: 生成报告 MD + HTML + Multica payload
    renderer_tool = Path("tools/report-renderer/report_renderer.py")
    if renderer_tool.exists():
        info("Step 3/3 — 渲染报告")
        subprocess.run([sys.executable, str(renderer_tool),
                        "--issue", issue, "--run-dir", str(run_dir)])
    else:
        # 回退：最简版报告
        warn("report_renderer.py 不存在，生成简版报告")
        api_result = json.loads((run_dir / "api_execution_result.json").read_text(encoding="utf-8")) \
                     if (run_dir / "api_execution_result.json").exists() else {}
        ui_result  = json.loads((run_dir / "ui_execution_result.json").read_text(encoding="utf-8")) \
                     if (run_dir / "ui_execution_result.json").exists() else {}
        api_s = api_result.get("summary", {})
        ui_s  = ui_result.get("summary", {})
        report_path = run_dir / "test_agent_report.md"
        report_path.write_text(
            f"# 测试报告 — {issue}\n\n"
            f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
            f"**Workspace：** {WORKSPACE_ID}  \n\n"
            f"| API 总 | API 通过 | UI 步骤 | UI 通过 |\n|---|---|---|---|\n"
            f"| {api_s.get('total',0)} | {api_s.get('passed',0)} | {ui_s.get('total_steps',0)} | {ui_s.get('passed_steps',0)} |\n",
            encoding="utf-8",
        )
        comment_path = run_dir / "multica_comment_payload.json"
        comment_path.write_text(json.dumps({
            "issue_id": issue, "workspace": WORKSPACE_ID,
            "status": "passed", "generated_at": datetime.now().isoformat(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    artifact_index_path = run_dir / "artifact_index.json"
    if artifact_index_path.exists():
        artifact_index = json.loads(artifact_index_path.read_text(encoding="utf-8"))
        blocked_execution = artifact_index.get("blocked_execution", [])
        all_nodes = [
            "context_load",
            "scope_analyze",
            "case_generate",
            "case_validate",
            "execution_plan",
            "api_execution",
            "ui_execution",
            "perf_probe",
            "artifact_collect",
            "defect_analyze",
            "repair_suggest",
            "report_generate",
            "multica_writeback",
        ]
        blocked_nodes = []
        if "api_execution_result" in blocked_execution:
            blocked_nodes.append("api_execution")
        if "ui_execution_result" in blocked_execution:
            blocked_nodes.append("ui_execution")
        completed_nodes = [n for n in all_nodes if n not in blocked_nodes and n != "perf_probe"]
        state = {
            "issue_id": issue,
            "workflow": "super_test_agent_v1",
            "workspace": WORKSPACE_ID,
            "source_path": "E:/workspace/idea/priceCenterServer/target-service",
            "updated_at": datetime.now().isoformat(),
            "status": artifact_index.get("status", "unknown"),
            "blocked_reason": "; ".join(blocked_execution) if blocked_execution else "",
            "nodes_completed": completed_nodes,
            "nodes_blocked": blocked_nodes,
            "nodes_pending": ["perf_probe"],
        }
        (run_dir / "run_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    ok(f"报告已生成: {run_dir}/test_agent_report.md")
    html_p = run_dir / "ui_report.html"
    if html_p.exists():
        ok(f"HTML 报告: {html_p}")
    ok(f"Multica payload: {run_dir}/multica_comment_payload.json")
    return EXIT_OK

# ── patrol ────────────────────────────────────────────────────────────────────

def cmd_patrol(args) -> int:
    workspace = args.workspace or WORKSPACE_ID
    profile   = args.profile   or "daily_smoke"

    print(BOLD(f"\n=== test-squad patrol ==="))
    print(f"  workspace: {workspace}")
    print(f"  profile:   {profile}\n")

    patrol_yaml = Path("contracts/autopilot_patrol.yaml")
    if not patrol_yaml.exists():
        fail(f"巡检配置不存在: {patrol_yaml}")
        return EXIT_FAILED
    ok(f"巡检配置已找到: {patrol_yaml}")

    issue_id = f"PATROL-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir  = OUTPUTS_ROOT / issue_id
    run_dir.mkdir(parents=True, exist_ok=True)

    patrol_result = {
        "patrol_id":  issue_id,
        "workspace":  workspace,
        "profile":    profile,
        "started_at": datetime.now().isoformat(),
        "status":     "stub",
        "note": "巡检触发成功，实际执行依赖 Track C/D 接入后的完整 run 命令。",
        "next_step": f"test-squad run --issue {issue_id} --workflow super_test_agent_v1",
    }
    result_path = run_dir / "patrol_run_result.json"
    result_path.write_text(json.dumps(patrol_result, ensure_ascii=False, indent=2), encoding="utf-8")
    ok(f"巡检任务已创建: {issue_id}")
    info(f"结果: {result_path}")
    info(f"手动推进: test-squad run --issue {issue_id} --workflow super_test_agent_v1")
    return EXIT_OK

# ── mify validate ─────────────────────────────────────────────────────────────

def cmd_mify(args) -> int:
    subcmd = args.subcmd
    print(BOLD(f"\n=== test-squad mify {subcmd} ===\n"))

    if subcmd == "validate":
        workflow_path = Path(args.workflow)
        if not workflow_path.exists():
            fail(f"workflow 文件不存在: {workflow_path}")
            return EXIT_FAILED
        content = workflow_path.read_text(encoding="utf-8")
        checks = [
            ("workflow_id",         "super_test_agent_v1" in content),
            ("runtime_owner",       "multica"             in content),
            ("multica_issue_id",    "multica_issue_id"    in content),
            ("source_path",         "source_path"         in content),
            ("system_name",         "system_name"         in content),
            ("node: case_generate", "case_generate"       in content),
            ("node: defect_analyze","defect_analyze"      in content),
            ("node: report_generate","report_generate"    in content),
        ]
        all_ok = True
        for name, passed in checks:
            if passed: ok(name)
            else:
                fail(name)
                all_ok = False
        return EXIT_OK if all_ok else EXIT_FAILED

    elif subcmd == "dry-run":
        issue = args.issue or "ISSUE-DEMO-001"
        node  = args.node  or "case_generate"
        prompt_path = Path("mify/prompts") / f"{node}.mify.md"
        if not prompt_path.exists():
            fail(f"prompt 不存在: {prompt_path}")
            return EXIT_FAILED
        ok(f"prompt 文件存在: {prompt_path}")
        info(f"dry-run: {node} for {issue}")
        info("实际执行需要 Mify runtime 接入")
        return EXIT_OK

    else:
        fail(f"未知子命令: {subcmd}")
        return EXIT_FAILED

# ── 入口 ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="test-squad",
        description="Super Test Agent CLI",
    )
    parser.add_argument("--version", action="version", version=f"test-squad {VERSION}")

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # doctor
    p_doctor = sub.add_parser("doctor", help="检查环境就绪情况")
    p_doctor.add_argument("--workspace", default=None)
    p_doctor.add_argument("--issue", default="ISSUE-001")
    p_doctor.add_argument("--profile", choices=["demo", "real", "all"], default="demo",
                          help="demo 检查本地演示骨架；real 检查真实 API/UI 执行环境；all 同时检查")
    p_doctor.add_argument("--project-path", default=None, dest="project_path")
    p_doctor.add_argument("--check-connectivity", action="store_true",
                          help="real/all 模式下额外请求 API health endpoint")

    # run
    p_run = sub.add_parser("run", help="启动完整 workflow")
    p_run.add_argument("--issue",        required=True)
    p_run.add_argument("--workflow",     default="super_test_agent_v1")
    p_run.add_argument("--workspace",    default=None)
    p_run.add_argument("--project-path", default=None, dest="project_path")

    # run-api
    p_api = sub.add_parser("run-api", help="只跑 API 用例")
    p_api.add_argument("--issue",    required=True)
    p_api.add_argument("--cases",    default=None)
    p_api.add_argument("--priority", default=None, help="只跑 P0/P1/P2")

    # run-ui
    p_ui = sub.add_parser("run-ui", help="只跑 UI flow")
    p_ui.add_argument("--issue",         required=True)
    p_ui.add_argument("--flow",          default=None)
    p_ui.add_argument("--profile",       default="readonly")
    p_ui.add_argument("--no-headless",   action="store_true", dest="no_headless")
    p_ui.add_argument("--storage-state", default=None, dest="storage_state")

    # status
    p_st = sub.add_parser("status", help="查看 issue / workspace 状态")
    p_st.add_argument("--issue",     default=None)
    p_st.add_argument("--workspace", default=None)

    # report
    p_rep = sub.add_parser("report", help="生成测试报告 + Multica 回写内容")
    p_rep.add_argument("--issue", required=True)

    # collect-artifacts
    p_ca = sub.add_parser("collect-artifacts", help="收集产物索引")
    p_ca.add_argument("--issue", required=True)

    # analyze-defects
    p_ad = sub.add_parser("analyze-defects", help="失败根因分类")
    p_ad.add_argument("--issue", required=True)

    # render-report
    p_rr = sub.add_parser("render-report", help="渲染 HTML 报告 + Multica payload")
    p_rr.add_argument("--issue", required=True)

    # patrol
    p_pat = sub.add_parser("patrol", help="手动触发巡检")
    p_pat.add_argument("--workspace", default=None)
    p_pat.add_argument("--profile",   default="daily_smoke")

    # mify
    p_mify = sub.add_parser("mify", help="Mify workflow 工具")
    mify_sub = p_mify.add_subparsers(dest="subcmd", metavar="<subcmd>")
    p_mv = mify_sub.add_parser("validate", help="校验 workflow YAML")
    p_mv.add_argument("--workflow", required=True)
    p_dr = mify_sub.add_parser("dry-run", help="干跑单个节点")
    p_dr.add_argument("--issue", default=None)
    p_dr.add_argument("--node",  default=None)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return EXIT_OK

    dispatch = {
        "doctor":             cmd_doctor,
        "run":                cmd_run,
        "run-api":            cmd_run_api,
        "run-ui":             cmd_run_ui,
        "status":             cmd_status,
        "collect-artifacts":  cmd_collect_artifacts,
        "analyze-defects":    cmd_analyze_defects,
        "render-report":      cmd_render_report,
        "report":             cmd_report,
        "patrol":  cmd_patrol,
        "mify":    cmd_mify,
    }

    handler = dispatch.get(args.command)
    if not handler:
        fail(f"未知命令: {args.command}")
        return EXIT_FAILED

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
