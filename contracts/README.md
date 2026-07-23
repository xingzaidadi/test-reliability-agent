# contracts/ — 说明

本目录是 **target-system 系统的具体部署配置**，workspace_id 和环境变量名有意绑定该系统。

这是正确的设计：contracts 是"某套系统的合约实例"，mify/prompts 才是"通用能力层"。

---

## 接入新系统时

**不要修改本目录**，而是：
1. 复制本目录到 `contracts-{新系统名}/`（如 `contracts-isc-procurement/`）
2. 把所有 `target-system-test` 替换为新系统的 workspace_id
3. 把所有 `TARGET_SYSTEM_*` 替换为新系统的环境变量名
4. 把 `mify/workflows/super_test_agent_v1.yaml` 的 required_context 传入新参数

mify/prompts 和 mify/workflows 无需修改，它们通过 {{变量名}} 自动适配。

---

## 文件说明

| 文件 | 说明 |
|---|---|
| multica_workspace.yaml | workspace 定义，workspace_id = target-system-test |
| test_squad.yaml | 9个测试 Agent 的职责定义 |
| agent_registry.yaml | 每个 Agent 的输入/输出/env 变量 |
| skill_registry.yaml | VAF/VCB/API/UI/report 能力注册 |
| runtime_capability.yaml | 允许/禁止动作边界 |
| autopilot_patrol.yaml | daily_smoke 巡检配置 |
| issue_lifecycle.md | Multica issue 状态流转定义 |
| artifact_contract.md | artifact_index.json 字段标准 |
| outputs_schema.md | 所有节点输出 schema |
