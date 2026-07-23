"""
Materialize the Java recovery engine templates from references/recovery-engine-code.md.

Usage:
    python scripts/materialize_recovery_engine.py \
        --source references/recovery-engine-code.md \
        --output fixtures/recovery-engine-compile/target/generated-sources/recovery-engine \
        --package com.example.recovery

The script extracts the Java code blocks under numbered sections such as
"## 3. ActionExecutor.java", replaces {{PACKAGE}}, and writes .java files
under the package directory.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


HEADING_RE = re.compile(r"^##\s+\d+\.\s+(.+\.java)\s*$")
FENCE_RE = re.compile(r"^```(\w+)?\s*$")


def extract_java_templates(markdown: str) -> dict[str, str]:
    templates: dict[str, str] = {}
    current_file: str | None = None
    in_java_block = False
    buffer: list[str] = []

    for line in markdown.splitlines():
        heading_match = HEADING_RE.match(line)
        if heading_match and not in_java_block:
            current_file = heading_match.group(1).strip()
            buffer = []
            continue

        fence_match = FENCE_RE.match(line)
        if fence_match:
            lang = (fence_match.group(1) or "").lower()
            if current_file and not in_java_block and lang == "java":
                in_java_block = True
                buffer = []
                continue
            if in_java_block:
                templates[current_file or ""] = "\n".join(buffer).rstrip() + "\n"
                current_file = None
                in_java_block = False
                buffer = []
                continue

        if in_java_block:
            buffer.append(line)

    return {name: code for name, code in templates.items() if name}


def package_to_dir(package_name: str) -> Path:
    return Path(*package_name.split("."))


def materialize(source: Path, output: Path, package_name: str, clean: bool = True) -> list[Path]:
    markdown = source.read_text(encoding="utf-8")
    templates = extract_java_templates(markdown)
    if not templates:
        raise RuntimeError(f"No Java templates found in {source}")

    if clean and output.exists():
        shutil.rmtree(output)

    base_dir = output / package_to_dir(package_name)
    written: list[Path] = []

    for relative_name, code in sorted(templates.items()):
        target = base_dir / relative_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code.replace("{{PACKAGE}}", package_name), encoding="utf-8")
        written.append(target)

    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="references/recovery-engine-code.md")
    parser.add_argument("--output", default="fixtures/recovery-engine-compile/target/generated-sources/recovery-engine")
    parser.add_argument("--package", default="com.example.recovery", dest="package_name")
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args()

    written = materialize(
        source=Path(args.source),
        output=Path(args.output),
        package_name=args.package_name,
        clean=not args.no_clean,
    )
    print(f"materialized {len(written)} Java files")
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
