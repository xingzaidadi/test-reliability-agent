# Report Renderer

把 test_agent_report.md 渲染为可分享的 HTML 报告，并生成 Multica 回写 payload。

输入：test_agent_report.md + artifact_index.json
输出：ui_report.html + multica_comment_payload.json

## 调用方式

```powershell
test-squad render-report --issue ISSUE-001
```

## 输出说明

- `ui_report.html`：含截图嵌入、折叠失败详情、产物链接的 HTML 报告
- `multica_comment_payload.json`：用于 `multica issue comment` 命令回写

## multica_comment_payload.json 格式

```json
{
  "multica_issue_id": "ISSUE-001",
  "status": "passed",
  "comment": "## 测试摘要\n- 总用例：6，P0 全部通过\n- API：5/6 通过\n- UI：1/1 通过\n\n详细报告见产物链接。",
  "artifact_links": [
    {"type": "report",      "path": "outputs/runs/ISSUE-001/test_agent_report.md"},
    {"type": "html_report", "path": "outputs/runs/ISSUE-001/ui_report.html"},
    {"type": "screenshots", "path": "outputs/runs/ISSUE-001/screenshots/"},
    {"type": "trace",       "path": "outputs/runs/ISSUE-001/trace.zip"}
  ]
}
```
