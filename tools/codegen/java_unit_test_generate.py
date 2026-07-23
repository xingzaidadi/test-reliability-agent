#!/usr/bin/env python3
"""
JavaUnitTestGenerator — 后端单测生成节点
读取目标 Java 方法源码 + 依赖上下文,调用本机 LLM CLI(codex exec / claude -p)
生成 JUnit5 + Mockito 单测。这是"真AI生成",不是模板套壳。

用法:
  python java_unit_test_generate.py --spec test_spec.json --out OutputTest.java
  python java_unit_test_generate.py --spec test_spec.json --out OutputTest.java --engine claude

test_spec.json 结构:
{
  "target_class": "ApiX5Controller",
  "target_method": "getHeadCodeEnumByRespCode",
  "package": "com.example.demo.client.x5.controller",
  "framework": "JUnit5 + Mockito",
  "method_source": "<方法源码>",
  "context": "<依赖枚举/类型说明>",
  "requirements": ["测全成功→SUCCESS", "测全失败→FAIL", "测部分→PART_SUCCESS", "测空列表边界"]
}
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_cli(name: str) -> str:
    """Windows 下 npm CLI 是 .cmd 包装,需解析完整路径。"""
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"找不到 {name} CLI,请确认已安装并在 PATH 中")
    return path


def build_prompt(spec: dict) -> str:
    reqs = "\n".join(f"  - {r}" for r in spec.get("requirements", []))
    return f"""你是资深Java测试工程师。请为下面的方法生成一个完整、可编译、可运行的单元测试类。

## 目标
- 类:{spec['target_class']}
- 方法:{spec['target_method']}
- 包:{spec['package']}
- 测试框架:{spec['framework']}

## 方法源码
```java
{spec['method_source']}
```

## 依赖上下文
{spec['context']}

## 测试要求(每条必须有对应的@Test + 真实断言)
{reqs}

## 硬性规则
1. 只输出Java代码,不要解释、不要markdown代码块标记(```)。
2. 测试类名 = {spec['target_class']}Test,放在同一个包。
3. 每个@Test方法名清晰表达测什么(如 testAllSuccess_returnsSUCCESS)。
4. 断言必须是真实的(assertEquals(HeadCodeEnum.SUCCESS, result)),不许写占位符。
5. 构造入参用真实对象:new PullPriceX5Resp().setCode(0) 表示成功,setCode(其他值)表示失败。
6. 如果方法无外部依赖,不要引入无用的@Mock。
7. 覆盖边界:空列表、单元素、多元素混合。
"""


def call_codex(prompt: str) -> str:
    """调用 codex exec 非交互生成。
    --skip-git-repo-check: 允许在非git信任目录运行。
    prompt 走 stdin,避免超长命令行参数被截断/转义问题。"""
    r = subprocess.run(
        [_resolve_cli("codex"), "exec", "--skip-git-repo-check", "-"],
        input=prompt, capture_output=True, text=True, timeout=300, encoding="utf-8")
    if not r.stdout and r.stderr:
        print(f"[unit-test-gen] codex stderr: {r.stderr[:300]}", file=sys.stderr)
    return r.stdout


def call_claude(prompt: str) -> str:
    """调用 claude -p 非交互生成(需已登录)。"""
    r = subprocess.run([_resolve_cli("claude"), "-p", prompt],
                       capture_output=True, text=True, timeout=300, encoding="utf-8")
    return r.stdout


def extract_java(raw: str) -> str:
    """从LLM输出里抽出Java代码(去掉可能的markdown围栏和说明)。"""
    text = raw
    # 去 markdown 围栏
    if "```" in text:
        parts = text.split("```")
        # 取最长的、含 'class' 的代码块
        candidates = [p for p in parts if "class" in p and ("@Test" in p or "void" in p)]
        if candidates:
            text = max(candidates, key=len)
            # 去掉开头可能的 "java\n"
            if text.lstrip().startswith("java"):
                text = text.lstrip()[4:]
    # 从 package/import 开始截取
    lines = text.splitlines()
    start = 0
    for i, ln in enumerate(lines):
        if ln.strip().startswith(("package ", "import ")):
            start = i
            break
    return "\n".join(lines[start:]).strip() + "\n"


def main():
    ap = argparse.ArgumentParser(prog="java_unit_test_generate")
    ap.add_argument("--spec", required=True, help="test_spec.json 路径")
    ap.add_argument("--out",  required=True, help="输出 Java 测试文件路径")
    ap.add_argument("--engine", default="codex", choices=["codex", "claude"],
                    help="LLM引擎(默认codex/GPT-5.5;claude需先登录)")
    ap.add_argument("--raw-out", default=None, help="保存LLM原始输出(调试用)")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    prompt = build_prompt(spec)

    print(f"[unit-test-gen] 引擎={args.engine} 目标={spec['target_class']}.{spec['target_method']}")
    print(f"[unit-test-gen] 调用LLM生成中...")

    raw = call_codex(prompt) if args.engine == "codex" else call_claude(prompt)

    if args.raw_out:
        Path(args.raw_out).write_text(raw, encoding="utf-8")

    java_code = extract_java(raw)
    Path(args.out).write_text(java_code, encoding="utf-8")
    print(f"[unit-test-gen] 已生成: {args.out} ({len(java_code.splitlines())} 行)")


if __name__ == "__main__":
    main()
