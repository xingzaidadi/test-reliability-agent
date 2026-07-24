#!/usr/bin/env python3
"""
源码扫描器 —— 自动扫 Java 源码,生成覆盖率分母 api_spec.json。
替代手工抓注解。扫描:
  - Controller 的 @X5RequestMapping/@RequestMapping/@PostMapping → 接口清单
  - 入参对象的 @NotBlank/@NotNull → 必填参数
  - @EnumRange(strValues=...) → 枚举值
这让"充分性反推"的分母是自动从源码来的,不是人肉填。

用法:
  python spec_scanner.py --src <java源码根目录> --out api_spec.json
"""

import argparse
import json
import re
from pathlib import Path


def scan_apis(src: Path) -> list:
    """扫 Controller 里的接口路径。"""
    apis = []
    for jf in src.rglob("*.java"):
        if "/target/" in str(jf).replace("\\", "/"):
            continue
        try:
            txt = jf.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "Controller" not in txt:
            continue
        # 类级 @RequestMapping("/x5/api")
        base = ""
        m = re.search(r'@RequestMapping\(\s*"([^"]+)"', txt)
        if m:
            base = m.group(1)
        # 方法级映射:X5RequestMapping(value="/pullPrice",...) 或 Post/GetMapping
        for mm in re.finditer(
            r'@(?:X5RequestMapping|PostMapping|GetMapping)\(\s*(?:value\s*=\s*)?"([^"]+)"', txt):
            path = mm.group(1)
            full = base.rstrip("/") + "/" + path.lstrip("/") if base else path
            if full not in apis:
                apis.append(full)
    return apis


def scan_params_enums(src: Path) -> tuple:
    """扫入参对象的必填字段和枚举。"""
    required, enums, error_msgs = [], {}, []
    for jf in src.rglob("*Req.java"):
        if "/target/" in str(jf).replace("\\", "/"):
            continue
        try:
            txt = jf.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        # @NotBlank/@NotNull → 字段名从紧随的 @HttpApiDocClassDefine(value="xxx") 或 private xxx 取
        for m in re.finditer(r'@(?:NotBlank|NotNull)\([^)]*\)', txt):
            after = txt[m.end():m.end()+220]
            fm = (re.search(r'@HttpApiDocClassDefine\(\s*value\s*=\s*"(\w+)"', after)
                  or re.search(r'private\s+\w+\s+(\w+)', after))
            if fm and fm.group(1) not in required:
                required.append(fm.group(1))
        # @EnumRange(strValues = {"A","B",...})
        for m in re.finditer(r'@EnumRange\(\s*strValues\s*=\s*\{([^}]+)\}', txt):
            vals = re.findall(r'"([^"]+)"', m.group(1))
            after = txt[m.end():m.end()+300]
            fm = (re.search(r'@HttpApiDocClassDefine\(\s*value\s*=\s*"(\w+)"', after)
                  or re.search(r'private\s+\w+\s+(\w+)', after))
            if fm and vals:
                enums[fm.group(1)] = vals
        # 校验消息(可推错误码场景)
        for m in re.finditer(r'message\s*=\s*"([^"]+)"', txt):
            error_msgs.append(m.group(1))
    return required, enums, error_msgs


def build_spec(src_path: str) -> dict:
    src = Path(src_path)
    if not src.exists():
        raise RuntimeError(f"源码路径不存在: {src_path}")
    apis = scan_apis(src)
    required, enums, msgs = scan_params_enums(src)
    # 错误码:校验失败通常400,鉴权401,常见业务码
    error_codes = [400, 401]
    return {
        "_generated_by": "spec_scanner.py(自动扫源码,非手工)",
        "_source": str(src),
        "apis": apis,
        "required_params": required,
        "enums": enums,
        "error_codes": error_codes,
        "_validation_messages": msgs[:20],   # 供参考
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="Java源码根目录")
    ap.add_argument("--out", default="api_spec.json")
    args = ap.parse_args()

    spec = build_spec(args.src)
    Path(args.out).write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[spec-scanner] 扫描完成:")
    print(f"  接口: {len(spec['apis'])} 个 → {spec['apis'][:5]}")
    print(f"  必填参数: {spec['required_params']}")
    print(f"  枚举字段: {list(spec['enums'].keys())}")
    print(f"  已写入: {args.out}")
