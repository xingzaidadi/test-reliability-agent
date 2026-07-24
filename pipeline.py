#!/usr/bin/env python3
"""
一键全自动流水线总控 —— 把测试可靠性平台的全链路串成一条命令。

链路:  需求驱动(可测性分析→设计) → 用例执行 → 充分性四闸 → 缺陷归因 → 报告
每一段复用已有模块,总控只负责编排、传递、汇总、容错。

用法:
  python pipeline.py --issue ISSUE-001
  python pipeline.py --issue ISSUE-001 --skip-requirement   # 跳过需求段(用已有用例)
  python pipeline.py --issue ISSUE-001 --dry               # 干跑,不连真实环境

设计原则(对齐平台信条):
  - 结果不伪造:某段失败如实标记,不粉饰;继续跑能跑的,最后汇总"哪些成功/哪些失败"
  - 机器可验证:每段产出落盘,最终一张总表
"""

import argparse
import subprocess
import sys
import json
import time
from pathlib import Path

PY = sys.executable
ROOT = Path(__file__).parent


def step(name, cmd, cwd=ROOT, timeout=600):
    """跑一段,返回 (ok, 耗时ms)。不抛异常——失败也继续,最后汇总。"""
    print(f"\n{'='*56}\n▶ {name}\n{'='*56}")
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, cwd=str(cwd), timeout=timeout)
        ok = (r.returncode == 0)
    except subprocess.TimeoutExpired:
        print(f"  [超时] {name} 超过 {timeout}s")
        ok = False
    except Exception as e:
        print(f"  [异常] {name}: {e}")
        ok = False
    ms = round((time.monotonic() - t0) * 1000)
    print(f"  {'✓ 成功' if ok else '✗ 失败/跳过'}  ({ms}ms)")
    return ok, ms


def main():
    ap = argparse.ArgumentParser(prog="pipeline")
    ap.add_argument("--issue", default="ISSUE-001")
    ap.add_argument("--skip-requirement", action="store_true", help="跳过需求驱动段")
    ap.add_argument("--samples", type=int, default=15, help="性能采样次数")
    args = ap.parse_args()

    issue = args.issue
    run_dir = ROOT / "outputs/runs" / issue
    results = []

    print(f"\n╔{'═'*54}╗")
    print(f"║  测试可靠性平台 — 一键全自动流水线")
    print(f"║  issue: {issue}")
    print(f"╚{'═'*54}╝")

    # ① 需求驱动(可测性分析→测试设计)
    if not args.skip_requirement and (ROOT/"orchestrator/demo_requirement.py").exists():
        ok, ms = step("① 需求驱动:可测性分析 → 测试设计",
                      [PY, "orchestrator/demo_requirement.py"], timeout=400)
        results.append(("需求驱动", ok, ms))

    # ② 用例执行(真发HTTP,含签名)
    # 注意:退出码非0可能只是"有用例FAIL"(如故意的缺陷检测用例),不代表"没执行"。
    # 判据改为:结果文件里真跑出了执行数据(total>0)= 这段成功。
    _, ms = step("② 用例执行:真发HTTP(含X5签名)",
                 [PY, "cli/test_squad.py", "run-api", "--issue", issue])
    api_res = run_dir/"api_execution_result.json"
    executed = False
    if api_res.exists():
        try:
            s = json.loads(api_res.read_text(encoding="utf-8")).get("summary", {})
            executed = s.get("total", 0) > 0 and s.get("status") != "blocked"
        except Exception:
            pass
    print(f"  {'✓ 真执行(含预期FAIL不影响)' if executed else '✗ 未执行'}")
    results.append(("用例执行", executed, ms))

    # ③ 性能探针
    ok, ms = step("③ 性能探针:p50/p95 采样",
                  [PY, "tools/api-runner/api_execution_tool.py",
                   "--issue", issue, "--perf", "--samples", str(args.samples), "--priority", "P0"])
    results.append(("性能探针", ok, ms))

    # ④ 充分性四闸
    spec = run_dir/"api_spec.json"; cases = run_dir/"api_cases.yaml"
    patterns = ROOT/"tools/sufficiency/defect_patterns.yaml"
    gap = run_dir/"gap_cases.yaml"
    if spec.exists() and cases.exists():
        cmd = [PY, "tools/sufficiency/sufficiency_pipeline.py",
               "--spec", str(spec), "--cases", str(cases), "--patterns", str(patterns)]
        if gap.exists():
            cmd += ["--gap-cases", str(gap)]
        ok, ms = step("④ 充分性四闸:覆盖率反推+缺口", cmd)
        results.append(("充分性四闸", ok, ms))

    # ⑤ 缺陷归因
    ok, ms = step("⑤ 缺陷归因:6类根因",
                  [PY, "cli/test_squad.py", "analyze-defects", "--issue", issue])
    results.append(("缺陷归因", ok, ms))

    # ⑥ 报告
    ok, ms = step("⑥ 报告:MD/HTML + 回写payload",
                  [PY, "cli/test_squad.py", "report", "--issue", issue])
    results.append(("报告生成", ok, ms))

    # ── 总汇总(不伪造:如实列成功/失败)──
    print(f"\n╔{'═'*54}╗\n║  流水线总汇总\n╚{'═'*54}╝")
    okc = sum(1 for _, o, _ in results if o)
    for name, o, ms in results:
        print(f"  {'✓' if o else '✗'} {name:<12} {ms:>6}ms")
    print(f"\n  {okc}/{len(results)} 段成功")
    print(f"  产物目录: {run_dir}")

    summary = {
        "issue": issue,
        "stages": [{"name": n, "ok": o, "ms": ms} for n, o, ms in results],
        "success": okc, "total": len(results),
    }
    (run_dir/"pipeline_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if okc == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
