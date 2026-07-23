#!/usr/bin/env python3
"""
locate.py — Track I (ai-api-tester)
在项目源码中定位 API 端点，提取路径/方法/参数信息。
支持 Java @RequestMapping / @GetMapping / @PostMapping，以及 OpenAPI yaml/json。
"""

import json
import re
import sys
from pathlib import Path


_MAPPING_RE = re.compile(
    r'@(RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)'
    r'\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
    re.MULTILINE,
)
_METHOD_NAME_RE = re.compile(r'public\s+\S+\s+(\w+)\s*\(')
_CLASS_MAPPING_RE = re.compile(
    r'@RequestMapping\s*\(\s*["\']([^"\']+)["\']',
)


def _locate_java(src_dir: Path) -> list:
    endpoints = []
    for java_file in src_dir.rglob("*.java"):
        text = java_file.read_text(encoding="utf-8", errors="replace")
        # 类级别 prefix
        class_prefix = ""
        class_match = _CLASS_MAPPING_RE.search(text)
        if class_match:
            class_prefix = class_match.group(1).rstrip("/")

        for match in _MAPPING_RE.finditer(text):
            annotation = match.group(1)
            path = match.group(2)

            # 推断 HTTP 方法
            if annotation == "GetMapping":
                method = "GET"
            elif annotation == "PostMapping":
                method = "POST"
            elif annotation == "PutMapping":
                method = "PUT"
            elif annotation == "DeleteMapping":
                method = "DELETE"
            elif annotation == "PatchMapping":
                method = "PATCH"
            else:
                method = "GET"  # RequestMapping 默认 GET

            full_path = (class_prefix + "/" + path.lstrip("/")).replace("//", "/")

            # 尝试找方法名（注解后最近的 public 方法）
            pos = match.end()
            snippet = text[pos:pos + 300]
            m_name = _METHOD_NAME_RE.search(snippet)
            method_name = m_name.group(1) if m_name else "unknown"

            endpoints.append({
                "path":        full_path,
                "http_method": method,
                "method_name": method_name,
                "source_file": str(java_file),
                "line":        text[:match.start()].count("\n") + 1,
            })
    return endpoints


def _locate_openapi(openapi_file: Path) -> list:
    try:
        import yaml
        spec = yaml.safe_load(openapi_file.read_text(encoding="utf-8"))
    except Exception:
        return []

    endpoints = []
    base_path = spec.get("basePath", "") or ""
    paths = spec.get("paths", {})
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for http_method, operation in methods.items():
            if http_method.startswith("x-") or not isinstance(operation, dict):
                continue
            endpoints.append({
                "path":        base_path + path,
                "http_method": http_method.upper(),
                "operation_id": operation.get("operationId", ""),
                "summary":     operation.get("summary", ""),
                "tags":        operation.get("tags", []),
                "source_file": str(openapi_file),
            })
    return endpoints


def locate(project_root: str) -> dict:
    root = Path(project_root).resolve()
    endpoints = []

    # OpenAPI first
    for pattern in ["**/openapi*.yaml", "**/openapi*.json",
                    "**/swagger*.yaml", "**/swagger*.json"]:
        for f in root.glob(pattern):
            endpoints.extend(_locate_openapi(f))

    # Java controllers
    src_dirs = [root / "src/main/java", root]
    for src_dir in src_dirs:
        if src_dir.is_dir():
            endpoints.extend(_locate_java(src_dir))

    # 去重
    seen = set()
    unique = []
    for e in endpoints:
        key = (e["path"], e["http_method"])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return {
        "project_root": str(root),
        "total":        len(unique),
        "endpoints":    unique,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="locate", description="定位 API 端点")
    parser.add_argument("project_root", nargs="?", default=".")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    result = locate(args.project_root)
    out = json.dumps(result, ensure_ascii=False, indent=2)
    print(out)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"[locate] 端点列表写入: {args.output}", file=sys.stderr)
