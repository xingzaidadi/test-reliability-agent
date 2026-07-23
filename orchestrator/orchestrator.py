#!/usr/bin/env python3
"""
Orchestrator(调度器=老板)+ Workspace(工作区隔离)— V1
把 Task 派给合适的 Worker,用 Skill 执行,产出隔离到 Workspace。

V1:串行执行。V2:依赖DAG、并发、Squad委派。
安全合规:全本地,不出网。
"""

import json
import time
from pathlib import Path

from core import Runtime, Worker, Task, TaskStatus
from skills import SkillRegistry, build_default_registry


class Workspace:
    """工作区隔离:每个项目一个,产物/配置独立。"""
    def __init__(self, workspace_id: str, root: str = "outputs/orchestrator"):
        self.id = workspace_id
        self.dir = Path(root) / workspace_id
        self.dir.mkdir(parents=True, exist_ok=True)

    def save_artifact(self, name: str, content: str) -> Path:
        p = self.dir / name
        p.write_text(content, encoding="utf-8")
        return p


class Orchestrator:
    def __init__(self, workspace: Workspace, registry: SkillRegistry = None):
        self.workspace = workspace
        self.registry = registry or build_default_registry()
        self.workers: dict = {}
        self.squads: dict = {}          # V2:小队
        self.tasks: list = []

    def register_worker(self, worker: Worker):
        if not worker.available():
            print(f"[orch] 警告:worker {worker.name}({worker.provider}) 本机不可用,跳过")
            return
        self.workers[worker.name] = worker
        print(f"[orch] 登记员工: {worker.name} (provider={worker.provider})")

    def register_squad(self, squad):
        """V2:登记小队。派活可指向 squad 名,由 leader 委派成员。"""
        self.squads[squad.name] = squad
        members = [m.name for m in squad.members]
        print(f"[orch] 登记小队: {squad.name} (成员={members})")

    def _pick_worker(self, task: Task) -> Worker:
        """选员工:①指派squad→leader委派 ②指派worker ③skill倾向provider ④任意可用。"""
        skill = self.registry.get(task.skill)
        # 1. 指派给 squad → 由 squad 委派成员(V2)
        if task.assigned_to and task.assigned_to in self.squads:
            return self.squads[task.assigned_to].delegate(task)
        # 2. task 明确指派 worker
        if task.assigned_to and task.assigned_to in self.workers:
            return self.workers[task.assigned_to]
        # 3. skill 倾向的 provider
        if skill.preferred_provider:
            for w in self.workers.values():
                if w.provider == skill.preferred_provider and w.can_do(task.skill):
                    return w
        # 4. 任意能做的
        for w in self.workers.values():
            if w.can_do(task.skill):
                return w
        raise RuntimeError(f"无可用员工执行 task {task.id}(skill={task.skill})")

    def submit(self, task: Task):
        task.status = TaskStatus.ENQUEUED
        self.tasks.append(task)

    def run(self, max_workers: int = 4) -> list:
        """V2:按 depends_on 做 DAG 拓扑执行。
        同一批(依赖已满足)的任务并发跑;前置产出注入后续 payload。"""
        from concurrent.futures import ThreadPoolExecutor

        task_map = {t.id: t for t in self.tasks}
        done_ids = set()
        pending = [t for t in self.tasks if t.status == TaskStatus.ENQUEUED]

        while pending:
            # 找出这一波:依赖全部 done 的任务
            ready = [t for t in pending
                     if all(dep in done_ids for dep in t.depends_on)]
            if not ready:
                # 有环或依赖缺失 → 剩余标 blocked,防死循环
                for t in pending:
                    t.status = TaskStatus.BLOCKED
                    t.error = f"依赖未满足或成环: depends_on={t.depends_on}"
                    print(f"[orch] 阻塞: {t.id} — {t.error}")
                break

            # 注入前置产出:①放进 payload['deps'] 供程序用
            #               ②把上游结论追加进每个文本payload字段,供prompt模板直接看到
            for t in ready:
                if t.depends_on:
                    t.payload = dict(t.payload)
                    deps = {dep: task_map[dep].result for dep in t.depends_on
                            if dep in task_map}
                    t.payload["deps"] = deps
                    dep_text = "\n".join(f"[{k}的结论]: {v.strip()}"
                                         for k, v in deps.items() if v)
                    # 把上游结论拼进所有字符串payload字段(让prompt模板无感知拿到上下文)
                    for key, val in list(t.payload.items()):
                        if isinstance(val, str) and key != "deps":
                            t.payload[key] = f"{val}\n\n【上游产出】\n{dep_text}"

            # 并发执行这一波
            print(f"[orch] 执行批次: {[t.id for t in ready]} (并发≤{max_workers})")
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                ex.map(self._run_one, ready)

            for t in ready:
                if t.status == TaskStatus.DONE:
                    done_ids.add(t.id)
                pending.remove(t)

        return self.tasks

    def _run_one(self, task: Task):
        skill = self.registry.get(task.skill)
        try:
            worker = self._pick_worker(task)
            task.assigned_to = worker.name
            task.status = TaskStatus.CLAIMED
            print(f"[orch] 派活: {task.id}({task.skill}) → {worker.name}")

            task.status = TaskStatus.RUNNING
            task.started_at = time.monotonic()

            if skill.kind == "tool" and skill.tool_fn:
                # 工具类:直接调函数(如现有test_squad工具)
                out = skill.tool_fn(task.payload)
            else:
                # LLM类:渲染prompt → 派给worker执行
                prompt = task.prompt or skill.build_prompt(task.payload)
                out = worker.run(prompt)

            if skill.post_process:
                out = skill.post_process(out)

            task.result = out
            task.ended_at = time.monotonic()
            task.status = TaskStatus.DONE

            # 产出落地到 workspace(隔离)
            art = self.workspace.save_artifact(f"{task.id}_{task.skill}.out", out)
            task.artifacts.append(str(art))
            print(f"[orch] 完成: {task.id} ({task.duration_ms()}ms) → {art.name}")

        except Exception as e:
            task.ended_at = time.monotonic()
            task.status = TaskStatus.FAILED
            task.error = str(e)
            print(f"[orch] 失败: {task.id} — {e}")

    def summary(self) -> dict:
        done = sum(1 for t in self.tasks if t.status == TaskStatus.DONE)
        failed = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
        return {
            "workspace": self.workspace.id,
            "total": len(self.tasks),
            "done": done,
            "failed": failed,
            "workers": list(self.workers.keys()),
            "tasks": [
                {"id": t.id, "skill": t.skill, "worker": t.assigned_to,
                 "status": t.status.value, "duration_ms": t.duration_ms()}
                for t in self.tasks
            ],
        }
