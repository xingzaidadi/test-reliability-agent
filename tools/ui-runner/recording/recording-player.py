#!/usr/bin/env python3
"""
recording-player.py — Track J (recording pack)
把 Playwright codegen 录制的 JavaScript 脚本转换为 ui_flow.yaml。
支持最常见的 page.goto / page.click / page.fill / page.selectOption 等调用。

使用：
    python recording-player.py recording.js --output ui_flow.yaml
"""

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("错误：缺少 pyyaml，请执行 pip install pyyaml", file=sys.stderr)
    sys.exit(1)


_GOTO_RE     = re.compile(r"page\.goto\(['\"]([^'\"]+)['\"]")
_CLICK_RE    = re.compile(r"page\.(?:locator|getByText|getByRole)\(['\"]([^'\"]+)['\"]\)\.click\(")
_FILL_RE     = re.compile(r"page\.(?:locator|getByLabel)\(['\"]([^'\"]+)['\"]\)\.fill\(['\"]([^'\"]*)['\"]")
_SELECT_RE   = re.compile(r"page\.(?:locator)\(['\"]([^'\"]+)['\"]\)\.selectOption\(['\"]([^'\"]*)['\"]")
_WAIT_RE     = re.compile(r"page\.waitForTimeout\((\d+)\)")
_SS_RE       = re.compile(r"page\.screenshot\(\{[^}]*path:['\"]([^'\"]*)['\"]")


def _parse_recording(js_text: str) -> list:
    steps = []
    counter = 1

    for line in js_text.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue

        m = _GOTO_RE.search(line)
        if m:
            steps.append({
                "step_id": f"S{counter:02d}",
                "name":    f"导航到 {m.group(1)[:50]}",
                "action":  "navigate",
                "url":     m.group(1),
            })
            counter += 1
            continue

        m = _FILL_RE.search(line)
        if m:
            steps.append({
                "step_id":  f"S{counter:02d}",
                "name":     f"填写 {m.group(1)[:30]}",
                "action":   "type",
                "selector": m.group(1),
                "value":    m.group(2),
            })
            counter += 1
            continue

        m = _SELECT_RE.search(line)
        if m:
            steps.append({
                "step_id":  f"S{counter:02d}",
                "name":     f"选择 {m.group(1)[:30]}",
                "action":   "select",
                "selector": m.group(1),
                "value":    m.group(2),
            })
            counter += 1
            continue

        m = _CLICK_RE.search(line)
        if m:
            steps.append({
                "step_id":  f"S{counter:02d}",
                "name":     f"点击 {m.group(1)[:30]}",
                "action":   "click",
                "selector": m.group(1),
            })
            counter += 1
            continue

        m = _WAIT_RE.search(line)
        if m:
            steps.append({
                "step_id": f"S{counter:02d}",
                "name":    f"等待 {m.group(1)}ms",
                "action":  "wait",
                "timeout": int(m.group(1)),
            })
            counter += 1
            continue

        m = _SS_RE.search(line)
        if m:
            steps.append({
                "step_id":    f"S{counter:02d}",
                "name":       "截图",
                "action":     "screenshot",
                "screenshot": Path(m.group(1)).name,
            })
            counter += 1
            continue

    return steps


def convert(recording_js: str, flow_name: str = "converted_flow") -> dict:
    text = Path(recording_js).read_text(encoding="utf-8", errors="replace")
    steps = _parse_recording(text)
    return {
        "name":    flow_name,
        "adapter": "generic-web",
        "profile": "readonly",
        "headless": True,
        "steps":   steps,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="recording-player",
                                     description="Playwright 录制脚本 -> ui_flow.yaml")
    parser.add_argument("recording_js")
    parser.add_argument("--name",   default="converted_flow")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    flow = convert(args.recording_js, args.name)
    out  = yaml.dump(flow, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(out)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"[recording-player] 写入: {args.output}", file=sys.stderr)
