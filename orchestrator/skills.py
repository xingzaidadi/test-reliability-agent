#!/usr/bin/env python3
"""
Skill(技能)机制 — V1
借鉴 multica 的 "compound skills":能力皆 skill,加功能=加 skill,不改核心。
同事维护:写一个 Skill 定义注册进 registry 即可。

两类 skill:
  - LLM类:派给 worker 执行 prompt(如生成用例/单测/归因)
  - 工具类:调现有 test_squad 工具(如执行API/性能),不走LLM

Skill 定义可来自:
  - 代码内联(本文件的 register)
  - 现有 mify/prompts/*.md(prompt来源)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


@dataclass
class Skill:
    name: str
    description: str
    kind: str = "llm"                       # llm | tool
    prompt_template: str = ""               # LLM类:{{var}} 占位
    prompt_file: str = ""                   # 或从文件读(复用mify/prompts)
    preferred_provider: str = ""            # 倾向哪个员工(空=任意)
    post_process: Optional[Callable] = None # 可选:对产出做后处理
    tool_fn: Optional[Callable] = None      # tool类:直接调的函数

    def build_prompt(self, payload: dict) -> str:
        """渲染 prompt:优先 template,其次 prompt_file。"""
        tmpl = self.prompt_template
        if not tmpl and self.prompt_file:
            p = Path(self.prompt_file)
            if p.exists():
                tmpl = p.read_text(encoding="utf-8")
        # 极简 {{var}} 替换
        for k, v in (payload or {}).items():
            tmpl = tmpl.replace("{{" + k + "}}", str(v))
        return tmpl


class SkillRegistry:
    """技能注册表。加技能 = register 一个 Skill。"""
    def __init__(self):
        self._skills: dict = {}

    def register(self, skill: Skill):
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        if name not in self._skills:
            raise RuntimeError(f"未注册的skill: {name}(可用: {list(self._skills)})")
        return self._skills[name]

    def list(self) -> list:
        return list(self._skills.keys())


# ── 内置技能(V1 三个 LLM 技能,证明 skill 化可行)──────────────
# 同事加新能力:照这个样子 register 一个 Skill,不碰核心代码。

def build_default_registry() -> SkillRegistry:
    reg = SkillRegistry()

    reg.register(Skill(
        name="gen_api_case",
        description="读接口信息,生成结构化API测试用例(YAML)",
        kind="llm",
        preferred_provider="codex",
        prompt_template=(
            "你是接口测试专家。根据下面的接口信息,生成3-5条API测试用例。\n"
            "要求:覆盖正向/参数缺失/边界;每条含 name/priority/method/path/body/assertions。\n"
            "只输出YAML,不要解释。\n\n接口信息:\n{{api_info}}\n"
        ),
    ))

    reg.register(Skill(
        name="gen_unit_test",
        description="读Java方法源码,生成JUnit5单测",
        kind="llm",
        preferred_provider="codex",
        prompt_template=(
            "你是Java测试工程师。为下面的方法生成JUnit5单测,只输出Java代码不要解释。\n"
            "覆盖正常/边界/异常分支,断言必须真实。\n\n方法:\n{{method_source}}\n\n上下文:\n{{context}}\n"
        ),
    ))

    reg.register(Skill(
        name="analyze_defect",
        description="对失败用例做根因分析,给出分类和建议",
        kind="llm",
        preferred_provider="codex",
        prompt_template=(
            "你是资深测试。分析下面的失败信息,判断根因类别"
            "(ENV/DATA/CASE/PRODUCT/TOOL之一),给一句证据和一句修复建议。\n"
            "只输出:类别|证据|建议\n\n失败信息:\n{{failure_info}}\n"
        ),
    ))

    return reg
