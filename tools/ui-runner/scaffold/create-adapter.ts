/**
 * create-adapter.ts — Track J
 * 脚手架工具：为新业务系统创建 Adapter 模板文件。
 *
 * 使用：
 *   npx ts-node scaffold/create-adapter.ts --name my-system --url-env MY_SYSTEM_URL
 */

import * as fs from "fs";
import * as path from "path";

function createAdapterTemplate(name: string, urlEnvKey: string): string {
  const className = name
    .split(/[-_]/)
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join("") + "Adapter";

  return `/**
 * ${name}-adapter.ts — 为 ${name} 系统创建的 Adapter
 * 由 create-adapter scaffold 自动生成，请根据实际系统登录逻辑修改。
 */

import type { Adapter, AdapterContext } from "../adapters/registry";

export const ${className}: Adapter = {
  name: "${name}",
  description: "${name} 系统适配器",
  baseUrlEnvKey: "${urlEnvKey}",

  async isLoggedIn(page: any): Promise<boolean> {
    // TODO: 根据 ${name} 系统的已登录特征修改
    const url = page.url().toLowerCase();
    return !["login", "sso", "signin"].some((k) => url.includes(k));
  },

  async login(page: any, ctx: AdapterContext): Promise<void> {
    // TODO: 根据 ${name} 系统的登录页面修改选择器
    const username = ctx.credentials?.username ?? process.env["${urlEnvKey.replace("URL","USER")}"] ?? "";
    const password = ctx.credentials?.password ?? process.env["${urlEnvKey.replace("URL","PASSWORD")}"] ?? "";

    await page.fill('input[name="username"]', username, { timeout: 5000 });
    await page.fill('input[type="password"]', password, { timeout: 5000 });
    await page.click('button[type="submit"]', { timeout: 5000 });
    await page.waitForLoadState("networkidle", { timeout: 15000 });
  },
};

// 注册到全局 adapter registry:
// import { registerAdapter } from "../adapters/registry";
// registerAdapter(${className});
`;
}

function main() {
  const args = process.argv.slice(2);
  const nameIdx = args.indexOf("--name");
  const urlIdx  = args.indexOf("--url-env");

  const name    = nameIdx >= 0 ? args[nameIdx + 1] : "my-system";
  const urlEnv  = urlIdx  >= 0 ? args[urlIdx + 1]  : "MY_SYSTEM_URL";

  const outFile = path.join(__dirname, "..", "adapters", `${name}-adapter.ts`);
  const content = createAdapterTemplate(name, urlEnv);

  fs.writeFileSync(outFile, content, "utf-8");
  console.log(`[create-adapter] Adapter 模板已生成: ${outFile}`);
  console.log(`下一步:`);
  console.log(`  1. 编辑 ${outFile} 修改登录逻辑`);
  console.log(`  2. 在 adapters/registry.ts 中 registerAdapter(${name}Adapter)`);
  console.log(`  3. 在 flow yaml 中设置 adapter: ${name}`);
}

main();
