# Artifact Collector

收集所有 tool 产物，生成统一的 artifact_index.json。

输入：api_execution_result.json + ui_execution_result.json + performance_result.json（各自可选）
输出：artifact_index.json

## 调用方式

```powershell
test-squad collect-artifacts --issue ISSUE-001
```

## 逻辑

1. 扫描 `outputs/runs/{issue_id}/` 目录下所有产物文件。
2. 按 artifact_contract.md 定义的类型逐一检查是否存在。
3. required=true 的产物缺失时，整体 status 设为 blocked。
4. 汇总所有 tool 的 passed/failed 数，计算整体 status：
   - 全部 P0 通过 → passed
   - 有 P0 失败 → failed
   - 有 required 产物缺失 → blocked
5. 写入 artifact_index.json。
