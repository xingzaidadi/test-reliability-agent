# Issue 生命周期定义

workspace_id: target-system-test

## 状态流转

```
created
  -> assigned
  -> context_loading
  -> case_generating
  -> waiting_human_confirmation
  -> executing
  -> analyzing
  -> reporting
  -> passed | failed | blocked
  -> archived
```

## 状态说明

| 状态 | 含义 |
|---|---|
| created | issue 已创建，等待 Agent 分配 |
| assigned | Squad Leader 已接单，准备启动 Mify workflow |
| context_loading | context_agent 正在读取源码/文档/接口信息 |
| case_generating | case_generation_agent 正在生成测试用例 |
| waiting_human_confirmation | 用例已生成，等待人工确认 P0 用例 |
| executing | API/UI/性能工具正在执行 |
| analyzing | defect_analysis_agent 正在分析失败原因 |
| reporting | report_agent 正在生成报告并回写 Multica |
| passed | 全部 P0 用例通过 |
| failed | 存在未修复的 P0 失败 |
| blocked | 环境/数据/鉴权问题导致无法执行 |
| archived | 已归档，不再更新 |

## 事件定义

| 事件 | 触发时机 |
|---|---|
| issue.created | issue 首次创建 |
| agent.assigned | Squad Leader 接单 |
| mify.workflow.started | Mify workflow 启动 |
| mify.node.completed | 任意 Mify 节点完成 |
| tool.started | API/UI/Perf tool 开始执行 |
| tool.completed | tool 执行完成 |
| artifact.collected | artifact_collector 收集产物 |
| analysis.completed | defect_analysis 完成 |
| report.generated | 报告生成完成 |
| issue.status.updated | issue 状态变更 |
| issue.comment.posted | 报告回写到 Multica comment |

## 事件 payload 格式

```json
{
  "event_id": "evt-001",
  "multica_issue_id": "ISSUE-001",
  "workspace_id": "target-system-test",
  "agent_id": "case_generation_agent",
  "event_type": "mify.node.completed",
  "status": "completed",
  "message": "case_generate completed",
  "artifact_refs": ["test_cases.json", "test_cases.md"],
  "created_at": "2026-06-11T10:00:00+08:00"
}
```

## 不可逆动作限制

以下动作触发前必须有 waiting_human_confirmation 状态，且 human_confirmation.json 中需有明确确认记录：

```
create（创建业务数据）
submit（提交单据）
approve（审批）
delete
release
publish
payment
settlement
```
