/**
 * flow-runner.ts — Track J (sap-playwright-agent engine)
 * 使用 Playwright 执行 FlowConfig，支持截图、trace、readonly 安全 profile。
 */

import * as fs from "fs";
import * as path from "path";
import type { FlowConfig, FlowResult, StepResult } from "./types";

// Playwright 运行时依赖（可选，如不存在使用 Python ui_execution_tool.py 代替）
let playwright: any;
try {
  playwright = require("playwright");
} catch {
  playwright = null;
}


const DANGER_TEXTS = ["提交", "审批", "删除", "确认提交", "发布", "支付", "下单", "确认删除"];


async function checkDangerous(locator: any): Promise<boolean> {
  try {
    const text = await locator.textContent({ timeout: 1000 });
    return DANGER_TEXTS.some((t) => (text ?? "").includes(t));
  } catch {
    return false;
  }
}


async function runStep(
  page: any,
  step: any,
  runDir: string,
  profile: string,
): Promise<StepResult> {
  const start = Date.now();
  const ssDir = path.join(runDir, "screenshots");
  fs.mkdirSync(ssDir, { recursive: true });

  const result: StepResult = {
    step_id:    step.step_id,
    name:       step.name,
    action:     step.action,
    status:     "passed",
    duration_ms: 0,
  };

  try {
    if (step.skip) {
      result.status = "skipped";
      return result;
    }

    switch (step.action) {
      case "navigate":
        await page.goto(step.url, { waitUntil: "networkidle", timeout: step.timeout ?? 30000 });
        break;

      case "click": {
        const loc = page.locator(step.selector);
        if (profile === "readonly" && await checkDangerous(loc)) {
          result.status = "skipped";
          result.error  = `[readonly] 危险按钮跳过: ${step.selector}`;
          break;
        }
        await loc.click({ timeout: step.timeout ?? 10000 });
        break;
      }

      case "type":
        await page.locator(step.selector).fill(step.value ?? "", { timeout: step.timeout ?? 10000 });
        break;

      case "select":
        await page.locator(step.selector).selectOption(step.value ?? "", { timeout: step.timeout ?? 10000 });
        break;

      case "wait":
        await page.waitForTimeout(step.timeout ?? 1000);
        break;

      case "wait_for_selector":
        await page.waitForSelector(step.selector, { timeout: step.timeout ?? 15000 });
        break;

      case "wait_for_network_idle":
        await page.waitForLoadState("networkidle", { timeout: step.timeout ?? 30000 });
        break;

      case "scroll":
        await page.locator(step.selector ?? "body").scrollIntoViewIfNeeded();
        break;

      case "hover":
        await page.locator(step.selector).hover({ timeout: step.timeout ?? 5000 });
        break;

      case "press_key":
        await page.keyboard.press(step.value ?? "Enter");
        break;

      case "assert_text": {
        const text = await page.locator(step.selector).textContent({ timeout: step.timeout ?? 5000 });
        const expected = step.assertions?.[0]?.expected as string ?? "";
        if (!String(text ?? "").includes(expected)) {
          throw new Error(`断言失败: 期望包含 '${expected}'，实际: '${text}'`);
        }
        break;
      }

      case "assert_visible": {
        const visible = await page.locator(step.selector).isVisible({ timeout: step.timeout ?? 5000 });
        if (!visible) throw new Error(`断言失败: 元素不可见 '${step.selector}'`);
        break;
      }

      case "assert_url": {
        const currentUrl = page.url();
        const expected = step.assertions?.[0]?.expected as string ?? "";
        if (!currentUrl.includes(expected)) {
          throw new Error(`断言失败: URL 不包含 '${expected}'，当前: '${currentUrl}'`);
        }
        break;
      }

      case "screenshot":
        break; // handled below

      default:
        result.error = `未知 action: ${step.action}`;
    }

    // 截图
    const ssName = step.screenshot ?? `${step.step_id}.png`;
    const ssPath = path.join(ssDir, ssName);
    await page.screenshot({ path: ssPath, fullPage: false });
    result.screenshot = ssPath;

  } catch (err: any) {
    result.status = "failed";
    result.error  = String(err.message ?? err);

    // 失败截图
    try {
      const ssPath = path.join(ssDir, `${step.step_id}_failed.png`);
      await page.screenshot({ path: ssPath });
      result.screenshot = ssPath;
    } catch {}
  }

  result.duration_ms = Date.now() - start;
  return result;
}


export async function runFlow(
  config: FlowConfig,
  issueId: string,
  runDir: string,
): Promise<FlowResult> {
  if (!playwright) {
    throw new Error(
      "Playwright 未安装。请运行 npm install playwright 或使用 Python ui_execution_tool.py",
    );
  }

  fs.mkdirSync(runDir, { recursive: true });

  const profile   = config.profile  ?? "readonly";
  const headless  = config.headless ?? true;
  const viewport  = config.viewport ?? { width: 1440, height: 900 };

  const browser = await playwright.chromium.launch({ headless });
  const context = await browser.newContext({
    viewport,
    storageState: config.storage_state && fs.existsSync(config.storage_state)
      ? config.storage_state
      : undefined,
  });

  // Tracing
  await context.tracing.start({ screenshots: true, snapshots: true });

  const page = await context.newPage();
  const stepResults: StepResult[] = [];

  for (const step of config.steps) {
    const r = await runStep(page, step, runDir, profile);
    stepResults.push(r);
    const sym = r.status === "passed" ? "PASS" : r.status === "skipped" ? "SKIP" : "FAIL";
    console.log(`  [${sym}] ${r.step_id} ${r.name} (${r.duration_ms}ms)`);
    if (r.status === "failed") break; // stop on first failure
  }

  // Save trace
  const tracePath = path.join(runDir, "trace.zip");
  await context.tracing.stop({ path: tracePath });

  // Save storage state
  if (config.storage_state) {
    await context.storageState({ path: config.storage_state });
  }

  await browser.close();

  const passed = stepResults.filter((s) => s.status === "passed").length;
  const failed = stepResults.filter((s) => s.status === "failed").length;

  const flowResult: FlowResult = {
    flow_name:    config.name,
    issue_id:     issueId,
    executed_at:  new Date().toISOString(),
    status:       failed > 0 ? "failed" : "passed",
    total_steps:  stepResults.length,
    passed_steps: passed,
    failed_steps: failed,
    steps:        stepResults,
    trace_path:   tracePath,
  };

  const resultPath = path.join(runDir, "ui_execution_result.json");
  fs.writeFileSync(resultPath, JSON.stringify(flowResult, null, 2), "utf-8");
  console.log(`[flow-runner] ${passed}/${stepResults.length} 通过  结果: ${resultPath}`);

  return flowResult;
}
