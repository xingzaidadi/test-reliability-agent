#!/usr/bin/env python3
"""
ApiExecutionTool — Track C
读取 api_cases.yaml，对 target-system 测试环境执行真实 HTTP 请求，输出 api_execution_result.json。
"""

import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# ── X5 协议签名封包 ────────────────────────────────────────────────────────────
# 小米 X5 网关协议:业务 body 需签名+信封封装+Base64+form 编码后发送。
# 算法对齐 Apifox 前置脚本:
#   sign = MD5(appid + raw + appkey).upper()
#   envelope = {header:{appid,sign,method}, body: raw}
#   最终 body = "data=" + urlencode(base64(json(envelope)))
#   Content-Type = application/x-www-form-urlencoded

def x5_wrap(raw_body: str, appid: str, appkey: str, method: str = "") -> str:
    sign = hashlib.md5((appid + raw_body + appkey).encode("utf-8")).hexdigest().upper()
    header = {"appid": appid, "sign": sign}
    if method:
        header["method"] = method
    envelope = {"header": header, "body": raw_body}
    envelope_json = json.dumps(envelope, ensure_ascii=False)
    b64 = base64.b64encode(envelope_json.encode("utf-8")).decode("ascii")
    return "data=" + urllib.parse.quote(b64, safe="")

try:
    import yaml as _yaml
    def _load_yaml(path: Path) -> dict:
        return _yaml.safe_load(path.read_text(encoding="utf-8"))
except ImportError:
    def _load_yaml(path: Path) -> dict:
        raise RuntimeError(
            "PyYAML 未安装。请运行: pip install pyyaml\n"
            "或: python -m pip install pyyaml"
        )

# ── 断言求值 ──────────────────────────────────────────────────────────────────

def _json_path_get(obj, path: str):
    """极简 JSONPath：支持 $.a.b.c 和 $.a[0].b。"""
    parts = re.split(r'[\.\[\]]+', path.lstrip("$").lstrip("."))
    cur = obj
    for p in parts:
        if not p:
            continue
        if isinstance(cur, list):
            try:
                cur = cur[int(p)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    return cur


def _eval_assertion(assertion: dict, resp_body: dict, status_code: int, duration_ms: float) -> tuple[bool, str]:
    t = assertion.get("type", "")

    if t == "status_code":
        expected = assertion.get("expected")
        if expected is not None:
            ok = status_code == expected
            return ok, f"status_code {status_code} {'==' if ok else '!='} {expected}"
        expected_in = assertion.get("expected_in", [])
        ok = status_code in expected_in
        return ok, f"status_code {status_code} {'in' if ok else 'not in'} {expected_in}"

    elif t == "json_path":
        path = assertion.get("path", "")
        val = _json_path_get(resp_body, path)
        expected = assertion.get("expected")
        condition = assertion.get("condition", "")

        if expected is not None:
            ok = str(val) == str(expected)
            return ok, f"json_path {path}={val!r} {'==' if ok else '!='} {expected!r}"

        if condition == "not_null":
            ok = val is not None
            return ok, f"json_path {path} is {'not null' if ok else 'null'}"

        if condition.startswith("length >"):
            n = int(condition.split(">")[1].strip())
            ok = isinstance(val, list) and len(val) > n
            return ok, f"json_path {path} length={len(val) if isinstance(val, list) else 'N/A'} > {n}: {ok}"

        return True, f"json_path {path}={val!r} (no condition checked)"

    elif t == "response_time_ms":
        max_ms = assertion.get("max", 5000)
        ok = duration_ms <= max_ms
        return ok, f"response_time {duration_ms:.0f}ms <= {max_ms}ms: {ok}"

    return True, f"unknown assertion type: {t} (skipped)"


# ── 单个用例执行 ──────────────────────────────────────────────────────────────

def _resolve_vars(obj, env_overrides: dict = None):
    """把 {{VAR_NAME}} 替换成环境变量值。"""
    overrides = env_overrides or {}
    def _replace(v):
        if isinstance(v, str):
            def sub(m):
                key = m.group(1)
                return overrides.get(key) or os.environ.get(key, m.group(0))
            return re.sub(r'\{\{(\w+)\}\}', sub, v)
        elif isinstance(v, dict):
            return {k: _replace(vv) for k, vv in v.items()}
        elif isinstance(v, list):
            return [_replace(i) for i in v]
        return v
    return _replace(obj)


def run_case(case: dict, base_url: str, token: str, env_overrides: dict = None) -> dict:
    case_id   = case.get("id", "UNKNOWN")
    name      = case.get("name", "")
    method    = case.get("method", "POST").upper()
    path      = case.get("path", "")
    headers   = dict(case.get("headers", {}))
    body      = case.get("body", {})
    assertions = case.get("assertions", [])
    priority  = case.get("priority", "P1")

    url = base_url.rstrip("/") + path

    # 注入 token
    if token:
        headers.setdefault("X-Token", token)
        headers.setdefault("Authorization", f"Bearer {token}")

    # 替换模板变量
    body = _resolve_vars(body, env_overrides)
    headers = _resolve_vars(headers, env_overrides)

    # X5 协议:headers 带 appid+appkey 时,业务 body 需签名封包后以 form 发送
    x5_appid  = headers.get("appid")
    x5_appkey = headers.get("appkey")
    if x5_appid and x5_appkey:
        raw_body = json.dumps(body, ensure_ascii=False) if body else ""
        x5_method = headers.get("method", "")
        payload = x5_wrap(raw_body, x5_appid, x5_appkey, x5_method).encode("utf-8")
        # X5 网关不需要 appkey 明文随请求头再发一次;保留 appid/method 供网关路由
        headers.pop("appkey", None)
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    else:
        payload = json.dumps(body).encode("utf-8") if body else b""
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=payload, headers=headers, method=method)

    start = time.monotonic()
    resp_status = None
    resp_body   = {}
    error_msg   = None

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_status   = resp.status
            raw           = resp.read().decode("utf-8", errors="replace")
            try:
                resp_body = json.loads(raw)
            except json.JSONDecodeError:
                resp_body = {"_raw": raw}
    except urllib.error.HTTPError as e:
        resp_status = e.code
        try:
            resp_body = json.loads(e.read().decode("utf-8", errors="replace"))
        except Exception:
            resp_body = {}
        error_msg = str(e)
    except Exception as e:
        resp_status = 0
        error_msg   = str(e)

    duration_ms = (time.monotonic() - start) * 1000

    # 求值断言
    assertion_results = []
    all_passed = True
    for a in assertions:
        passed, detail = _eval_assertion(a, resp_body, resp_status or 0, duration_ms)
        assertion_results.append({"assertion": a, "passed": passed, "detail": detail})
        if not passed:
            all_passed = False

    status = "passed" if (all_passed and error_msg is None) else "failed"

    return {
        "case_id":       case_id,
        "name":          name,
        "priority":      priority,
        "url":           url,
        "method":        method,
        "status":        status,
        "status_code":   resp_status,
        "duration_ms":   round(duration_ms, 1),
        "error":         error_msg,
        "assertions":    assertion_results,
        "response_body": resp_body,
        "request_body":  body,
    }


# ── 性能探针 ──────────────────────────────────────────────────────────────────
# 复用 run_case(含 X5 签名),对同一用例连发 N 次,统计 p50/p95/max/min。
# 只采样耗时,不做压测(不并发),对测试环境无压力。

def _percentile(sorted_vals: list, pct: float) -> float:
    """线性插值百分位。sorted_vals 已升序。pct 如 50 / 95。"""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = (pct / 100.0) * (len(sorted_vals) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = rank - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def run_perf_case(case: dict, base_url: str, token: str, n: int,
                  env_overrides: dict = None) -> dict:
    case_id = case.get("id", "UNKNOWN")
    name    = case.get("name", "")
    samples = []          # 每次耗时 ms
    status_codes = []     # 每次 HTTP 状态
    errors = 0

    for i in range(n):
        r = run_case(case, base_url, token, env_overrides)
        samples.append(r["duration_ms"])
        status_codes.append(r["status_code"])
        if r.get("error"):
            errors += 1

    ordered = sorted(samples)
    stats = {
        "samples":  n,
        "min_ms":   round(min(ordered), 1),
        "p50_ms":   round(_percentile(ordered, 50), 1),
        "p95_ms":   round(_percentile(ordered, 95), 1),
        "max_ms":   round(max(ordered), 1),
        "avg_ms":   round(sum(ordered) / len(ordered), 1),
        "errors":   errors,
        "status_codes": sorted(set(status_codes)),
    }
    return {
        "case_id": case_id,
        "name":    name,
        "stats":   stats,
        "durations_ms": samples,
    }


def run_perf(cases_yaml: Path, issue_id: str, run_dir: Path, n: int = 10,
             priority_filter: str | None = None,
             env_overrides: dict | None = None) -> dict:
    base_url = os.environ.get("TARGET_SYSTEM_BASE_URL", "").rstrip("/")
    token    = os.environ.get("TARGET_SYSTEM_TOKEN", "")
    if not base_url:
        raise RuntimeError("TARGET_SYSTEM_BASE_URL 未设置")

    spec = _load_yaml(cases_yaml)
    cases = spec.get("cases", [])
    if priority_filter:
        pf = priority_filter.upper()
        cases = [c for c in cases if c.get("priority", "").upper() == pf]

    print(f"[perf-probe] {len(cases)} 个用例 x {n} 次采样，base_url={base_url}")

    results = []
    for c in cases:
        cid = c.get("id", "?")
        print(f"  [PERF] {cid} {c.get('name', '')} x{n}", end=" ... ", flush=True)
        r = run_perf_case(c, base_url, token, n, env_overrides)
        s = r["stats"]
        print(f"p50={s['p50_ms']}ms p95={s['p95_ms']}ms max={s['max_ms']}ms err={s['errors']}")
        results.append(r)

    output = {
        "issue_id":    issue_id,
        "executed_at": datetime.now().isoformat(),
        "base_url":    base_url,
        "cases_file":  str(cases_yaml),
        "probe_type":  "response_time_sampling",
        "samples_per_case": n,
        "note":        "单请求串行采样,非并发压测;仅用于响应时间基线",
        "cases":       results,
    }
    out_path = run_dir / "performance_result.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[perf-probe] 结果已写入: {out_path}")
    return output


# ── 主执行函数 ────────────────────────────────────────────────────────────────

def run(cases_yaml: Path, issue_id: str, run_dir: Path,
        priority_filter: str | None = None,
        env_overrides: dict | None = None) -> dict:

    base_url = os.environ.get("TARGET_SYSTEM_BASE_URL", "").rstrip("/")
    token    = os.environ.get("TARGET_SYSTEM_TOKEN", "")

    if not base_url:
        raise RuntimeError("TARGET_SYSTEM_BASE_URL 未设置")

    spec = _load_yaml(cases_yaml)
    cases = spec.get("cases", [])

    # 优先级过滤
    if priority_filter:
        pf = priority_filter.upper()
        cases = [c for c in cases if c.get("priority", "").upper() == pf]

    print(f"[api-runner] {len(cases)} 个用例，base_url={base_url}")

    results = []
    for c in cases:
        cid = c.get("id", "?")
        print(f"  [RUN] {cid} {c.get('name', '')}", end=" ... ", flush=True)
        r = run_case(c, base_url, token, env_overrides)
        icon = "PASS" if r["status"] == "passed" else "FAIL"
        print(f"{icon} ({r['duration_ms']}ms)")
        results.append(r)

    total   = len(results)
    passed  = sum(1 for r in results if r["status"] == "passed")
    failed  = total - passed

    output = {
        "issue_id":    issue_id,
        "executed_at": datetime.now().isoformat(),
        "base_url":    base_url,
        "cases_file":  str(cases_yaml),
        "status":      "passed" if failed == 0 else "failed",
        "summary": {
            "total":   total,
            "passed":  passed,
            "failed":  failed,
            "skipped": 0,
        },
        "cases": results,
    }

    out_path = run_dir / "api_execution_result.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[api-runner] 结果已写入: {out_path}")
    print(f"[api-runner] 总计 {total}，通过 {passed}，失败 {failed}")
    return output


# ── CLI 入口 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="api_execution_tool",
                                     description="ApiExecutionTool — Track C")
    parser.add_argument("--issue",    required=True)
    parser.add_argument("--cases",    default=None)
    parser.add_argument("--priority", default=None, help="只跑指定优先级 P0/P1/P2")
    parser.add_argument("--run-dir",  default=None, dest="run_dir")
    parser.add_argument("--perf",     action="store_true", help="性能探针模式:同用例连发N次采样p50/p95")
    parser.add_argument("--samples",  type=int, default=10, help="性能模式每用例采样次数(默认10)")
    args = parser.parse_args()

    issue   = args.issue
    run_dir = Path(args.run_dir) if args.run_dir else Path("outputs/runs") / issue
    cases   = Path(args.cases)  if args.cases   else run_dir / "api_cases.yaml"

    if not cases.exists():
        # 回退到模板
        cases = Path(__file__).parent / "api_cases_template.yaml"
        print(f"[api-runner] 用例文件不存在，使用模板: {cases}")

    try:
        if args.perf:
            run_perf(cases, issue, run_dir, n=args.samples, priority_filter=args.priority)
            sys.exit(0)
        result = run(cases, issue, run_dir, priority_filter=args.priority)
        sys.exit(0 if result["status"] == "passed" else 1)
    except Exception as e:
        print(f"[api-runner] ERROR: {e}", file=sys.stderr)
        sys.exit(2)
