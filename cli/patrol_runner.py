#!/usr/bin/env python3
"""
patrol_runner.py — Autopilot Patrol 执行器 (Track H)

读取 contracts/autopilot_patrol.yaml，生成 patrol issue，调用 test-squad run。
可由外部调度器（cron / Task Scheduler / Multica 定时触发）直接调用。

用法：
    python cli/patrol_runner.py --profile daily_smoke
    python cli/patrol_runner.py --profile daily_smoke --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml as _yaml
    def load_yaml(text: str):
        return _yaml.safe_load(text)
except ImportError:
    # 无 PyYAML 时简单解析 key: value（不支持嵌套列表，仅用于读顶层 workspace_id）
    def load_yaml(text: str):
        result = {}
        for line in text.splitlines():
            if ":" in line and not line.strip().startswith("#"):
                k, _, v = line.partition(":")
                result[k.strip()] = v.strip()
        return result

PATROL_CONFIG = Path("contracts/autopilot_patrol.yaml")
OUTPUTS_ROOT  = Path("outputs/runs")
CLI           = [sys.executable, str(Path(__file__).parent / "test_squad.py")]

MAX_RETRY_DEFAULT = 2
EXIT_OK      = 0
EXIT_BLOCKED = 1
EXIT_FAILED  = 2


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _log(level: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def load_patrol_config() -> dict:
    if not PATROL_CONFIG.exists():
        _log("ERROR", f"巡检配置不存在: {PATROL_CONFIG}")
        sys.exit(EXIT_FAILED)
    text = PATROL_CONFIG.read_text(encoding="utf-8")
    return load_yaml(text)


def find_profile(config: dict, profile_id: str) -> dict | None:
    patrols = config.get("patrols", [])
    if not isinstance(patrols, list):
        return None
    for p in patrols:
        if isinstance(p, dict) and p.get("id") == profile_id:
            return p
    return None


def run_cli(*args, dry_run: bool = False) -> int:
    cmd = CLI + list(args)
    _log("CMD", " ".join(cmd))
    if dry_run:
        _log("DRY-RUN", "跳过实际执行")
        return EXIT_OK
    result = subprocess.run(cmd, cwd=str(Path.cwd()))
    return result.returncode


def write_patrol_result(patrol_id: str, profile: dict, status: str, attempts: int, note: str = ""):
    run_dir = OUTPUTS_ROOT / patrol_id
    run_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "patrol_id":    patrol_id,
        "profile":      profile.get("id", "unknown"),
        "workspace":    profile.get("workspace_id", ""),
        "workflow":     profile.get("workflow", "super_test_agent_v1"),
        "started_at":   datetime.now().isoformat(),
        "status":       status,
        "attempts":     attempts,
        "note":         note,
    }
    result_path = run_dir / "patrol_run_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _log("INFO", f"巡检结果已写入: {result_path}")
    return result_path


def run_patrol(profile: dict, dry_run: bool = False) -> int:
    patrol_id = f"PATROL-{_ts()}"
    workflow  = profile.get("workflow", "super_test_agent_v1")
    retry_cfg = profile.get("retry", {}) if isinstance(profile.get("retry"), dict) else {}
    max_att   = retry_cfg.get("max_attempts", MAX_RETRY_DEFAULT)

    _log("INFO", f"=== Autopilot Patrol 开始 ===")
    _log("INFO", f"patrol_id : {patrol_id}")
    _log("INFO", f"profile   : {profile.get('id')}")
    _log("INFO", f"workflow  : {workflow}")
    _log("INFO", f"max_retry : {max_att}")

    # Step 1: doctor
    _log("INFO", "Step 1/4 — doctor")
    rc = run_cli("doctor", "--workspace", profile.get("workspace_id", ""), dry_run=dry_run)
    if rc != EXIT_OK and not dry_run:
        _log("ERROR", "doctor 未通过，终止巡检")
        write_patrol_result(patrol_id, profile, "blocked_by_doctor", 0,
                            "doctor 检查未通过，环境未就绪")
        return EXIT_BLOCKED

    # Step 2: run（带重试）
    for attempt in range(1, max_att + 2):
        _log("INFO", f"Step 2/4 — run (attempt {attempt}/{max_att + 1})")
        rc = run_cli("run",
                     "--issue",     patrol_id,
                     "--workflow",  workflow,
                     "--workspace", profile.get("workspace_id", ""),
                     dry_run=dry_run)
        if rc == EXIT_OK:
            break
        if attempt <= max_att:
            _log("WARN", f"run 失败（rc={rc}），将重试（{attempt}/{max_att}）...")
        else:
            _log("ERROR", f"run 达到最大重试次数（{max_att}），终止")
            write_patrol_result(patrol_id, profile, "failed", attempt,
                                f"run 重试 {max_att} 次后仍失败")
            return EXIT_FAILED

    # Step 3: report
    _log("INFO", "Step 3/4 — report")
    run_cli("report", "--issue", patrol_id, dry_run=dry_run)

    # Step 4: 写入 patrol 结果
    _log("INFO", "Step 4/4 — 写入巡检结果")
    result_path = write_patrol_result(patrol_id, profile, "passed", attempt)

    # 生成巡检报告 Markdown
    report_lines = [
        f"# 巡检报告 — {patrol_id}",
        f"",
        f"**Profile：** {profile.get('id')}  ",
        f"**Workspace：** {profile.get('workspace_id')}  ",
        f"**Workflow：** {workflow}  ",
        f"**时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**尝试次数：** {attempt}  ",
        f"**状态：** passed  ",
        f"",
        f"## 说明",
        f"",
        f"当前版本为 Contract 阶段巡检。",
        f"Track C/D 执行层接入后，本报告将包含真实 API 和 UI 执行结果。",
        f"",
        f"## 下一步",
        f"",
        f"1. 接入 Track C ApiExecutionTool（HTTP 执行）",
        f"2. 接入 Track D WebExecutionTool（Playwright）",
        f"3. 配置 cron 每日 09:30 自动触发本脚本",
    ]
    run_dir = OUTPUTS_ROOT / patrol_id
    patrol_report = run_dir / "patrol_report.md"
    patrol_report.write_text("\n".join(report_lines), encoding="utf-8")
    _log("INFO", f"巡检报告: {patrol_report}")

    _log("INFO", f"=== 巡检完成: {patrol_id} [OK] ===")
    return EXIT_OK


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="patrol_runner",
        description="Autopilot Patrol Runner — 超级测试 Agent 定时巡检执行器",
    )
    parser.add_argument("--profile",   default="daily_smoke", help="巡检 profile id")
    parser.add_argument("--workspace", default=None,          help="覆盖 workspace_id")
    parser.add_argument("--dry-run",   action="store_true",   help="只打印命令，不实际执行")
    args = parser.parse_args()

    config = load_patrol_config()
    profile = find_profile(config, args.profile)

    if not profile:
        _log("ERROR", f"未找到 profile: {args.profile}")
        _log("INFO",  f"可用 profiles: {[p.get('id') for p in config.get('patrols', []) if isinstance(p, dict)]}")
        return EXIT_FAILED

    if args.workspace:
        profile = dict(profile)
        profile["workspace_id"] = args.workspace

    return run_patrol(profile, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
