/**
 * flow-loader.ts — Track J (sap-playwright-agent engine)
 * 从 YAML / JSON 文件加载 FlowConfig，支持变量替换。
 */

import * as fs from "fs";
import * as path from "path";
import type { FlowConfig } from "./types";

// Optional yaml dep; fall back to JSON if not installed.
let yaml: any;
try {
  yaml = require("js-yaml");
} catch {
  yaml = null;
}


function substituteVars(obj: any, vars: Record<string, string>): any {
  if (typeof obj === "string") {
    return obj.replace(/\{\{(\w+)\}\}/g, (_m, k) => vars[k] ?? `{{${k}}}`);
  }
  if (Array.isArray(obj)) return obj.map((v) => substituteVars(v, vars));
  if (obj && typeof obj === "object") {
    const result: any = {};
    for (const [k, v] of Object.entries(obj)) {
      result[k] = substituteVars(v, vars);
    }
    return result;
  }
  return obj;
}


export function loadFlow(
  flowPath: string,
  vars: Record<string, string> = {},
): FlowConfig {
  const abs = path.resolve(flowPath);
  if (!fs.existsSync(abs)) {
    throw new Error(`Flow 文件不存在: ${abs}`);
  }

  const raw = fs.readFileSync(abs, "utf-8");
  const ext = path.extname(abs).toLowerCase();

  let config: any;
  if ((ext === ".yaml" || ext === ".yml") && yaml) {
    config = yaml.load(raw);
  } else if (ext === ".json" || !yaml) {
    config = JSON.parse(raw);
  } else {
    throw new Error(`不支持的文件格式: ${ext}，请安装 js-yaml 或使用 JSON`);
  }

  if (!config.steps || !Array.isArray(config.steps)) {
    throw new Error(`Flow 文件缺少 'steps' 字段: ${abs}`);
  }

  // 合并环境变量到 vars
  const envVars: Record<string, string> = {
    TARGET_SYSTEM_UI_URL: process.env.TARGET_SYSTEM_UI_URL ?? "",
    TARGET_SYSTEM_USER:   process.env.TARGET_SYSTEM_USER ?? "",
    ...vars,
  };

  return substituteVars(config, envVars) as FlowConfig;
}
