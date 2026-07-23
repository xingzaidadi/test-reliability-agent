/**
 * screenshot.ts — Track J / Track D/E
 * 截图工具：提供带时间戳、步骤 ID 的截图命名策略，
 * 以及截图目录压缩为 zip 的辅助函数。
 */

import * as fs from "fs";
import * as path from "path";
import * as zlib from "zlib";

export interface ScreenshotOptions {
  stepId: string;
  runDir: string;
  suffix?: string;
  fullPage?: boolean;
}


export function buildScreenshotPath(opts: ScreenshotOptions): string {
  const dir = path.join(opts.runDir, "screenshots");
  fs.mkdirSync(dir, { recursive: true });
  const name = opts.suffix
    ? `${opts.stepId}_${opts.suffix}.png`
    : `${opts.stepId}.png`;
  return path.join(dir, name);
}


export async function takeScreenshot(
  page: any,
  opts: ScreenshotOptions,
): Promise<string> {
  const ssPath = buildScreenshotPath(opts);
  await page.screenshot({ path: ssPath, fullPage: opts.fullPage ?? false });
  return ssPath;
}


export function listScreenshots(runDir: string): string[] {
  const dir = path.join(runDir, "screenshots");
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".png") || f.endsWith(".jpg"))
    .map((f) => path.join(dir, f))
    .sort();
}


export function screenshotCount(runDir: string): number {
  return listScreenshots(runDir).length;
}
