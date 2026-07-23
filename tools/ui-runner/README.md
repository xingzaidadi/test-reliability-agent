# UI Runner

负责驱动 PurchaseQuery 页面执行只读查询流程。

输入：`ui_flow.yaml` + `execution_plan.json`
输出：`ui_execution_result.json` + `screenshots/` + `trace.zip`

## 调用方式

```powershell
test-squad run-ui `
  --issue ISSUE-001 `
  --flow outputs/runs/ISSUE-001/ui_flow.yaml `
  --profile readonly `
  --env .env.test
```

## 环境变量依赖

```
TARGET_SYSTEM_UI_URL=（PurchaseQuery 页面完整地址，本地配置）
TARGET_SYSTEM_TEST_USER=test-user-01
TARGET_SYSTEM_TEST_PASSWORD=（本地环境变量，不写真实值）
```

## 执行约束

- profile=readonly：只执行查询操作，禁止任何写操作。
- 每个 step 执行后自动截图。
- 全程录制 trace，失败时保存 trace.zip。
- 登录使用 storageState 复用 session，避免每次重新登录。
- SSO 跳转：如遇 SSO 重定向，等待最多 30s，超时标记为 ENV 失败。

## UI 框架

前端仓库：https://your-ui-host.example.com/fe/ProdMgmt/PurchaseMgmt/PurchaseQuery

定位器优先级：
1. `data-testid` 属性（如有）
2. 业务文本（`button:has-text("查询")`）
3. CSS 类名（Element UI / Ant Design）
4. 禁止使用位置定位（nth-child、坐标）
