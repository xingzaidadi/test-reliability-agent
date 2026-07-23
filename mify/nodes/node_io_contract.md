# Mify 节点 IO Contract

workflow_id: super_test_agent_v1
workspace_id: "{{multica_workspace_id}}"

每个节点的输入输出必须符合本文档。上游节点未完成前，下游节点不得启动。
适用范围：任意自研系统，workspace_id 由启动参数注入，不绑定特定系统。

---

## 节点依赖图

```
context_load
  └─> scope_analyze
        └─> case_generate
              └─> case_validate
                    └─> human_confirm_cases
                          └─> execution_plan
                                ├─> run_api_tool
                                ├─> run_ui_tool
                                └─> perf_probe_tool
                                      └─> artifact_collect
                                            └─> defect_analyze
                                                  └─> repair_suggest
                                                        └─> report_generate
                                                              └─> multica_writeback
```

---

## 节点详情

| 节点 | 类型 | 必须输入 | 必须输出 | 阻断条件 |
|---|---|---|---|---|
| context_load | agent_node | multica_issue_id, system_name, tech_stack, source_path, api_base_url_env | context_package.json | 源码路径不存在 |
| scope_analyze | agent_node | context_package.json | scope_analysis.json | context_package.json 缺失 |
| case_generate | agent_node | context_package.json, scope_analysis.json | test_cases.json, test_cases.md, api_cases.yaml, ui_flow.yaml, e2e_cases.yaml, perf_cases.yaml | scope_analysis.json 缺失 |
| case_validate | agent_node | test_cases.json | case_review_matrix.json | test_cases.json 缺失 |
| human_confirm_cases | human_node | test_cases.md, case_review_matrix.json | human_confirmation.json | 超时 60 分钟未确认 → blocked |
| execution_plan | router_node | test_cases.json, human_confirmation.json, runtime_capability.yaml, context_package.json | execution_plan.json | human_confirmation.json 缺失 |
| run_api_tool | tool_node | execution_plan.json（has_api=true）, api_cases.yaml | api_execution_result.json | {{api_base_url_env}} 未配置 |
| run_e2e_tool | tool_node | execution_plan.json（has_e2e=true）, e2e_cases.yaml | e2e_execution_result.json, screenshots/, trace.zip | {{system_name}}_UI_URL 未配置 |
| run_ui_tool | tool_node | execution_plan.json（has_ui=true）, ui_flow.yaml | ui_execution_result.json, screenshots/ | {{system_name}}_UI_URL 未配置 |
| perf_probe_tool | tool_node | execution_plan.json（has_perf=true）, perf_cases.yaml | performance_result.json | 可选，失败不阻断 |
| artifact_collect | tool_node | api/ui/perf 结果 | artifact_index.json | required 产物缺失 → status=blocked |
| defect_analyze | agent_node | artifact_index.json, execution_plan.json | defect_analysis.json | artifact_index.json 缺失 |
| repair_suggest | agent_node | defect_analysis.json, context_package.json | repair_suggestion.md | defect_analysis.json 缺失 |
| report_generate | agent_node | test_cases.json, artifact_index.json, defect_analysis.json, repair_suggestion.md, context_package.json | test_agent_report.md | artifact_index.json 缺失 |
| multica_writeback | tool_node | artifact_index.json, test_agent_report.md, defect_analysis.json | multica_comment_payload.json | test_agent_report.md 缺失 |

---

## 禁止项

- 禁止任何节点在缺少必须输入时继续执行（应输出 blocked 状态）。
- 禁止 tool_node 输出仅有模拟数据的结果（必须有真实 HTTP/浏览器执行证据）。
- 禁止 human_confirm_cases 超时后自动通过（必须 blocked）。
- 禁止任何节点将密码/token 写入输出文件。
- 禁止在本文档中硬编码任何特定系统的环境变量名，必须用 {{变量名}} 占位。
