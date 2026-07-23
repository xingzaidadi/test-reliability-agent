/**
 * actions/registry.ts — Track J
 * Action 注册表：定义平台可用的 Action 类型及其元信息。
 * 新增 Action 时在此处注册，flow-runner 会自动识别。
 */

import type { ActionType } from "../engine/types";

export interface ActionMeta {
  type: ActionType;
  description: string;
  requiredFields: string[];
  optionalFields: string[];
  /** readonly profile 下是否允许执行 */
  allowInReadonly: boolean;
  /** 是否可能触发不可逆操作 */
  dangerous: boolean;
}

const ACTION_REGISTRY: ActionMeta[] = [
  {
    type: "navigate",
    description: "导航到 URL",
    requiredFields: ["url"],
    optionalFields: ["timeout"],
    allowInReadonly: true,
    dangerous: false,
  },
  {
    type: "click",
    description: "点击元素",
    requiredFields: ["selector"],
    optionalFields: ["timeout"],
    allowInReadonly: true,   // readonly profile 中会检查危险文本后决定
    dangerous: false,        // 由 flow-runner 运行时判断
  },
  {
    type: "type",
    description: "在输入框中填写文本",
    requiredFields: ["selector", "value"],
    optionalFields: ["timeout"],
    allowInReadonly: true,
    dangerous: false,
  },
  {
    type: "select",
    description: "选择下拉框选项",
    requiredFields: ["selector", "value"],
    optionalFields: ["timeout"],
    allowInReadonly: true,
    dangerous: false,
  },
  {
    type: "wait",
    description: "等待固定毫秒数",
    requiredFields: ["timeout"],
    optionalFields: [],
    allowInReadonly: true,
    dangerous: false,
  },
  {
    type: "wait_for_selector",
    description: "等待元素出现",
    requiredFields: ["selector"],
    optionalFields: ["timeout"],
    allowInReadonly: true,
    dangerous: false,
  },
  {
    type: "wait_for_network_idle",
    description: "等待网络空闲",
    requiredFields: [],
    optionalFields: ["timeout"],
    allowInReadonly: true,
    dangerous: false,
  },
  {
    type: "assert_text",
    description: "断言元素文本内容",
    requiredFields: ["selector"],
    optionalFields: ["timeout", "assertions"],
    allowInReadonly: true,
    dangerous: false,
  },
  {
    type: "assert_visible",
    description: "断言元素可见",
    requiredFields: ["selector"],
    optionalFields: ["timeout"],
    allowInReadonly: true,
    dangerous: false,
  },
  {
    type: "assert_url",
    description: "断言当前 URL",
    requiredFields: [],
    optionalFields: ["assertions"],
    allowInReadonly: true,
    dangerous: false,
  },
  {
    type: "screenshot",
    description: "主动截图",
    requiredFields: [],
    optionalFields: ["screenshot"],
    allowInReadonly: true,
    dangerous: false,
  },
  {
    type: "scroll",
    description: "滚动元素到视图",
    requiredFields: [],
    optionalFields: ["selector"],
    allowInReadonly: true,
    dangerous: false,
  },
  {
    type: "hover",
    description: "悬停在元素上",
    requiredFields: ["selector"],
    optionalFields: ["timeout"],
    allowInReadonly: true,
    dangerous: false,
  },
  {
    type: "press_key",
    description: "按下键盘按键",
    requiredFields: ["value"],
    optionalFields: [],
    allowInReadonly: true,
    dangerous: false,
  },
  {
    type: "upload_file",
    description: "上传文件",
    requiredFields: ["selector", "value"],
    optionalFields: [],
    allowInReadonly: false,
    dangerous: true,
  },
  {
    type: "custom",
    description: "自定义 Adapter 扩展 Action",
    requiredFields: [],
    optionalFields: [],
    allowInReadonly: false,
    dangerous: true,
  },
];

const _registryMap = new Map<string, ActionMeta>(
  ACTION_REGISTRY.map((a) => [a.type, a]),
);

export function getAction(type: string): ActionMeta | undefined {
  return _registryMap.get(type);
}

export function listActions(): ActionMeta[] {
  return [...ACTION_REGISTRY];
}

export function isAllowedInReadonly(type: string): boolean {
  return _registryMap.get(type)?.allowInReadonly ?? false;
}
