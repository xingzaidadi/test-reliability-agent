---
name: java-codegen-pro
description: |
  TRIGGER when the user asks to generate Java Playwright automation code, Java TestNG Page Object code, PO/Test files from an SOP, SAP automation code, or code from a Playwright recording.
  TRIGGER when user says ANY of: Java Playwright自动化、Java自动化脚本、生成Java PO、生成PO/Test、SOP生成Java代码、SOP转自动化、流程转Java Playwright、SAP自动化、Playwright录制生成Java、/java-codegen-pro
  TRIGGER when user context includes: SAP自动化、Playwright Java项目、PO/Test生成、Java测试代码、TestNG、Page Object、playwright codegen录制脚本
  Also known as: Java自动化代码生成Pro、Playwright代码生成Pro
  DO NOT TRIGGER: 只问Playwright API用法、只修bug、普通非自动化代码生成、纯前端/非Java项目、只说"录制"但不是Playwright自动化录制、只提供文档但没要求生成代码
  ---
  功能：把业务流程（Word/截图/口述/SOP/Playwright录制脚本）转成符合项目风格的 Java Playwright + TestNG + Page Object 自动化代码。
  三条输入路径：Word/截图/口述 → 先整理SOP等确认；已有SOP → 直接生成代码；录制脚本 → AI理解+精确定位器直出代码。
---

# Java Playwright 代码生成 Pro

把业务流程整理成标准 SOP，再参考目标项目风格生成 Java Playwright + TestNG + Page Object 自动化代码。

**三条输入路径**：
- 路径 A：Word/截图/口述 → 整理 SOP → 生成代码
- 路径 B：已有 SOP → 直接生成代码
- 路径 C：Playwright 录制脚本 → AI 理解语义 + 保留精确定位器 → 生成代码

## 核心原则

1. **先整理 SOP，再写代码。** 如果用户给的是 Word、截图、测试用例或口述步骤，先整理成 SOP 并让用户确认。
2. **先读项目，再生成代码。** 生成前必须至少读 1 个 PO + 1 个 Test + 工具类；无参考项目时用 `references/default-code-style.md` 兜底。

## 触发后第一件事：接受输入，立刻开始处理

**核心原则：用户给了什么就先处理什么，处理完再问缺失项。不要在开头列清单。**

### 用户已经提供了材料（Word/截图/口述/SOP/录制脚本）

直接开始处理：
1. 提取内容、识别截图、整理信息。如果是 `.js` 录制脚本，直接进入路径 C。
2. 处理过程中记录缺失项（测试数据、成功提示、字段名等）。
3. 处理完后，将缺失项和需要确认的路径信息**一次性**问用户。

问的时候用这个格式：

```text
我已经整理了 SOP，有几个地方需要确认：

1. [具体缺失项1]
2. [具体缺失项2]
3. 参考项目路径：你的项目代码在哪里？
4. 目标项目路径：代码写到哪里？（和参考项目一样就说"同参考项目"）
```

### 用户什么材料都没给

```text
好的，我来帮你生成 Java Playwright 自动化代码。
请把你有的材料发给我（Word 文档路径、截图、口述步骤、SOP 都行），我来处理。

也可以直接发页面 URL，我帮你启动浏览器录制，操作完自动转成 Java 代码。
```

### 用户发来 URL（询问是否录制）

**规则：用户明确说"帮我录制"、"录制这个页面"、"用录制方式"并附带 URL 时，才进入路径 C。**
单纯在 SOP 或描述中出现 URL（如系统地址）不触发录制，继续按路径 A/B 处理。

### 用户选择录制（路径 C 启动录制）

启动录制前先检查环境：

```bash
node --version
npx playwright --version
npx playwright install --dry-run
```

| 检查项 | 正常 | 异常时告知用户 |
|--------|------|---------------|
| Node.js | 版本 ≥ 16 | 「未找到 Node.js，请从 https://nodejs.org 下载安装」 |
| Playwright 包 | 有版本号输出 | 「未安装 Playwright，请运行：npm install -g @playwright/test」 |
| 浏览器 | chromium 已安装 | 「浏览器未安装，请运行：npx playwright install chromium」 |

环境检查通过后，**必须先询问用户确认**再启动录制：

```text
环境检查通过。我将打开浏览器录制页面：<URL>
录制文件将保存到：~/Desktop/recording_<功能名>.js
确认启动录制吗？（输入"确认"或"是"继续，输入"取消"停止）
```

用户确认后才执行：

```bash
npx playwright codegen --output ~/Desktop/recording_<功能名>.js "<URL>"
```

用户取消 → 停止执行，询问用户是否改用路径 A/B。
录制完成后立即自动读取该文件，进入"录制脚本处理"流程。

### 参考项目路径的处理

- 如果用户已经告知 → 直接用。
- 如果用户没告知 → 在整理完 SOP、准备生成代码前再问。

### 测试数据的处理

1. 从材料中提取能识别的数据（单号、账号、金额、供应商号等）。
2. 提取到的数据写入 SOP 的测试数据段。
3. 提取不到的标注 `[待确认：...]`。

## 流程总览

```text
触发 skill
  -> 用户有材料 → 直接处理
  -> 用户没材料 → 提示三条路供选择
  -> 判断输入类型：
     路径 C（浏览器录制）：
       -> 检查环境（Node.js + Playwright包 + 浏览器）
       -> 环境有问题 → 告知缺失项和安装命令，停止
       -> 环境正常 → 启动 playwright codegen
       -> 等待用户关闭浏览器 → 自动读取输出文件
       -> AI 解析每步操作语义，保留精确定位器
       -> 生成 PO/Test → 编译 → 跑测试 → 自动修复
     路径 A（Word/截图/口述）：
       -> 整理标准 SOP
       -> 用户确认 SOP
       -> 确认后进入路径 B
     路径 B（已有 SOP）：
       -> 拆解 SOP，输出实现计划
       -> 读取参考项目代码风格
       -> 确认目标项目写入范围
       -> 生成 Java PO/Test
       -> 编译验证（mvn test-compile）
       -> 编译失败则自动修复
       -> 编译通过，问用户是否运行实际测试
       -> 运行测试失败则读截图+日志调试
       -> 最终说明变更、命令、假设
```

## 阶段零：处理 Word / 截图 / 口述材料

### Word 文档

当用户提供 `.docx` 路径时，调用脚本提取文字、表格和图片：

```bash
python scripts/extract_word.py "<docx路径>"
```

提取后必须：

1. 读取文字和表格。
2. 逐张读取图片，识别字段名、按钮名、菜单项、表格结构、弹窗内容、成功提示。
3. 参考 `references/SOP-format.md` 整理标准 SOP。
4. **必须将 SOP 写入文件**（`<功能名>_标准SOP.md`，与原始材料同目录）。
5. 让用户确认 SOP 后再生成代码。

### 口述 + 截图

1. 读取截图识别页面元素。
2. 结合口述内容整理标准 SOP。
3. 不明确的标注 `[待确认：...]`。
4. **必须将 SOP 写入文件**。

### 纯口述

必须先输出 SOP 草稿（含 `[待确认：...]` 标记），再一次性询问缺失信息。

## 路径 B 入口：用户直接提供了 SOP

材料中包含具体页面元素名称和操作步骤序列 → 跳过阶段零，直接从"第一步"开始。

## 路径 C 入口：Playwright 录制脚本

### 录制脚本处理

读取 JS 脚本后执行以下转换：

1. **逐行解析**：识别每个 Playwright 操作（click/fill/dblclick/press/waitForTimeout/goto）。
2. **保留精确定位器**：录制产物的定位器直接复用，不用 AI 猜测。
3. **AI 标注语义**：理解每步操作的业务含义，写中文注释。
4. **JS → Java 转换**：
   - `page.getByRole('button', { name: 'xxx' })` → `p.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("xxx"))`
   - `page.locator('selector').click()` → `p.locator("selector").click()`
   - `page.fill('selector', 'value')` → `p.locator("selector").fill("value")`
   - `page.waitForTimeout(ms)` → `p.waitForTimeout(ms)`
5. **生成标准 PO/Test**：每步操作封装为方法，组成完整业务流程。

处理完后一次性确认：功能名称、参考项目路径、目标项目路径、校验点。

## 第一步：拆解 SOP

输出简短实现计划：系统/功能/测试数据/前置条件/步骤/校验点/文件清单/待确认项。

## 第二步：读取参考项目

至少读取 1 个 PO + 1 个 Test + 工具类。

系统匹配：
- SRM -> `srmweb/`、`SettlementPO`、`SettlementTest`
- ECC -> `ecc/`、`ECCPaymentProposalPO`、`PaymentProposalTest`

无参考项目时用 `references/default-code-style.md`。

## 第三步：确认目标项目写入范围

```text
目标项目路径：
准备新增文件：
准备修改文件：
不会修改的文件：
```

## 第四步：生成 Java 代码

根据参考项目风格生成，不套固定模板。

### PO 类结构

```text
src/main/java/.../{Feature}PO.java
src/test/java/.../{Feature}Test.java
```

### Test 类职责

获取账号 → 初始化浏览器 → 登录 → 供应商绑定 → 调用 PO 方法 → finally 写出报告

### PO 类职责

菜单点击、字段输入、表格查询、行选择、弹窗处理、按钮点击、页面校验、截图和日志

### SAP 自动化规范（强制，生成每个文件前必须遵守）

#### 规范1：LightReporter 集成

每个对外暴露的 **public 业务方法**必须使用 `LightReporter` 记录步骤、截图和报告（private 辅助方法如 `selectFirstRow` 不需要）：

```java
LightReporter report = new LightReporter(page, "ECC-ZFI001H-付款建议", businessId);
report.addParam("公司代码", companyCode);
try {
    report.step("填写查询条件", () -> {
        // 操作代码
    });
    report.step("点击执行", () -> {
        // 操作代码
    });
} finally {
    report.finish(); // 必须在 finally 中调用，保证报告一定写出
}
```

多方法共用一份报告时，在 PO 类中声明 `private LightReporter report` 字段，跨方法共享，由 Test 类在 `finally` 里调用 `po.finishReport()`。

#### 规范2：SkipException 语义

业务前置条件不满足时（数据状态异常、按钮不可用、单据已处理），抛 `SkipException` 而非 `RuntimeException`：

```java
// 检测页面是否有业务错误（已操作过、状态不满足等）
Object msgObj = page.evaluate("() => { ... }");
if (msgObj != null) {
    String msg = msgObj.toString();
    if (msg.contains("已生成") || msg.contains("已确认") || msg.contains("不能重复")) {
        throw new SkipException("【操作名】跳过（SKIP）：" + msg);
    }
}
```

SkipException = 数据问题，TestNG 标记为 SKIP；RuntimeException = 代码/系统问题，TestNG 标记为 FAIL。两者语义不同，不可混用。

#### 规范3：isEnabled() 前置检查

操作关键按钮前必须先检查 `isEnabled()`，按钮不可用时直接 SKIP，不强行点击等 30s timeout：

```java
Locator btn = page.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("生成SAP暂估发票"));
btn.waitFor(new Locator.WaitForOptions().setState(WaitForSelectorState.VISIBLE).setTimeout(10000));
if (!btn.isEnabled()) {
    throw new SkipException("【生成暂估发票】按钮不可点击，数据可能已生成或状态不满足");
}
btn.click();
```

适用场景：生成/确认/驳回/过账等一次性操作按钮，数据消耗后按钮会变灰。

#### 规范4：智能等待策略

禁止无差别使用 `Thread.sleep`，按场景选择正确等待方式：

| 场景 | 正确写法 | 禁止写法 |
|------|---------|---------|
| 页面导航后等目标元素 | `locator.waitFor(VISIBLE, timeout=15000)` | ~~`Thread.sleep(8000)`~~ |
| 等查询结果出现 | `page.locator("[id*='-mrss-cont-left-Row-0'] td").first().waitFor(VISIBLE)` | ~~`Thread.sleep(5000)`~~ |
| 等弹窗出现（可能没有） | `locator.or(locator2).nth(0).waitFor(timeout=500)` + catch TimeoutError | ~~串行三层 try-catch~~ |
| 业务操作后等 SAP 响应 | `page.waitForLoadState(LoadState.NETWORKIDLE, timeout=60000)` | ~~`Thread.sleep(10000)`~~ |
| dispatchEvent 事件序列 | 保留 `Thread.sleep(100)`（DOM 事件时序必需） | 不可删除 |

**注意**：SAP WebDynpro 页面导航后禁止用 `waitForLoadState(NETWORKIDLE)`，因为 SAP 后台心跳轮询会让它永远等待。应改为等具体目标元素出现。

#### 规范5：evaluate() 返回值必须检查

所有 `page.evaluate()` 调用必须检查返回值，找不到元素时主动抛异常，禁止静默失败：

```java
// 错误写法：返回值被丢弃，操作失败也记录 SUCCESS
page.evaluate("() => { var el = document.querySelector('xxx'); if(el) el.click(); }");

// 正确写法：检查返回值，失败时抛异常
Object result = page.evaluate("() => { var el = document.querySelector('xxx'); if(el){ el.click(); return true; } return false; }");
if (!Boolean.TRUE.equals(result)) {
    throw new RuntimeException("未找到目标元素[xxx]，操作失败");
}
```

**根因**：`evaluate()` 返回 false 不是异常，LightReporter 的 `step()` 只 catch Exception，会把静默失败记录为 SUCCESS，报告失真。

#### 规范6：SAP 元素定位优先级

SAP 页面**交互元素**定位按以下优先级，越靠前越稳定：

```text
1. getByRole(AriaRole.BUTTON, name="按钮名")          ← 首选，语义化
2. getByText("文本", exact=true)                       ← 文本节点可见时可用
3. page.locator("[id*='-mrss-cont-left-Row-0'] td")   ← SAP 表格行选中专用
4. page.evaluate("JS TreeWalker 遍历")                 ← 终极方案，标签+相邻input
```

SAP 弹窗定位：`[role='dialog'], [role='alertdialog'], .urMsgBox, .lsPopupWindow`（不是 `.sapMDialog`）

**消息区定位**（用于校验点，见 `references/assertion-patterns.md`）：
- FPM 右上角：`.sapLsFPMMessageArea`
- WebDynpro 消息条：`.urMessageArea, [class*='urMsg']`
- Fiori 提示条：`.sapMMsgStrip, .sapMMessageStrip`

### 校验点与断言（强制）

> 完整规则见 `references/assertion-patterns.md`

- 每个校验点必须生成断言代码（throw RuntimeException），禁止只记录日志
- 截图在断言之前（先留证据再判断）
- 未确认的提示文本用 `// TODO: 确认实际成功提示文本` 标注，但仍必须是断言

### Java 约束

- 账号密码不硬编码，复用 MifyUtil、SapLoginUtil
- 日志/截图/步骤记录复用 TestContext、ExtentReportLog、ExtentImageLog、LightReporter

### SAP WebDynpro 特殊处理（强制）

> 完整规则见 `references/sap-webdynpro-rules.md`

- 表格行选中：`dispatchEvent("mousedown/mouseup/click")` 三连，不能直接 click
- 下拉框：keyboard ArrowDown + Tab 关闭，禁止 click option / Escape / Enter
- 弹窗：`[role='dialog'], .urMsgBox, .lsPopupWindow`
- 页面类型判断：URL含`webdynpro`或有`lsButton` → WebDynpro；有`.sapMSlt` → Fiori

## 第五步：编译验证与自动修复

> 完整修复清单见 `references/compile-fix-guide.md`

代码生成后必须执行 `mvn test-compile`。编译失败时直接修，不问用户。

### 编译通过后：主动提出运行测试

```text
编译验证通过。接下来我帮你运行实际测试，如果有问题我会自动修复并重跑。需要我来做吗？
```

### 运行测试失败时：自动修复并重跑

1. 读取错误堆栈和截图
2. 判断失败阶段：登录失败 / 定位器 timeout / 断言失败 / 页面状态异常
3. 修复后立即重跑，不问用户
4. 重复循环直到通过或确认是环境问题

**退出条件**：VPN不通 / 数据失效 / 同问题修3次未过

### 定位器降级策略（SAP WebDynpro）

```text
Level 1: getByRole(AriaRole.BUTTON, name="按钮名")      ← 首次生成默认
Level 2: getByText("按钮名", exact=true)
Level 3: locator("text=标签名").locator("xpath=following::input[1]")
Level 4: page.evaluate("JS TreeWalker 遍历")             ← 终极方案
```

## 最终答复

简洁说明：
- 参考项目路径 / 目标项目路径
- 修改或新增的文件
- 生成的类和方法
- 验证命令和结果
- 运行测试的命令
- 仍需用户确认的运行时假设或环境阻塞
