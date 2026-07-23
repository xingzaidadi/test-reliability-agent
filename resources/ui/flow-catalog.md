# Flow Catalog

super_test_agent UI 引擎 Flow 格式说明与模板。

## Flow YAML 完整格式

```yaml
name: flow_name          # Flow 唯一标识
description: "功能描述"
adapter: generic-web     # Adapter 选择（见下表）
profile: readonly        # readonly（默认）或 interactive
headless: true           # true=后台运行，false=有界面（调试用）
viewport:
  width: 1440
  height: 900
storage_state: "outputs/runs/ISSUE-001/storage_state.json"  # SSO 会话复用

steps:
  - step_id: S01
    name: "打开价格查询页"
    action: navigate
    url: "{{TARGET_SYSTEM_UI_URL}}/price/query"

  - step_id: S02
    name: "等待页面加载"
    action: wait_for_network_idle
    timeout: 15000

  - step_id: S03
    name: "输入物料编码"
    action: type
    selector: 'input[placeholder*="物料编码"]'
    value: "TEST_OBJECT_CODE_001"

  - step_id: S04
    name: "点击查询按钮"
    action: click
    selector: 'button:has-text("查询")'

  - step_id: S05
    name: "断言查询结果"
    action: assert_visible
    selector: ".price-result-list"
    timeout: 10000

  - step_id: S06
    name: "截图记录"
    action: screenshot
    screenshot: "price_query_result.png"
```

## 支持的 Adapter

| Adapter | 说明 | 环境变量 |
|---|---|---|
| `generic-web` | 通用自研 Web 应用（默认，target-system 使用） | `TARGET_SYSTEM_UI_URL` |
| `sap-webdynpro` | SAP WebDynpro（样例） | `SAP_BASE_URL` |
| 自定义 | 通过 `scaffold/create-adapter.ts` 创建 | 自定义 |

## 变量替换

Flow 中的 `{{VAR_NAME}}` 会自动替换为同名环境变量值。

内置变量：
- `{{TARGET_SYSTEM_UI_URL}}` — UI 地址
- `{{TARGET_SYSTEM_USER}}` — 登录用户名

## 选择器约定

1. 优先使用语义化选择器：`button:has-text("查询")`、`input[placeholder="..."]`
2. 次选 data-testid：`[data-testid="search-btn"]`
3. 最后才用 CSS path（与系统版本强耦合，不推荐）

## SSO 自动处理

当页面 URL 包含 `login`/`sso`/`oauth`/`cas` 关键词时，generic-web Adapter 自动填充：
- 用户名：`TARGET_SYSTEM_USER` 环境变量
- 密码：`TARGET_SYSTEM_TEST_PASSWORD` 环境变量（**绝不写入文件**）

登录成功后，`storage_state.json` 保存会话，后续 Flow 可直接复用。
