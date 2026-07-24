#!/usr/bin/env python3
"""
测试可靠性平台 — Web 入口后端(FastAPI)
把命令行 pipeline 包成 HTTP 接口,让平台从"敲命令"升级为"点鼠标"。
全本地,不出网。

接口:
  GET  /              → 返回单页界面
  POST /api/run       → 触发一次执行(后台跑 pipeline / 各能力)
  GET  /api/result    → 读某 issue 的结果卡片数据
  GET  /api/report    → 读 test_agent_report.md

启动:  python web/server.py   然后浏览器开 http://127.0.0.1:8000
"""

import json
import subprocess
import sys
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
app = FastAPI(title="测试可靠性平台")

# 简单的执行状态(单机 demo,内存即可)
_state = {"running": False, "issue": None, "log": [], "done": False}


def _run_pipeline(issue: str, caps: list):
    """后台线程跑 pipeline(真实调用,不伪造)。"""
    _state.update(running=True, issue=issue, log=[], done=False)
    try:
        # Web 默认跑"快链路"(执行→性能→充分性→归因→报告,秒级);
        # 需求驱动含多次 LLM 调用较慢,设为可选(caps 里带 'requirement' 才跑)
        cmd = [PY, "-u", "pipeline.py", "--issue", issue]
        if "requirement" not in (caps or []):
            cmd.append("--skip-requirement")
        import os
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                errors="replace", bufsize=1, env=env)
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                _state["log"].append(line)
        proc.wait()
    except Exception as e:
        _state["log"].append(f"[ERROR] {e}")
    finally:
        _state.update(running=False, done=True)


def _cards(issue: str) -> dict:
    """读产物,拼成结果卡片数据。缺的就标 N/A,不编。"""
    d = ROOT / "outputs/runs" / issue
    def _j(name):
        p = d / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    api = _j("api_execution_result.json").get("summary", {})
    suf = _j("sufficiency_report.json")
    dfa = _j("defect_analysis.json").get("summary", {})
    perf = _j("performance_result.json").get("cases", [{}])
    p0 = perf[0].get("stats", {}) if perf else {}
    bycat = dfa.get("by_category", {})
    return {
        "api": {"passed": api.get("passed"), "total": api.get("total")},
        "coverage": suf.get("final_coverage_pct"),
        "perf": {"p50": p0.get("p50_ms"), "p95": p0.get("p95_ms")},
        "defect_product": bycat.get("PRODUCT", 0) if bycat else None,
        "verdict": suf.get("final_verdict"),
    }


@app.post("/api/run")
def run(payload: dict):
    if _state["running"]:
        return JSONResponse({"error": "已有任务在跑"}, status_code=409)
    issue = payload.get("issue", "ISSUE-001")
    caps = payload.get("caps", [])
    threading.Thread(target=_run_pipeline, args=(issue, caps), daemon=True).start()
    return {"ok": True, "issue": issue}


@app.get("/api/status")
def status():
    return {"running": _state["running"], "done": _state["done"],
            "log": _state["log"], "issue": _state["issue"]}


@app.get("/api/result")
def result(issue: str = "ISSUE-001"):
    return _cards(issue)


@app.get("/api/report", response_class=PlainTextResponse)
def report(issue: str = "ISSUE-001"):
    p = ROOT / "outputs/runs" / issue / "test_agent_report.md"
    return p.read_text(encoding="utf-8") if p.exists() else "(报告未生成)"


@app.get("/", response_class=HTMLResponse)
def index():
    return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    import uvicorn
    print("测试可靠性平台 Web 入口: http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
