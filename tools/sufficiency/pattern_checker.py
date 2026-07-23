#!/usr/bin/env python3
"""
闸④ 历史缺陷比对 — 检查用例集是否覆盖了"已知会坑"的缺陷模式。
用例没覆盖高危模式 = 高风险漏测。

用法:
  python pattern_checker.py --patterns defect_patterns.yaml --cases api_cases.yaml
"""

import argparse
import json
from pathlib import Path

try:
    import yaml as _yaml
    def _load_yaml(p): return _yaml.safe_load(Path(p).read_text(encoding="utf-8"))
except ImportError:
    def _load_yaml(p): raise RuntimeError("需要 pyyaml")


def check(patterns_path: str, cases_path: str) -> dict:
    patterns = _load_yaml(patterns_path)["patterns"]
    cases_doc = _load_yaml(cases_path)
    cases = cases_doc.get("cases", cases_doc) if isinstance(cases_doc, dict) else cases_doc
    cases_text = json.dumps(cases, ensure_ascii=False).lower()

    covered, uncovered = [], []
    for p in patterns:
        # 模式被覆盖:关键词有足够命中(≥2个,或含专属词)
        hits = [kw for kw in p["check_keywords"] if kw.lower() in cases_text]
        is_covered = len(hits) >= 2
        entry = {"id": p["id"], "name": p["name"], "severity": p["severity"],
                 "source": p["source"], "hits": hits}
        (covered if is_covered else uncovered).append(entry)

    high_uncovered = [u for u in uncovered if u["severity"] == "high"]
    return {
        "total_patterns": len(patterns),
        "covered": covered,
        "uncovered": uncovered,
        "high_severity_uncovered": high_uncovered,
        "pattern_coverage_pct": round(len(covered) / len(patterns) * 100, 1),
        "risk": "高风险漏测" if high_uncovered else ("有遗漏" if uncovered else "已覆盖已知坑"),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--patterns", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    r = check(args.patterns, args.cases)
    out = args.out or "pattern_report.json"
    Path(out).write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[闸④缺陷模式] 覆盖 {r['pattern_coverage_pct']}% ({len(r['covered'])}/{r['total_patterns']})")
    print(f"[风险] {r['risk']}")
    if r["high_severity_uncovered"]:
        print("[高危未覆盖]:")
        for u in r["high_severity_uncovered"]:
            print(f"  - {u['id']} {u['name']} ({u['source']})")
    print(f"[报告] {out}")
