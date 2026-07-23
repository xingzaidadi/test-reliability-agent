#!/usr/bin/env python3
"""
闸③ 对抗补全 — 拿闸①②算出的"缺口清单"驱动LLM补全用例。
关键:不是让AI"再想想",而是拿机器算出的确切缺口(缺哪个接口/错误码/维度)去补。
补全后再跑一遍覆盖率,验证真的补上了(闭环)。

多agent思路:codex补全 → 覆盖率复算(机器审查,比LLM互审更可靠)。

用法:
  python gap_filler.py --report coverage_report.json --spec api_spec.json --out gap_cases.yaml
"""

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def _codex(prompt: str, timeout: int = 300) -> str:
    cli = shutil.which("codex")
    r = subprocess.run([cli, "exec", "--skip-git-repo-check", "-"],
                       input=prompt, capture_output=True, text=True,
                       timeout=timeout, encoding="utf-8")
    raw = r.stdout or ""
    # 提取 codex 回复正文
    lines = raw.splitlines()
    start = max((i+1 for i, l in enumerate(lines) if l.strip() == "codex"), default=0)
    end = next((i for i in range(len(lines)-1, -1, -1)
                if lines[i].strip().startswith("tokens used")), len(lines))
    body = "\n".join(lines[start:end]).strip()
    # 去 markdown 围栏
    if "```" in body:
        parts = [p for p in body.split("```") if "id:" in p or "name" in p]
        if parts:
            body = max(parts, key=len)
            if body.lstrip().startswith(("yaml", "yml")):
                body = body.lstrip()[4:]
    return body.strip()


def build_gap_prompt(report: dict, spec: dict) -> str:
    gaps = report["gaps_summary"]
    return (
        "你是接口测试专家。下面是覆盖率分析发现的**确切缺口**,请**只补生成缺口对应的用例**。\n"
        "已有用例不用重复。只输出YAML格式的用例列表(cases下的条目),不要解释。\n\n"
        f"缺的接口用例: {gaps['缺接口用例']}\n"
        f"缺的错误码用例(需构造触发这些码的场景): {gaps['缺错误码用例']}\n"
        f"缺的测试维度: {gaps['缺测试维度']}\n\n"
        f"接口分母信息:\n"
        f"- 必填参数: {spec['required_params']}\n"
        f"- priceType枚举: {spec['enums'].get('priceType')}\n"
        f"- 接口: {spec['apis']}\n\n"
        "每条用例含: id/name/priority/method/path/headers(appid/appkey/method)/body/assertions。\n"
        "path用 /x5/api/xxx。body是List格式(getPrice收裸数组)。\n"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))

    print(f"[补全] 依据缺口清单驱动codex补全...")
    print(f"[补全] 缺口: {json.dumps(report['gaps_summary'], ensure_ascii=False)}")

    prompt = build_gap_prompt(report, spec)
    gap_cases = _codex(prompt)

    Path(args.out).write_text(gap_cases, encoding="utf-8")
    print(f"[补全] 补充用例已生成: {args.out} ({len(gap_cases.splitlines())}行)")


if __name__ == "__main__":
    main()
