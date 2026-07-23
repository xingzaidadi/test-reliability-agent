#!/usr/bin/env python3
"""
测试充分性保障流水线 — 四闸串联
把"用例够不够全"从主观判断变成可度量的闭环:
  闸②维度检查 → 闸①覆盖率反推 → 闸③对抗补全 → 复算覆盖率 → 闸④缺陷模式比对
产出一份"充分性报告",含真实数字。

对标 VAF 原则3(机器可验证)+ 原则7(失败分类)在"测试设计质量"上的落地。

用法:
  python sufficiency_pipeline.py --spec api_spec.json --cases api_cases.yaml \
      --patterns defect_patterns.yaml --gap-cases gap_cases.yaml --out sufficiency_report.json
"""

import argparse
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from coverage_analyzer import analyze as coverage_analyze
from pattern_checker import check as pattern_check

try:
    import yaml as _yaml
    def _load_yaml(p): return _yaml.safe_load(Path(p).read_text(encoding="utf-8"))
    def _dump_yaml(d): return _yaml.safe_dump(d, allow_unicode=True)
except ImportError:
    def _load_yaml(p): raise RuntimeError("需要 pyyaml")


def _cases_of(path):
    doc = _load_yaml(path)
    return doc.get("cases", doc) if isinstance(doc, dict) else doc


def run(spec_path, cases_path, patterns_path, gap_cases_path=None, out=None):
    steps = []

    # ── 闸①② 初测 ──
    cov_before = coverage_analyze(spec_path, cases_path)
    steps.append({
        "step": "初测(闸①覆盖率+闸②维度)",
        "coverage_pct": cov_before["gate1_coverage"]["overall_coverage_pct"],
        "dimension_pct": cov_before["gate2_dimensions"]["dimension_coverage_pct"],
        "verdict": cov_before["sufficiency_verdict"],
        "gaps": cov_before["gaps_summary"],
    })

    # ── 闸③ 对抗补全:合并gap用例后复算 ──
    cov_after = cov_before
    merged_path = cases_path
    if gap_cases_path and Path(gap_cases_path).exists():
        base = _cases_of(cases_path)
        try:
            gap = _cases_of(gap_cases_path) or []
        except Exception:
            gap = []
        if gap:
            merged = {"cases": base + gap}
            merged_path = str(Path(cases_path).parent / "cases_after_fill.yaml")
            Path(merged_path).write_text(_dump_yaml(merged), encoding="utf-8")
            cov_after = coverage_analyze(spec_path, merged_path)
            steps.append({
                "step": "闸③对抗补全后复算",
                "added_cases": len(gap),
                "coverage_pct": cov_after["gate1_coverage"]["overall_coverage_pct"],
                "dimension_pct": cov_after["gate2_dimensions"]["dimension_coverage_pct"],
                "verdict": cov_after["sufficiency_verdict"],
                "gaps": cov_after["gaps_summary"],
            })

    # ── 闸④ 缺陷模式比对(用补全后的用例集)──
    pat = pattern_check(patterns_path, merged_path)
    steps.append({
        "step": "闸④缺陷模式比对",
        "pattern_coverage_pct": pat["pattern_coverage_pct"],
        "risk": pat["risk"],
        "high_uncovered": [u["name"] for u in pat["high_severity_uncovered"]],
    })

    report = {
        "pipeline": "测试充分性四闸流水线",
        "final_coverage_pct": cov_after["gate1_coverage"]["overall_coverage_pct"],
        "final_dimension_pct": cov_after["gate2_dimensions"]["dimension_coverage_pct"],
        "final_pattern_pct": pat["pattern_coverage_pct"],
        "final_verdict": cov_after["sufficiency_verdict"],
        "final_risk": pat["risk"],
        "steps": steps,
        "improvement": {
            "coverage": f"{cov_before['gate1_coverage']['overall_coverage_pct']}% → "
                        f"{cov_after['gate1_coverage']['overall_coverage_pct']}%",
        },
    }
    out = out or "sufficiency_report.json"
    Path(out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 55)
    print(" 测试充分性四闸流水线")
    print("=" * 55)
    for s in steps:
        print(f"\n[{s['step']}]")
        for k, v in s.items():
            if k != "step":
                print(f"   {k}: {json.dumps(v, ensure_ascii=False) if isinstance(v,(dict,list)) else v}")
    print(f"\n最终: 覆盖率{report['final_coverage_pct']}% | 维度{report['final_dimension_pct']}% | "
          f"缺陷模式{report['final_pattern_pct']}% | {report['final_verdict']} | {report['final_risk']}")
    print(f"覆盖率提升: {report['improvement']['coverage']}")
    print(f"报告: {out}")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--patterns", required=True)
    ap.add_argument("--gap-cases", default=None, dest="gap_cases")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    run(args.spec, args.cases, args.patterns, args.gap_cases, args.out)
