#!/usr/bin/env python3
"""
detect.py — Track I (ai-api-tester)
识别目标项目类型，输出 project_info.json。
支持 Maven/Gradle Java、Spring Boot、Node.js 等。
"""

import json
import sys
from pathlib import Path


_DETECTORS = [
    ("maven-java",    lambda r: (r / "pom.xml").exists()),
    ("gradle-java",   lambda r: (r / "build.gradle").exists() or (r / "build.gradle.kts").exists()),
    ("springboot",    lambda r: any((r / f).exists() for f in [
                          "src/main/resources/application.yml",
                          "src/main/resources/application.properties",
                      ])),
    ("nodejs",        lambda r: (r / "package.json").exists()),
    ("python-flask",  lambda r: (r / "app.py").exists() or (r / "wsgi.py").exists()),
    ("python-fastapi",lambda r: any(p.name == "main.py" for p in r.glob("*.py"))),
    ("openapi",       lambda r: any(r.glob("**/openapi*.yaml")) or any(r.glob("**/swagger*.yaml"))),
]


def detect(project_root: str) -> dict:
    root = Path(project_root).resolve()
    if not root.is_dir():
        return {"error": f"目录不存在: {root}", "detected": False}

    detected_types = []
    for type_name, checker in _DETECTORS:
        try:
            if checker(root):
                detected_types.append(type_name)
        except Exception:
            pass

    # OpenAPI/swagger 文件扫描
    openapi_files = list(root.glob("**/openapi*.yaml")) + \
                    list(root.glob("**/openapi*.json")) + \
                    list(root.glob("**/swagger*.yaml")) + \
                    list(root.glob("**/swagger*.json"))

    # 源码 API 文件扫描（Controller）
    controller_files = []
    for pattern in ["**/Controller.java", "**/*Controller.java",
                    "**/*Resource.java", "**/*Api.java"]:
        controller_files.extend(str(p) for p in root.glob(pattern))

    result = {
        "project_root":      str(root),
        "detected_types":    detected_types,
        "primary_type":      detected_types[0] if detected_types else "unknown",
        "openapi_files":     [str(p) for p in openapi_files],
        "controller_files":  controller_files[:20],
        "detected":          bool(detected_types),
        "has_openapi":       bool(openapi_files),
        "has_controllers":   bool(controller_files),
    }
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="detect", description="识别项目类型")
    parser.add_argument("project_root", nargs="?", default=".")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    info = detect(args.project_root)
    out = json.dumps(info, ensure_ascii=False, indent=2)
    print(out)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"[detect] 结果写入: {args.output}", file=sys.stderr)
