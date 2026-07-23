# Action Catalog

super_test_agent UI 执行引擎支持的 Action 类型完整说明。

## 只读操作（readonly profile 允许）

| Action | 必须字段 | 可选字段 | 说明 |
|---|---|---|---|
| `navigate` | `url` | `timeout` | 导航到指定 URL，等待 networkidle |
| `click` | `selector` | `timeout` | 点击元素；readonly profile 中，按钮文本含「提交/删除/审批/发布/支付」时自动跳过 |
| `type` | `selector`, `value` | `timeout` | 填写输入框（使用 fill，会先清空） |
| `select` | `selector`, `value` | `timeout` | 选择下拉框选项（按 value 或 text 匹配） |
| `wait` | `timeout` | — | 等待固定毫秒数（建议 ≤ 3000ms，优先用 wait_for_*） |
| `wait_for_selector` | `selector` | `timeout` | 等待元素出现在 DOM 中 |
| `wait_for_network_idle` | — | `timeout` | 等待网络请求停止（500ms 内无请求） |
| `assert_text` | `selector` | `timeout`, `assertions` | 断言元素文本包含指定内容 |
| `assert_visible` | `selector` | `timeout` | 断言元素可见 |
| `assert_url` | — | `assertions` | 断言当前 URL 包含指定字符串 |
| `screenshot` | — | `screenshot` | 主动截图（每步也会自动截图） |
| `scroll` | — | `selector` | 滚动元素到视图中心 |
| `hover` | `selector` | `timeout` | 悬停，不触发点击 |
| `press_key` | `value` | — | 按下键盘按键（如 `Enter`、`Escape`、`Tab`） |

## 非只读操作（需要 interactive profile）

| Action | 说明 | 使用条件 |
|---|---|---|
| `upload_file` | 上传文件到 file input | 需 profile=interactive + 明确授权 |
| `custom` | Adapter 自定义扩展 Action | 由各系统 Adapter 实现 |

## 危险文本列表（readonly profile 自动跳过的按钮）

```
提交  审批  删除  确认提交  发布  支付  下单  确认删除
```

如需测试这些按钮，必须使用 `profile: interactive` 并确认测试环境数据可回滚。

## Assertions 格式

```yaml
assertions:
  - type: text        # 文本断言
    expected: "查询成功"
    contains: true    # 默认 true，false 则要求完全匹配
  - type: visible     # 可见性
  - type: url         # URL 断言
    expected: "/price/query"
  - type: attribute   # 属性断言
    selector: ".result-count"
    expected: "10"
  - type: count       # 元素数量断言
    expected: 5
```
