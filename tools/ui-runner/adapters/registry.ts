/**
 * adapters/registry.ts — Track J
 * Adapter 注册表。
 * Adapter 封装特定系统的登录逻辑和选择器约定，
 * flow-runner 通过 FlowConfig.adapter 字段选择 Adapter。
 *
 * 默认提供两个 Adapter：
 *   generic-web    — 通用 Web 应用（target-system 使用此 Adapter）
 *   sap-webdynpro  — SAP WebDynpro（参考样例，非平台默认目标）
 */

import type { AdapterContext } from "../engine/types";

export interface Adapter {
  name: string;
  description: string;
  /** 系统基础 URL 环境变量名 */
  baseUrlEnvKey: string;
  /** 登录逻辑 */
  login: (page: any, ctx: AdapterContext) => Promise<void>;
  /** 是否已登录检测 */
  isLoggedIn: (page: any) => Promise<boolean>;
}


const GenericWebAdapter: Adapter = {
  name: "generic-web",
  description: "通用自研 Web 应用，支持 SSO/CAS 自动处理",
  baseUrlEnvKey: "TARGET_SYSTEM_UI_URL",

  async isLoggedIn(page: any): Promise<boolean> {
    const url = page.url();
    const loginKeywords = ["login", "sso", "oauth", "cas", "auth", "signin"];
    return !loginKeywords.some((k) => url.toLowerCase().includes(k));
  },

  async login(page: any, ctx: AdapterContext): Promise<void> {
    const url = page.url().toLowerCase();
    const onLoginPage = ["login", "sso", "oauth", "cas", "auth"].some((k) => url.includes(k));
    if (!onLoginPage) return;

    const username = ctx.credentials?.username
      ?? process.env.TARGET_SYSTEM_USER ?? "";
    const password = ctx.credentials?.password
      ?? process.env.TARGET_SYSTEM_TEST_PASSWORD ?? "";

    // 常见用户名选择器（按优先级尝试）
    const userSelectors = [
      'input[name="username"]',
      'input[placeholder*="用户名"]',
      'input[placeholder*="工号"]',
      'input[type="text"]:first-of-type',
    ];
    const pwdSelectors = [
      'input[name="password"]',
      'input[type="password"]',
    ];
    const submitSelectors = [
      'button[type="submit"]',
      'input[type="submit"]',
      'button:has-text("登录")',
      'button:has-text("Login")',
    ];

    for (const sel of userSelectors) {
      try {
        await page.fill(sel, username, { timeout: 2000 });
        break;
      } catch { continue; }
    }
    for (const sel of pwdSelectors) {
      try {
        await page.fill(sel, password, { timeout: 2000 });
        break;
      } catch { continue; }
    }
    for (const sel of submitSelectors) {
      try {
        await page.click(sel, { timeout: 2000 });
        break;
      } catch { continue; }
    }

    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  },
};


const SapWebDynproAdapter: Adapter = {
  name: "sap-webdynpro",
  description: "SAP WebDynpro 系统 Adapter（样例，非平台默认目标）",
  baseUrlEnvKey: "SAP_BASE_URL",

  async isLoggedIn(page: any): Promise<boolean> {
    try {
      const logoffVisible = await page.locator('[title="Log Off"]').isVisible({ timeout: 2000 });
      return logoffVisible;
    } catch {
      return false;
    }
  },

  async login(page: any, ctx: AdapterContext): Promise<void> {
    const username = ctx.credentials?.username ?? process.env.SAP_USER ?? "";
    const password = ctx.credentials?.password ?? process.env.SAP_PASSWORD ?? "";

    try {
      await page.fill('#USERNAME_FIELD input', username, { timeout: 5000 });
      await page.fill('#PASSWORD_FIELD input', password, { timeout: 5000 });
      await page.click('#LOGIN_LINK', { timeout: 5000 });
      await page.waitForLoadState("networkidle", { timeout: 30000 });
    } catch (e) {
      throw new Error(`SAP 登录失败: ${e}`);
    }
  },
};


const _registry = new Map<string, Adapter>([
  ["generic-web",   GenericWebAdapter],
  ["sap-webdynpro", SapWebDynproAdapter],
]);


export function getAdapter(name: string): Adapter | undefined {
  return _registry.get(name ?? "generic-web");
}

export function registerAdapter(adapter: Adapter): void {
  _registry.set(adapter.name, adapter);
}

export function listAdapters(): Adapter[] {
  return [..._registry.values()];
}
