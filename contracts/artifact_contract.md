# Artifact Contract

workspace_id: target-system-test

每次 issue 执行，`artifact_index.json` 必须包含以下结构：

```json
{
  "multica_issue_id": "ISSUE-001",
  "workspace_id": "target-system-test",
  "run_id": "run-20260611-001",
  "status": "passed|failed|blocked",
  "target_system": "target-system",
  "artifacts": [
    {
      "type": "context_package",
      "path": "outputs/runs/ISSUE-001/context_package.json",
      "required": true
    },
    {
      "type": "test_cases",
      "path": "outputs/runs/ISSUE-001/test_cases.json",
      "required": true
    },
    {
      "type": "test_cases_md",
      "path": "outputs/runs/ISSUE-001/test_cases.md",
      "required": true
    },
    {
      "type": "api_cases",
      "path": "outputs/runs/ISSUE-001/api_cases.yaml",
      "required": false,
      "note": "API 功能用例（positive/negative/boundary/auth/idempotent/concurrent/rollback）"
    },
    {
      "type": "ui_flow",
      "path": "outputs/runs/ISSUE-001/ui_flow.yaml",
      "required": false,
      "note": "UI 分层用例（VAF execution_skill_web 格式）"
    },
    {
      "type": "e2e_cases",
      "path": "outputs/runs/ISSUE-001/e2e_cases.yaml",
      "required": false,
      "note": "E2E 端到端组合链用例（UI操作 + API验证，VAF T04.1 双维度）"
    },
    {
      "type": "perf_cases",
      "path": "outputs/runs/ISSUE-001/perf_cases.yaml",
      "required": false,
      "note": "性能探针用例（P0接口，repeat=5, concurrency=1，非压测）"
    },
    {
      "type": "execution_plan",
      "path": "outputs/runs/ISSUE-001/execution_plan.json",
      "required": true
    },
    {
      "type": "api_execution_result",
      "path": "outputs/runs/ISSUE-001/api_execution_result.json",
      "required": false
    },
    {
      "type": "ui_execution_result",
      "path": "outputs/runs/ISSUE-001/ui_execution_result.json",
      "required": false
    },
    {
      "type": "performance_result",
      "path": "outputs/runs/ISSUE-001/performance_result.json",
      "required": false
    },
    {
      "type": "defect_analysis",
      "path": "outputs/runs/ISSUE-001/defect_analysis.json",
      "required": true
    },
    {
      "type": "repair_suggestion",
      "path": "outputs/runs/ISSUE-001/repair_suggestion.md",
      "required": false
    },
    {
      "type": "report",
      "path": "outputs/runs/ISSUE-001/test_agent_report.md",
      "required": true
    },
    {
      "type": "multica_comment",
      "path": "outputs/runs/ISSUE-001/multica_comment_payload.json",
      "required": true
    }
  ]
}
```

## 验收规则

1. `required: true` 的产物缺失时，issue 状态设为 `blocked`，不得标记为 `passed`。
2. 所有 artifact path 必须是相对于 `outputs/runs/{issue_id}/` 的相对路径。
3. 截图统一放在 `outputs/runs/{issue_id}/screenshots/` 目录。
4. trace 文件统一命名为 `trace.zip`。
5. 任何产物不得包含真实密码或 token 明文。
