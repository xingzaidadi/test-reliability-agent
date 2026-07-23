#!/usr/bin/env python3
"""
测试充分性保障 — 闸① 覆盖率反推 + 闸② 维度检查清单
核心思想:把"用例够不够全"从AI/人的主观判断,变成机器可算的数字。
对标 VAF 原则3「机器可验证优于AI自述」。

- 闸②(维度清单):每个接口按固定测试维度扫,缺哪个维度标红。纯规则。
- 闸①(覆盖率反推):拿源码提取的"分母"(必填参数/枚举/错误码)算覆盖率。

用法:
  python coverage_analyzer.py --spec api_spec.json --cases api_cases.yaml
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml as _yaml
    def _load_yaml(p): return _yaml.safe_load(Path(p).read_text(encoding="utf-8"))
except ImportError:
    def _load_yaml(p): raise RuntimeError("需要 pyyaml")


# ── 闸②:测试维度清单(ISTQB + 接口测试通用维度)────────────────
# 每个接口"应该"覆盖的维度。缺哪个=用例设计有维度盲区。
DIMENSION_CHECKLIST = {
    "positive":   "正向:合法参数返回预期",
    "missing":    "参数缺失:必填字段缺失",
    "boundary":   "边界值:0/负数/超长/空串",
    "enum_invalid":"枚举非法:枚举字段传非法值",
    "auth":       "鉴权:签名/token缺失或错误",
    "not_found":  "数据不存在:查不到的编码",
    "type_error": "类型错误:字段类型不对",
}

# 维度识别关键词(从用例name/body/assertions里判断它测了哪个维度)
_DIM_KEYWORDS = {
    "positive":    ["正向", "正常", "成功", "positive", "合法"],
    "missing":     ["缺失", "缺", "为空", "missing", "必填", "空数组", "空列表"],
    "boundary":    ["边界", "boundary", "超长", "负数", "空串", "0", "最大"],
    "enum_invalid":["枚举", "非法", "enum", "不合法", "invalid"],
    "auth":        ["鉴权", "签名", "token", "auth", "未授权", "权限", "appkey"],
    "not_found":   ["不存在", "未找到", "not_found", "nonexist", "无效编码"],
    "type_error":  ["类型", "type", "格式"],
}


def detect_dimension(case: dict) -> set:
    """从一条用例判断它覆盖了哪些维度。"""
    text = json.dumps(case, ensure_ascii=False).lower()
    name = str(case.get("name", "")).lower()
    hit = set()
    for dim, kws in _DIM_KEYWORDS.items():
        if any(kw.lower() in text or kw.lower() in name for kw in kws):
            hit.add(dim)
    # 有断言status_code=200且无其他特征 → 至少算正向
    if not hit:
        hit.add("positive")
    return hit


def gate2_dimension_check(cases: list) -> dict:
    """闸②:维度覆盖检查。"""
    covered = set()
    for c in cases:
        covered |= detect_dimension(c)
    missing = [DIMENSION_CHECKLIST[d] for d in DIMENSION_CHECKLIST if d not in covered]
    return {
        "total_dimensions": len(DIMENSION_CHECKLIST),
        "covered_dimensions": sorted(covered),
        "missing_dimensions": [d for d in DIMENSION_CHECKLIST if d not in covered],
        "missing_desc": missing,
        "dimension_coverage_pct": round(len(covered) / len(DIMENSION_CHECKLIST) * 100, 1),
    }


def gate1_coverage(spec: dict, cases: list) -> dict:
    """闸①:覆盖率反推。拿源码分母算覆盖率。"""
    cases_text = json.dumps(cases, ensure_ascii=False)

    # 分母1:必填参数——每个必填参数是否都有"缺失"用例
    required = spec.get("required_params", [])
    req_covered, req_missing = [], []
    for p in required:
        # 该参数的缺失用例:某用例body里缺了这个字段(简化:看是否有针对它的缺失用例描述)
        if p in cases_text and any(
            kw in cases_text for kw in ["缺", "为空", "missing"]
        ):
            req_covered.append(p)
        else:
            req_missing.append(p)

    # 分母2:枚举值——枚举字段的合法值是否被覆盖 + 是否有非法值用例
    enums = spec.get("enums", {})
    enum_result = {}
    for field, values in enums.items():
        covered_vals = [v for v in values if v in cases_text]
        enum_result[field] = {
            "total_values": len(values),
            "covered_values": covered_vals,
            "covered_pct": round(len(covered_vals) / len(values) * 100, 1) if values else 0,
            "has_invalid_case": any(kw in cases_text for kw in ["非法", "不合法", "invalid"]),
        }

    # 分母3:错误码/状态码——期望的错误场景是否有用例
    error_codes = spec.get("error_codes", [])
    ec_covered = [ec for ec in error_codes if str(ec) in cases_text]
    ec_missing = [ec for ec in error_codes if str(ec) not in cases_text]

    # 分母4:接口——每个接口是否至少1条用例
    apis = spec.get("apis", [])
    api_covered = [a for a in apis if a in cases_text]
    api_missing = [a for a in apis if a not in cases_text]

    # 综合覆盖率(加权:接口40% 必填参数30% 枚举20% 错误码10%)
    api_pct = len(api_covered) / len(apis) if apis else 1
    req_pct = len(req_covered) / len(required) if required else 1
    enum_pct = (sum(e["covered_pct"] for e in enum_result.values()) / len(enum_result) / 100) if enum_result else 1
    ec_pct = len(ec_covered) / len(error_codes) if error_codes else 1
    overall = round((api_pct*0.4 + req_pct*0.3 + enum_pct*0.2 + ec_pct*0.1) * 100, 1)

    return {
        "overall_coverage_pct": overall,
        "api_coverage": {"covered": api_covered, "missing": api_missing},
        "required_param_coverage": {"covered": req_covered, "missing_missing_case": req_missing},
        "enum_coverage": enum_result,
        "error_code_coverage": {"covered": ec_covered, "missing": ec_missing},
    }


def analyze(spec_path: str, cases_path: str) -> dict:
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    cases_doc = _load_yaml(cases_path)
    cases = cases_doc.get("cases", cases_doc) if isinstance(cases_doc, dict) else cases_doc

    gate2 = gate2_dimension_check(cases)
    gate1 = gate1_coverage(spec, cases)

    # 汇总:充分性判定
    sufficient = (gate1["overall_coverage_pct"] >= 80 and
                  gate2["dimension_coverage_pct"] >= 70)

    report = {
        "case_count": len(cases),
        "gate1_coverage": gate1,
        "gate2_dimensions": gate2,
        "sufficiency_verdict": "充分" if sufficient else "不充分-需补",
        "gaps_summary": {
            "缺接口用例": gate1["api_coverage"]["missing"],
            "缺必填缺失用例": gate1["required_param_coverage"]["missing_missing_case"],
            "缺错误码用例": gate1["error_code_coverage"]["missing"],
            "缺测试维度": gate2["missing_desc"],
        },
    }
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    report = analyze(args.spec, args.cases)
    out = args.out or "coverage_report.json"
    Path(out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[充分性] 用例数: {report['case_count']}")
    print(f"[闸①覆盖率] {report['gate1_coverage']['overall_coverage_pct']}%")
    print(f"[闸②维度] {report['gate2_dimensions']['dimension_coverage_pct']}% "
          f"(缺: {report['gate2_dimensions']['missing_dimensions']})")
    print(f"[判定] {report['sufficiency_verdict']}")
    print(f"[缺口] {json.dumps(report['gaps_summary'], ensure_ascii=False)}")
    print(f"[报告] {out}")
