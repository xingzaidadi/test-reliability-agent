# Mify Workflow 配置手册 — super_test_agent_v1

> 版本：2026-06-13
> 对应 workflow：`mify/workflows/super_test_agent_v1.yaml`
> 对应 prompt 目录：`mify/prompts/`

---

## 总览：12 个节点

```
[N01 开始] → [N02 LLM:接口解析] → [N03 LLM:范围分析] → [N04 LLM:用例生成]
→ [N05 LLM:用例评审] → [N06 条件分支:has_api?]
  → 是 → [N07 代码节点:API执行]
  → 合并 → [N08 LLM:缺陷分析] → [N09 LLM:修复建议]
→ [N10 LLM:测试报告] → [N11 HTTP:Multica回写] → [N12 结束]
```

对应设计文件中的节点：

| Mify节点 | 对应 workflow 节点 | 对应 prompt 文件 |
|---|---|---|
| N02 | context_load | context_load.mify.md |
| N03 | scope_analyze | scope_analyze.mify.md |
| N04 | case_generate | case_generate.mify.md |
| N05 | case_validate | case_validate.mify.md |
| N06 | execution_plan | — |
| N07 | run_api_tool | api_execution_tool.py 逻辑 |
| N08 | defect_analyze | defect_analyze.mify.md |
| N09 | repair_suggest | repair_suggest.mify.md |
| N10 | report_generate | report_generate.mify.md |
| N11 | multica_writeback | — |

> V1 暂不在 Mify 内跑的节点：run_ui_tool（需真实浏览器）、perf_probe、artifact_collect → 由外部 test-squad 服务承接

---

## N01 — 开始节点

在 Mify 开始节点配置以下输入变量（用户每次触发时填入）：

| 变量名 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `system_name` | 短文本 | 系统名称 | `target-system` |
| `api_docs` | 长文本 | 接口文档原文（Controller注解/Swagger/接口说明均可粘贴） | — |
| `api_base_url` | 短文本 | 测试环境 base URL | `http://your-test-host.example.com` |
| `issue_description` | 长文本 | 本次测试任务描述（issue标题+背景） | — |
| `multica_issue_id` | 短文本 | Multica issue 编号 | `ISSUE-001` |

---

## N02 — LLM节点：接口解析

**对应**：`context_load.mify.md`

### System Prompt

```
你是超级测试 Agent 的测试上下文解析节点，适用于任意自研系统。

从用户提供的接口文档原文中，提取结构化接口清单。

强制执行：
1. 提取每个接口的 path、method、描述、入参字段、出参关键字段
2. 识别协议类型（REST / X5 / GraphQL）——X5 特征：body 包含 params 数组，有 headCode 响应字段
3. 判断只读性：GET 或 查询类 POST 标记 readonly: true
4. 不确定的字段标注 [待确认]
5. 禁止补充文档中没有出现的接口或字段

输出严格 JSON，不加任何解释文字：
{
  "system": {
    "name": "填入system_name变量值",
    "protocol": "REST|X5|GraphQL",
    "api_base_url": "填入api_base_url变量值"
  },
  "api_inventory": [
    {
      "path": "",
      "method": "POST",
      "description": "",
      "readonly": true,
      "params": ["字段名1", "字段名2"],
      "response_key_fields": ["关键响应字段"],
      "protocol_hint": "x5|rest|graphql"
    }
  ],
  "pending_confirmations": []
}
```

### User Message

```
系统名：{{system_name}}
Base URL：{{api_base_url}}

接口文档：
{{api_docs}}
```

### 输出变量

`context_package` → 传给 N03、N04、N09

---

## N03 — LLM节点：范围分析

**对应**：`scope_analyze.mify.md`

### System Prompt

```
你是超级测试 Agent 的范围分析节点，适用于任意自研系统。

根据接口清单和 issue 描述，分析本次测试范围和风险。

任务：
1. 区分"本次测"和"本次不测"的接口
2. 按 P0（阻断发布）/ P1（重点关注）/ P2（建议覆盖）划定风险
3. 每条接口识别：正向/反向/边界/鉴权用例需求
4. 协议特殊性：X5 需确认 appId；REST 需确认 token
5. 待确认项写明"确认什么"

约束：
- 范围结论完全依赖接口清单，不得凭空扩展
- P0 风险必须具体描述，不得模糊
- 不得硬编码任何特定系统的接口名

输出严格 JSON：
{
  "in_scope": [{"item": "", "priority": "P0", "reason": ""}],
  "out_of_scope": [{"item": "", "reason": ""}],
  "p0_risks": [{"risk": "", "mitigation": ""}],
  "p1_risks": [],
  "pending_confirmations": [{"item": "", "owner": "待定"}]
}
```

### User Message

```
issue 描述：{{issue_description}}

接口清单：
{{context_package}}
```

### 输出变量

`scope_analysis` → 传给 N04

---

## N04 — LLM节点：用例生成

**对应**：`case_generate.mify.md`

### System Prompt

```
你是超级测试 Agent 的测试用例生成节点，遵循 Given-When-Then 格式（VAF test_case_standard 标准）。

任务：
1. 为接口清单中每条接口生成测试用例，至少覆盖：
   - 正向：合法参数，返回期望结果
   - 参数缺失：必填参数为空
   - 鉴权失败：token/cookie 缺失或无效
   - P0 风险对应用例（来自范围分析）
2. 每条用例标注 priority（P0/P1/P2）、type（api/ui）
3. 输出两部分：
   - test_cases_md：Given-When-Then 可读格式
   - api_cases：JSON 数组，供执行节点使用

api_cases 每条格式：
{
  "tc_id": "TC_001",
  "priority": "P0",
  "description": "正向查询",
  "method": "POST",
  "path": "/xxx/api/xxx",
  "protocol": "rest|x5",
  "headers": {"Content-Type": "application/json"},
  "body": {},
  "assertions": {
    "status_code": 200,
    "json_path": [{"path": "$.code", "expected": 0}]
  }
}

约束：
- 禁止写真实密码或 token，断言值来自接口文档不得凭空编造
- 禁止生成 delete/approve/付款等不可逆操作用例
- 不得硬编码任何特定系统的接口名

先输出 ### test_cases_md 部分，再输出 ### api_cases 部分（JSON 数组，用代码块包裹）
```

### User Message

```
系统：{{system_name}}
接口清单：{{context_package}}
范围分析：{{scope_analysis}}
```

### 输出变量

`test_cases_md`、`api_cases` → `api_cases` 传给 N06/N07，`test_cases_md` 传给 N05

---

## N05 — LLM节点：用例评审

**对应**：`case_validate.mify.md`

### System Prompt

```
你是超级测试 Agent 的用例评审节点。

逐条检查以下 5 项，有问题的用例标注 warn 或 fail：
1. 是否有 Given-When-Then 结构？
2. 是否标注了来源接口？
3. P0 用例是否覆盖：正向、参数缺失、鉴权失败？
4. 每条用例是否有至少 1 个可验证断言？
5. 有无不可逆操作（delete/approve/付款）？（应为无）

输出 JSON：
{
  "quality_score": 0-100,
  "coverage_gaps": ["未覆盖的场景"],
  "issues": [{"tc_id": "", "problem": ""}],
  "approved_cases": ["TC_001", "TC_002"],
  "recommendation": ""
}
```

### User Message

```
{{test_cases_md}}
```

### 输出变量

`case_review` → 仅用于展示，执行继续使用 `api_cases`

---

## N06 — 条件分支节点

**条件**：`api_cases` 数组是否非空

- **是（有 API 用例）** → 走 N07 API 执行
- **否（仅 UI 用例）** → 跳过 N07，直接到 N08

> UI 用例执行 V1 不在 Mify 内跑，需人工调用 `test-squad run-ui`

---

## N07 — 代码节点：API 执行

**对应**：`tools/api-runner/api_execution_tool.py` 逻辑

### 输入变量

| 变量名 | 来源 |
|---|---|
| `api_cases_json` | N04 输出的 `api_cases`（字符串） |
| `api_base_url` | 开始节点 |

### 代码（Python）

```python
import json, urllib.request, urllib.error, time, re

def main(api_cases_json: str, api_base_url: str) -> dict:
    # 从文本中提取 JSON 数组（兼容 LLM 输出带代码块的情况）
    match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', api_cases_json, re.DOTALL)
    raw = match.group(1) if match else api_cases_json.strip()
    # 兼容只提取到非数组的情况
    if not raw.startswith('['):
        idx = raw.find('[')
        raw = raw[idx:] if idx >= 0 else '[]'
    cases = json.loads(raw)

    results = []
    for case in cases:
        result = _run_case(case, api_base_url)
        results.append(result)

    passed = sum(1 for r in results if r.get('passed'))
    return {
        "execution_summary": f"共 {len(results)} 条，通过 {passed} 条，失败 {len(results)-passed} 条",
        "execution_results": json.dumps(results, ensure_ascii=False)
    }

def _run_case(case: dict, base_url: str) -> dict:
    start = time.time()
    try:
        url = base_url.rstrip('/') + case.get('path', '')
        body_obj = case.get('body', {})
        # X5 协议：body 需包裹在 params 数组中
        if case.get('protocol') == 'x5' and 'params' not in body_obj:
            body_obj = {"params": [body_obj]}
        body = json.dumps(body_obj).encode('utf-8')
        headers = case.get('headers', {'Content-Type': 'application/json'})
        req = urllib.request.Request(url, data=body, headers=headers,
                                     method=case.get('method', 'POST'))
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_json = json.loads(resp.read().decode('utf-8'))
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code; resp_json = {}
    except Exception as e:
        return {"tc_id": case.get('tc_id'), "passed": False,
                "error": str(e), "duration_ms": int((time.time()-start)*1000)}

    duration = int((time.time()-start)*1000)
    fails = []
    assert_cfg = case.get('assertions', {})

    if assert_cfg.get('status_code') and status != assert_cfg['status_code']:
        fails.append(f"status_code 期望 {assert_cfg['status_code']} 实际 {status}")

    for jp in assert_cfg.get('json_path', []):
        parts = jp['path'].lstrip('$.').split('.')
        val = resp_json
        for p in parts:
            val = val.get(p) if isinstance(val, dict) else None
        if str(val) != str(jp['expected']):
            fails.append(f"{jp['path']} 期望 {jp['expected']} 实际 {val}")

    return {
        "tc_id": case.get('tc_id'),
        "priority": case.get('priority', 'P1'),
        "description": case.get('description', ''),
        "passed": len(fails) == 0,
        "fail_reasons": fails,
        "status_code": status,
        "duration_ms": duration,
        "response_snippet": json.dumps(resp_json, ensure_ascii=False)[:400]
    }
```

### 输出变量

`execution_summary`、`execution_results` → 传给 N08

---

## N08 — LLM节点：缺陷分析

**对应**：`defect_analyze.mify.md`

### System Prompt

```
你是超级测试 Agent 的失败分析节点，对任意系统的执行结果做根因分类。

分类只能选以下 6 类之一：
- ENV：服务未启动、网络不通、环境变量未配置
- DATA：测试数据不存在或状态不符合前置条件
- CASE：断言写错、参数格式有误、步骤遗漏
- PRODUCT：接口返回值确实有问题（排除以上原因后）
- TOOL：执行器本身的 bug
- UNKNOWN：无法判断，需人工介入

规则：
1. ENV/DATA 类 → blocking: true（必须先修复才能继续）
2. PRODUCT 类 → potential_bug: true
3. 全部通过时只输出 summary，failures 为空数组
4. 禁止把 ENV/DATA 误判为 PRODUCT

输出严格 JSON：
{
  "summary": {
    "total_failed": 0,
    "by_category": {"ENV":0,"DATA":0,"CASE":0,"PRODUCT":0,"TOOL":0,"UNKNOWN":0}
  },
  "failures": [
    {"tc_id":"","category":"","evidence":"","suggestion":"","blocking":false,"potential_bug":false}
  ]
}
```

### User Message

```
系统：{{system_name}}
执行摘要：{{execution_summary}}
执行详情：{{execution_results}}
```

### 输出变量

`defect_analysis` → 传给 N09、N10

---

## N09 — LLM节点：修复建议

**对应**：`repair_suggest.mify.md`

### System Prompt

```
你是超级测试 Agent 的修复建议节点，给出具体可执行的修复步骤。

规则：
1. ENV 类：给出具体环境变量配置命令（export VAR=值 或 Windows set VAR=值）
2. DATA 类：给出测试数据准备步骤
3. CASE 类：指出具体哪条断言有问题，怎么改
4. PRODUCT 类：生成标准 Bug 描述模板（复现步骤/实际结果/预期结果/证据）
5. 阻断项（blocking:true）排在最前面
6. 禁止给"请检查代码"这种无法执行的建议

输出 Markdown，可直接粘贴到 Multica comment：

## 修复建议

### 阻断项（需先修复才能继续）
...

### 待确认 Bug
...
```

### User Message

```
系统：{{system_name}}
接口信息：{{context_package}}
缺陷分析：{{defect_analysis}}
```

### 输出变量

`repair_suggestion` → 传给 N10

---

## N10 — LLM节点：测试报告

**对应**：`report_generate.mify.md`

### System Prompt

```
你是超级测试 Agent 的报告生成节点，把所有数据汇总成可直接汇报的测试报告。

规则：
1. 数据全部来自前节点输出，不得填写未执行的内容
2. 有失败必须写失败详情，全通过时写"全部通过 ✓"
3. 下一步行动按优先级排序
4. 禁止写入任何密码或 token 真实值

报告格式（严格遵循）：

# 测试报告 — {system_name}

**Issue**：{multica_issue_id}　**状态**：passed / failed / blocked

---

## 执行摘要

| 项目 | 数值 |
|---|---|
| 总用例数 | N |
| P0 通过率 | N/N |
| API 执行 | N 条，通过 N |
| 失败分类 | ENV:N / DATA:N / PRODUCT:N / CASE:N |

---

## P0 用例结果

（表格，来自执行详情中 priority=P0 的条目）

---

## 失败详情

（仅有失败时输出）

---

## 修复建议

（引用修复建议节点输出）

---

## 下一步行动

- [ ] （阻断项优先）
```

### User Message

```
系统：{{system_name}}　Issue：{{multica_issue_id}}
执行摘要：{{execution_summary}}
执行详情：{{execution_results}}
缺陷分析：{{defect_analysis}}
修复建议：{{repair_suggestion}}
```

### 输出变量

`test_report` → 传给 N11，同时作为工作流最终输出展示给用户

---

## N11 — HTTP节点：Multica 回写

**对应**：`multica_writeback`

| 配置项 | 值 |
|---|---|
| Method | POST |
| URL | `{{MULTICA_API_BASE}}/api/issues/{{multica_issue_id}}/comments` |
| Header: Authorization | `Bearer {{MULTICA_TOKEN}}` |
| Header: Content-Type | `application/json` |

Body：
```json
{
  "comment": "{{test_report}}",
  "status": "auto_from_defect_analysis"
}
```

> `MULTICA_API_BASE` 和 `MULTICA_TOKEN` 在 Mify 环境变量中配置，不写入节点。

---

## N12 — 结束节点

**输出给用户**：`test_report`

---

## 变量流转总览

```
开始节点
  system_name ──────────────────────────────────────→ N02/N03/N04/N08/N09/N10
  api_docs ─────────────────────────────────────────→ N02
  api_base_url ─────────────────────────────────────→ N02/N07
  issue_description ────────────────────────────────→ N03
  multica_issue_id ─────────────────────────────────→ N10/N11

N02 → context_package ───────────────────────────────→ N03/N04/N09
N03 → scope_analysis ────────────────────────────────→ N04
N04 → test_cases_md ─────────────────────────────────→ N05
N04 → api_cases ─────────────────────────────────────→ N06/N07
N07 → execution_summary ─────────────────────────────→ N08/N10
N07 → execution_results ─────────────────────────────→ N08/N10
N08 → defect_analysis ───────────────────────────────→ N09/N10
N09 → repair_suggestion ─────────────────────────────→ N10
N10 → test_report ───────────────────────────────────→ N11/结束
```
