#!/usr/bin/env python3
"""
WebExecutionTool — Track D
读取 ui_flow.yaml，使用 Playwright 驱动 PurchaseQuery 页面执行只读查询流程。
输出 ui_execution_result.json + screenshots/ + trace.zip。

依赖：pip install playwright && playwright install chromium
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import yaml as _yaml
    def _load_yaml(path: Path) -> dict:
        return _yaml.safe_load(path.read_text(encoding="utf-8"))
except ImportError:
    def _load_yaml(path: Path) -> dict:
        raise RuntimeError("PyYAML 未安装：pip install pyyaml")

# ── 变量替换 ──────────────────────────────────────────────────────────────────

def _resolve(obj, env: dict):
    if isinstance(obj, str):
        return re.sub(r'\{\{(\w+)\}\}',
                      lambda m: env.get(m.group(1)) or os.environ.get(m.group(1), m.group(0)),
                      obj)
    elif isinstance(obj, dict):
        return {k: _resolve(v, env) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve(i, env) for i in obj]
    return obj

# ── 单步执行 ──────────────────────────────────────────────────────────────────

def _run_step(page, step: dict, screenshots_dir: Path, env: dict) -> dict:
    step_id  = step.get("id", "?")
    name     = step.get("name", "")
    action   = step.get("action", "")
    timeout  = step.get("timeout_ms", 15000)
    ss       = step.get("screenshot", False)

    step_r = {
        "step_id":    step_id,
        "name":       name,
        "action":     action,
        "status":     "passed",
        "error":      None,
        "screenshot": None,
        "assertions": [],
    }

    try:
        selector = _resolve(step.get("selector", ""), env)
        url      = _resolve(step.get("url", ""), env)

        # ── 动作执行 ──
        if action == "navigate":
            page.goto(url, wait_until=step.get("wait", "domcontentloaded"), timeout=timeout)

        elif action == "wait_for_selector":
            state = step.get("state", "visible")
            try:
                page.wait_for_selector(selector, state=state, timeout=timeout)
            except Exception:
                pass  # loading spinner 可能不出现，容错

        elif action == "assert_visible":
            page.wait_for_selector(selector, state="visible", timeout=timeout)

        elif action == "click":
            # 安全检查：readonly profile 禁止提交/审批/删除类按钮
            danger_texts = ["提交", "审批", "删除", "确认提交", "发布", "支付"]
            button_text = page.locator(selector).first.inner_text() if selector else ""
            for d in danger_texts:
                if d in button_text:
                    step_r["status"] = "skipped"
                    step_r["error"]  = f"readonly profile: 跳过危险操作 '{d}'"
                    return step_r
            page.locator(selector).first.click(timeout=timeout)
            wait_ms = step.get("wait_after_ms", 0)
            if wait_ms:
                page.wait_for_timeout(wait_ms)

        elif action in ("assert", "assert_text"):
            pass  # 断言在下面统一处理

        # ── 截图 ──
        if ss:
            ss_path = screenshots_dir / f"{step_id}.png"
            page.screenshot(path=str(ss_path), full_page=False)
            step_r["screenshot"] = str(ss_path)

        # ── 断言求值 ──
        for a in step.get("assertions", []):
            a_type     = a.get("type", "")
            a_passed   = True
            a_detail   = ""

            if a_type == "url_contains":
                val      = a.get("value", "")
                current  = page.url
                a_passed = val in current
                a_detail = f"url '{current}' contains '{val}': {a_passed}"

            elif a_type == "visible":
                expected = a.get("expected", True)
                try:
                    sel = step.get("selector", "")
                    is_visible = page.locator(sel).first.is_visible()
                    a_passed   = is_visible == expected
                    a_detail   = f"visible={is_visible} expected={expected}"
                except Exception as e:
                    a_passed = False
                    a_detail = str(e)

            elif a_type == "element_count":
                sel       = a.get("selector", step.get("selector", ""))
                condition = a.get("condition", ">= 1")
                count     = page.locator(sel).count()
                m = re.match(r'([><=!]+)\s*(\d+)', condition)
                if m:
                    op, n = m.group(1), int(m.group(2))
                    mapping = {">=": count >= n, ">": count > n, "==": count == n, "<=": count <= n}
                    a_passed = mapping.get(op, False)
                    a_detail = f"count={count} {op} {n}: {a_passed}"
                on_fail = a.get("on_fail", "")
                if not a_passed and on_fail:
                    a_detail += f" — {on_fail}"

            elif a_type == "not_contain_text":
                sel   = a.get("selector", "")
                val   = a.get("value", "")
                text  = page.locator(sel).first.inner_text() if sel else ""
                a_passed = val not in text
                a_detail = f"text not contains '{val}': {a_passed}"

            step_r["assertions"].append({"type": a_type, "passed": a_passed, "detail": a_detail})
            if not a_passed:
                step_r["status"] = "failed"

    except Exception as e:
        step_r["status"] = "failed"
        step_r["error"]  = str(e)
        # 失败截图
        try:
            ss_fail = screenshots_dir / f"{step_id}_fail.png"
            page.screenshot(path=str(ss_fail))
            step_r["screenshot"] = str(ss_fail)
        except Exception:
            pass

    return step_r


# ── 主执行函数 ────────────────────────────────────────────────────────────────

def run(flow_yaml: Path, issue_id: str, run_dir: Path,
        profile: str = "readonly",
        headless: bool = True,
        storage_state: Path | None = None) -> dict:

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        raise RuntimeError(
            "Playwright 未安装。请运行:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )

    flow = _load_yaml(flow_yaml)

    env = {
        "TARGET_SYSTEM_UI_URL":        os.environ.get("TARGET_SYSTEM_UI_URL", ""),
        "TARGET_SYSTEM_TEST_USER":     os.environ.get("TARGET_SYSTEM_TEST_USER", ""),
        "TARGET_SYSTEM_TEST_PASSWORD": os.environ.get("TARGET_SYSTEM_TEST_PASSWORD", ""),
        "multica_issue_id":               issue_id,
    }

    screenshots_dir = run_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    trace_path = run_dir / "trace.zip"

    steps   = flow.get("steps", [])
    results = []

    print(f"[ui-runner] {len(steps)} 步，profile={profile}, headless={headless}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        ctx_kwargs = {"viewport": {"width": 1440, "height": 900}}
        if storage_state and storage_state.exists():
            ctx_kwargs["storage_state"] = str(storage_state)

        context = browser.new_context(**ctx_kwargs)
        context.tracing.start(screenshots=True, snapshots=True)
        page = context.new_page()

        # SSO 登录处理：如果目标页面跳到登录页则尝试填账号密码
        ui_url = env.get("TARGET_SYSTEM_UI_URL", "")
        if ui_url:
            page.goto(ui_url, wait_until="domcontentloaded", timeout=30000)
            # 等待页面稳定
            page.wait_for_timeout(2000)
            current = page.url
            # 检测登录页（包含 login / sso / oauth）
            if any(x in current.lower() for x in ["login", "sso", "oauth", "cas"]):
                print(f"[ui-runner] 检测到登录页，尝试自动登录...")
                username = env.get("TARGET_SYSTEM_TEST_USER", "")
                password = env.get("TARGET_SYSTEM_TEST_PASSWORD", "")
                try:
                    page.fill("input[type='text'], input[name='username'], #username", username, timeout=5000)
                    page.fill("input[type='password'], input[name='password'], #password", password, timeout=5000)
                    page.click("button[type='submit'], input[type='submit'], button:has-text('登录')", timeout=5000)
                    page.wait_for_url(f"**{re.escape(ui_url.split('/')[2])}**", timeout=30000)
                    print(f"[ui-runner] 登录完成，当前页面: {page.url}")
                    # 保存 storage state 供下次复用
                    ss_save = run_dir / "storage_state.json"
                    context.storage_state(path=str(ss_save))
                    print(f"[ui-runner] session 已保存: {ss_save}")
                except Exception as e:
                    print(f"[ui-runner] 自动登录失败: {e}（可能需要手动登录或配置 storage_state）")

        for step in steps:
            sid = step.get("id", "?")
            print(f"  [STEP] {sid} {step.get('name', '')}", end=" ... ", flush=True)
            r = _run_step(page, _resolve(step, env), screenshots_dir, env)
            icon = "PASS" if r["status"] == "passed" else ("SKIP" if r["status"] == "skipped" else "FAIL")
            print(icon)
            results.append(r)
            # 失败时停止后续步骤
            if r["status"] == "failed":
                print(f"[ui-runner] 步骤 {sid} 失败，中止后续步骤")
                break

        context.tracing.stop(path=str(trace_path))
        browser.close()

    total_steps  = len(results)
    passed_steps = sum(1 for r in results if r["status"] == "passed")
    failed_steps = sum(1 for r in results if r["status"] == "failed")
    skipped_steps= sum(1 for r in results if r["status"] == "skipped")

    output = {
        "issue_id":    issue_id,
        "executed_at": datetime.now().isoformat(),
        "ui_url":      env.get("TARGET_SYSTEM_UI_URL", ""),
        "flow_file":   str(flow_yaml),
        "profile":     profile,
        "status":      "passed" if failed_steps == 0 else "failed",
        "summary": {
            "total_steps":   total_steps,
            "passed_steps":  passed_steps,
            "failed_steps":  failed_steps,
            "skipped_steps": skipped_steps,
        },
        "trace":       str(trace_path) if trace_path.exists() else None,
        "steps":       results,
    }

    out_path = run_dir / "ui_execution_result.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ui-runner] 结果已写入: {out_path}")
    print(f"[ui-runner] 步骤: {total_steps} 总 / {passed_steps} 通过 / {failed_steps} 失败 / {skipped_steps} 跳过")
    return output


# ── CLI 入口 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="ui_execution_tool",
                                     description="WebExecutionTool — Track D")
    parser.add_argument("--issue",         required=True)
    parser.add_argument("--flow",          default=None)
    parser.add_argument("--profile",       default="readonly")
    parser.add_argument("--run-dir",       default=None, dest="run_dir")
    parser.add_argument("--no-headless",   action="store_true", dest="no_headless")
    parser.add_argument("--storage-state", default=None, dest="storage_state")
    args = parser.parse_args()

    issue   = args.issue
    run_dir = Path(args.run_dir)      if args.run_dir      else Path("outputs/runs") / issue
    flow    = Path(args.flow)         if args.flow         else run_dir / "ui_flow.yaml"
    ss_path = Path(args.storage_state) if args.storage_state else None

    if not flow.exists():
        flow = Path(__file__).parent / "ui_flow_template.yaml"
        print(f"[ui-runner] flow 文件不存在，使用模板: {flow}")

    try:
        result = run(flow, issue, run_dir,
                     profile=args.profile,
                     headless=not args.no_headless,
                     storage_state=ss_path)
        sys.exit(0 if result["status"] == "passed" else 1)
    except Exception as e:
        print(f"[ui-runner] ERROR: {e}", file=sys.stderr)
        sys.exit(2)
