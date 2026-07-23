# API Runner

负责执行 target-system 测试环境的 API 用例。

输入：`api_cases.yaml` + `execution_plan.json`
输出：`api_execution_result.json`

## 调用方式

```powershell
test-squad run-api `
  --issue ISSUE-001 `
  --cases outputs/runs/ISSUE-001/api_cases.yaml `
  --env .env.test
```

## 环境变量依赖

```
TARGET_SYSTEM_BASE_URL=http://your-test-host.example.com/price
TARGET_SYSTEM_TOKEN=
TARGET_SYSTEM_TEST_USER=test-user-01
TARGET_SYSTEM_TEST_PASSWORD=（只在 cookie 登录时使用，不写真实值）
```

## X5 协议说明

target-system 所有接口使用 X5 协议，请求格式：

```json
{
  "params": { ... }
}
```

响应格式：

```json
{
  "code": 200,
  "data": {
    "code": "SUCCESS|FAIL|PART_SUCCESS",
    "dataList": [ ... ]
  }
}
```

鉴权：通过 X5 appId 注入（header 或 token），测试时使用 `TARGET_SYSTEM_TOKEN`。
