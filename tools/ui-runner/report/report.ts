/**
 * report.ts — Track J / Track D/E
 * UI 执行报告生成：读取 ui_execution_result.json + 截图目录，
 * 输出 Markdown 摘要和 Multica comment payload。
 */

import * as fs from "fs";
import * as path from "path";
import type { FlowResult, StepResult } from "../engine/types";

export interface UiReportOptions {
  issueId: string;
  runDir: string;
  workspaceId?: string;
}


function statusBadge(status: string): string {
  const map: Record<string, string> = {
    passed:  "PASS",
    failed:  "FAIL",
    skipped: "SKIP",
    blocked: "BLOCKED",
  };
  return map[status] ?? status.toUpperCase();
}


function buildMarkdown(result: FlowResult, opts: UiReportOptions): string {
  const lines: string[] = [
    `# UI 执行报告 — ${opts.issueId}`,
    "",
    `- Flow: **${result.flow_name}**`,
    `- 整体状态: **${statusBadge(result.status)}**`,
    `- 步骤: ${result.passed_steps}/${result.total_steps} 通过，${result.failed_steps} 失败`,
    `- 执行时间: ${result.executed_at}`,
    "",
    "## 步骤明细",
    "",
    "| 步骤 | 名称 | 动作 | 状态 | 耗时 | 错误 |",
    "|---|---|---|---|---|---|",
  ];

  for (const step of result.steps) {
    const err = step.error ? step.error.slice(0, 60).replace(/\|/g, "\\|") : "";
    lines.push(
      `| ${step.step_id} | ${step.name} | ${step.action} | ${statusBadge(step.status)} | ${step.duration_ms}ms | ${err} |`,
    );
  }

  if (result.trace_path && fs.existsSync(result.trace_path)) {
    lines.push("", `Trace 文件: \`${result.trace_path}\``);
  }

  return lines.join("\n");
}


export function generateUiReport(opts: UiReportOptions): {
  markdown: string;
  markdownPath: string;
  commentPayload: object;
  commentPayloadPath: string;
} {
  const resultPath = path.join(opts.runDir, "ui_execution_result.json");
  if (!fs.existsSync(resultPath)) {
    throw new Error(`ui_execution_result.json 不存在: ${resultPath}`);
  }

  const result: FlowResult = JSON.parse(fs.readFileSync(resultPath, "utf-8"));
  const markdown = buildMarkdown(result, opts);

  const mdPath = path.join(opts.runDir, "ui_report.md");
  fs.writeFileSync(mdPath, markdown, "utf-8");

  // Multica comment payload
  const commentPayload = {
    multica_issue_id: opts.issueId,
    workspace_id:     opts.workspaceId ?? "target-system-test",
    status:           result.status,
    comment: [
      `## UI 测试摘要`,
      `- 整体: **${statusBadge(result.status)}**`,
      `- ${result.passed_steps}/${result.total_steps} 步骤通过`,
    ].join("\n"),
    generated_at: new Date().toISOString(),
    artifact_links: [
      { type: "ui_report_md",  path: mdPath },
      { type: "trace",         path: path.join(opts.runDir, "trace.zip") },
      { type: "screenshots",   path: path.join(opts.runDir, "screenshots/") },
    ],
  };

  const commentPath = path.join(opts.runDir, "ui_multica_comment.json");
  fs.writeFileSync(commentPath, JSON.stringify(commentPayload, null, 2), "utf-8");

  console.log(`[ui-report] Markdown: ${mdPath}`);
  console.log(`[ui-report] Comment: ${commentPath}`);

  return {
    markdown,
    markdownPath:       mdPath,
    commentPayload,
    commentPayloadPath: commentPath,
  };
}
