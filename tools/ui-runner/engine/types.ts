/**
 * types.ts — Track J (sap-playwright-agent engine)
 * 通用 Flow 类型定义，不绑定 SAP 特定系统。
 */

export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";

export type ActionType =
  | "navigate"
  | "click"
  | "type"
  | "select"
  | "wait"
  | "wait_for_selector"
  | "wait_for_network_idle"
  | "assert_text"
  | "assert_visible"
  | "assert_url"
  | "screenshot"
  | "scroll"
  | "hover"
  | "press_key"
  | "upload_file"
  | "custom";

export interface Assertion {
  type: "text" | "visible" | "url" | "attribute" | "count";
  selector?: string;
  expected?: string | number | boolean;
  contains?: boolean;
}

export interface FlowStep {
  step_id: string;
  name: string;
  action: ActionType;
  /** CSS / XPath selector or locator expression */
  selector?: string;
  /** For navigate: full URL */
  url?: string;
  /** For type/select: value to input */
  value?: string;
  /** For wait: milliseconds */
  timeout?: number;
  assertions?: Assertion[];
  /** Screenshot filename (auto-generated if omitted) */
  screenshot?: string;
  /** Skip this step if true */
  skip?: boolean;
  /** Human-readable comment */
  note?: string;
}

export interface FlowConfig {
  name: string;
  description?: string;
  /** Adapter identifier: generic-web | sap-webdynpro | internal-system */
  adapter?: string;
  /** Viewport dimensions */
  viewport?: { width: number; height: number };
  /** Headless mode */
  headless?: boolean;
  /** Storage state path for SSO session reuse */
  storage_state?: string;
  /** Safety profile: readonly | interactive */
  profile?: "readonly" | "interactive";
  steps: FlowStep[];
}

export interface StepResult {
  step_id: string;
  name: string;
  action: ActionType;
  status: "passed" | "failed" | "skipped";
  duration_ms: number;
  screenshot?: string;
  error?: string;
  assertions?: Array<{ passed: boolean; detail: string }>;
}

export interface FlowResult {
  flow_name: string;
  issue_id: string;
  executed_at: string;
  status: "passed" | "failed" | "blocked";
  total_steps: number;
  passed_steps: number;
  failed_steps: number;
  steps: StepResult[];
  trace_path?: string;
  error?: string;
}

export interface AdapterContext {
  name: string;
  base_url: string;
  credentials?: {
    username?: string;
    password?: string;
  };
}
