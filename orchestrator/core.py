#!/usr/bin/env python3
"""
多Agent测试编排器 — 核心抽象(V1)
借鉴 multica:Worker(员工)/ Task(任务)/ Runtime(运行时)。
安全合规:纯本地,只调本机 codex/claude CLI,不连任何外部平台,不出网。

架构分层(见 编排器_完整设计蓝图_V2.md):
  Workspace > Squad > Worker > Runtime ; Task ; Skill ; Autopilot
V1 真做:Worker/Task/Runtime-local/Skill/Workspace
V1 留口:Squad/Runtime-remote/Autopilot(接口占位,V2 实现)
"""

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


def _extract_codex_reply(raw: str) -> str:
    """从 codex exec 输出里提取模型真实回复。
    codex 输出结构:日志头 → 'codex' 行 → 真实回复 → 'tokens used' 行。
    取最后一个 'codex' 标记之后、'tokens used' 之前的内容。"""
    if not raw:
        return ""
    lines = raw.splitlines()
    # 找最后一个单独的 'codex' 标记行(回复正文的起点)
    start = -1
    for i, ln in enumerate(lines):
        if ln.strip() == "codex":
            start = i + 1
    # 找 'tokens used'(回复正文的终点)
    end = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith("tokens used"):
            end = i
            break
    if start >= 0 and start <= end:
        return "\n".join(lines[start:end]).strip()
    # 兜底:提取失败就返回原始(总比空好)
    return raw.strip()


# ── Runtime(运行时)──────────────────────────────────────────────
# V1 只实现 local(subprocess 调本机 CLI)。type 留 remote 扩展口。

class Runtime:
    def __init__(self, runtime_id: str, rtype: str = "local"):
        self.id = runtime_id
        self.type = rtype              # local | remote(V2)

    def detect_clis(self) -> dict:
        """检测本机有哪些 agent CLI 可用。"""
        clis = {}
        for name in ("codex", "claude"):
            path = shutil.which(name)
            clis[name] = path or ""
        return clis

    def execute(self, provider: str, prompt: str, timeout: int = 300) -> str:
        """在本 runtime 上执行一个 provider CLI,返回其 stdout。"""
        if self.type != "local":
            raise NotImplementedError("remote runtime 是 V2 能力(接口已留)")

        cli = shutil.which(provider)
        if not cli:
            raise RuntimeError(f"本机找不到 {provider} CLI")

        # codex:prompt 走 stdin(避免超长参数被截断),--skip-git-repo-check 允许非git目录
        # claude:-p 非交互
        if provider == "codex":
            r = subprocess.run([cli, "exec", "--skip-git-repo-check", "-"],
                               input=prompt, capture_output=True, text=True,
                               timeout=timeout, encoding="utf-8")
            return _extract_codex_reply(r.stdout or "")
        elif provider == "claude":
            r = subprocess.run([cli, "-p", prompt],
                               capture_output=True, text=True,
                               timeout=timeout, encoding="utf-8")
            return r.stdout or ""
        else:
            raise RuntimeError(f"未知 provider: {provider}")


# ── Task(任务)──────────────────────────────────────────────────
# 生命周期借鉴 multica:enqueued → claimed → running → done/failed/blocked

class TaskStatus(str, Enum):
    ENQUEUED = "enqueued"
    CLAIMED  = "claimed"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"
    BLOCKED  = "blocked"


@dataclass
class Task:
    id: str
    type: str                          # 任务类型(对应一个 skill)
    prompt: str = ""                   # 直接prompt(或由skill生成)
    payload: dict = field(default_factory=dict)
    skill: str = ""                    # 用哪个 skill 执行
    assigned_to: str = ""              # worker 名(V2:可为 squad)
    status: TaskStatus = TaskStatus.ENQUEUED
    result: str = ""
    error: str = ""
    artifacts: list = field(default_factory=list)
    depends_on: list = field(default_factory=list)   # V2:任务依赖DAG
    started_at: float = 0.0
    ended_at: float = 0.0

    def duration_ms(self) -> float:
        if self.started_at and self.ended_at:
            return round((self.ended_at - self.started_at) * 1000, 1)
        return 0.0


# ── Worker(员工)────────────────────────────────────────────────
# 绑定 provider(codex/claude)+ runtime。统一 run 接口。

class Worker:
    def __init__(self, name: str, provider: str, runtime: Runtime,
                 skills: Optional[list] = None):
        self.name = name
        self.provider = provider       # codex | claude
        self.runtime = runtime
        self.skills = skills or []      # 该员工会哪些技能(空=通用)

    def available(self) -> bool:
        return bool(self.runtime.detect_clis().get(self.provider))

    def can_do(self, skill_name: str) -> bool:
        return (not self.skills) or (skill_name in self.skills)

    def run(self, prompt: str, timeout: int = 300) -> str:
        return self.runtime.execute(self.provider, prompt, timeout)


# ── Squad(小队)── V2 实现,V1 留接口占位 ──────────────────────

class Squad:
    """员工分组+leader委派。V1 占位:squad 即单 worker 直通。V2 实现真实委派。"""
    def __init__(self, name: str, members: list, leader: Optional[Worker] = None):
        self.name = name
        self.members = members
        self.leader = leader or (members[0] if members else None)

    def delegate(self, task: Task) -> Worker:
        # V2:leader 按能力/负载分配。V1:返回第一个能做该skill的成员。
        for w in self.members:
            if w.available() and w.can_do(task.skill):
                return w
        raise RuntimeError(f"squad {self.name} 无可用成员执行 {task.skill}")
