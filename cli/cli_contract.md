# CLI Contract

workspace: target-system-test

## 完整命令清单

### 诊断

```powershell
# 检查环境变量、源码路径、测试环境连通性
test-squad doctor --workspace target-system-test
```

### Issue 生命周期

```powershell
# 创建 issue
multica issue create `
  --type full_test `
  --workspace target-system-test `
  --title "target-system MVP smoke"

# 分配给 Squad Leader
multica issue assign --issue ISSUE-001 --agent squad_leader_agent

# 启动 Mify workflow
test-squad run `
  --issue ISSUE-001 `
  --workflow super_test_agent_v1 `
  --workspace target-system-test

# 单独跑 API
test-squad run-api `
  --issue ISSUE-001 `
  --cases outputs/runs/ISSUE-001/api_cases.yaml

# 单独跑 UI
test-squad run-ui `
  --issue ISSUE-001 `
  --flow outputs/runs/ISSUE-001/ui_flow.yaml `
  --profile readonly

# 查看状态
test-squad status --issue ISSUE-001

# 生成报告
test-squad report --issue ISSUE-001

# 回写 Multica
multica issue comment `
  --issue ISSUE-001 `
  --file outputs/runs/ISSUE-001/multica_comment_payload.json

multica issue status --issue ISSUE-001 --status passed
```

### 巡检

```powershell
# 手动触发 daily smoke
test-squad patrol `
  --workspace target-system-test `
  --profile smoke
```

## Doctor 检查项

`test-squad doctor` 必须检查以下项，全部通过才允许开始执行：

| 检查项 | 通过标准 |
|---|---|
| TARGET_SYSTEM_BASE_URL | 已设置且非空 |
| TARGET_SYSTEM_TOKEN | 已设置且非空（或 cookie 模式） |
| TARGET_SYSTEM_UI_URL | 已设置且非空 |
| TARGET_SYSTEM_TEST_USER | 已设置，值为 test-user-01 |
| TARGET_SYSTEM_TEST_PASSWORD | 已设置且非空 |
| 源码路径 | E:/workspace/idea/priceCenterServer/target-service 存在 |
| 测试环境连通性 | GET http://your-test-host.example.com/price/actuator/health 或等效检查 |
| outputs/runs 目录 | 存在或可创建 |

任意一项失败，doctor 输出 BLOCKED 并说明原因，不得继续执行。
