#!/usr/bin/env python3
"""
Autopilot(定时/触发)— V2
借鉴 multica:cron/webhook/manual 触发 → 自动生成 Task 派发。
复用现有 patrol 概念(patrol_schedule_setup.ps1 是 cron 落地基础)。

V2 实现:
  - manual 触发:立即生成任务(真跑通)
  - cron 定义:记录 cron 表达式,给外部调度器(patrol/系统计划任务)调用
  - webhook:留接口占位
安全合规:纯本地,触发只是"生成Task并submit",不连外部。
"""

from dataclasses import dataclass, field
from typing import Callable, List

from core import Task


@dataclass
class Autopilot:
    name: str
    trigger: str = "manual"            # manual | cron | webhook
    cron: str = ""                     # cron类:如 "0 2 * * *"(交给外部调度器)
    # 任务工厂:每次触发生成一批 Task
    task_factory: Callable[[], List[Task]] = None
    description: str = ""

    def fire(self, orchestrator) -> List[Task]:
        """触发一次:生成任务并提交给编排器。返回生成的任务。"""
        if not self.task_factory:
            raise RuntimeError(f"autopilot {self.name} 没有 task_factory")
        tasks = self.task_factory()
        for t in tasks:
            orchestrator.submit(t)
        print(f"[autopilot] {self.name}({self.trigger}) 触发 → 生成 {len(tasks)} 个任务")
        return tasks

    def cron_hint(self) -> str:
        """给外部调度器(patrol/Windows计划任务)的提示。V2不内置常驻调度进程。"""
        if self.trigger == "cron" and self.cron:
            return (f"# 交给系统计划任务/patrol 执行:\n"
                    f"# cron: {self.cron}\n"
                    f"# 命令: python orchestrator/run_autopilot.py --name {self.name}")
        return ""


class AutopilotRegistry:
    def __init__(self):
        self._aps: dict = {}

    def register(self, ap: Autopilot):
        self._aps[ap.name] = ap
        print(f"[autopilot] 登记: {ap.name} (trigger={ap.trigger}"
              + (f", cron={ap.cron}" if ap.cron else "") + ")")

    def get(self, name: str) -> Autopilot:
        return self._aps[name]

    def list(self) -> list:
        return list(self._aps.keys())
