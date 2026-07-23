# Outputs Schema

workspace_id: target-system-test

每个 Mify 节点的输出必须符合本文档定义的 schema。

---

## context_package.json

```json
{
  "system": {
    "name": "string",
    "tech_stack": "string",
    "source_path": "string",
    "api_base_url_env": "string",
    "server_port": "integer",
    "context_path": "string"
  },
  "api_inventory": [
    {
      "path": "string",
      "method": "string",
      "description": "string",
      "readonly": "boolean",
      "idempotent": "boolean",
      "source_file": "string"
    }
  ],
  "test_scope": {
    "target_apis": ["string"],
    "target_ui_flows": ["string"],
    "excluded": ["string"],
    "p0_risks": ["string"]
  },
  "pending_confirmations": ["string"],
  "source_refs": ["string"]
}
```

---

## scope_analysis.json

```json
{
  "in_scope": [{"item": "string", "priority": "P0|P1|P2", "reason": "string"}],
  "out_of_scope": [{"item": "string", "reason": "string"}],
  "p0_risks": [{"risk": "string", "mitigation": "string"}],
  "p1_risks": [{"risk": "string", "mitigation": "string"}],
  "pending_confirmations": [{"item": "string", "owner": "string", "deadline": "string"}]
}
```

---

## test_cases.json

```json
{
  "cases": [
    {
      "id": "TC_001",
      "name": "string",
      "type": "api|ui|e2e",
      "priority": "P0|P1|P2",
      "readonly": "boolean",
      "source": "string",
      "given": ["string"],
      "when": ["string"],
      "then": ["string"],
      "pending_confirmations": ["string"]
    }
  ],
  "coverage_matrix": [
    {
      "scope_item": "string",
      "priority": "P0|P1|P2",
      "covered_by": ["TC_001"],
      "status": "covered|gap"
    }
  ]
}
```

---

## execution_plan.json

```json
{
  "has_api": "boolean",
  "has_ui": "boolean",
  "has_perf": "boolean",
  "api_batch": {
    "tool": "api_runner",
    "base_url_env": "string",
    "token_env": "string",
    "cases": ["string"]
  },
  "ui_batch": {
    "tool": "ui_runner",
    "ui_url_env": "string",
    "test_user_env": "string",
    "test_password_env": "string",
    "flows": ["string"]
  },
  "perf_batch": {
    "tool": "perf_probe",
    "target": "string",
    "samples": "integer"
  },
  "excluded": ["string"],
  "warnings": ["string"]
}
```

---

## defect_analysis.json

```json
{
  "summary": {
    "total_failed": "integer",
    "by_category": {
      "ENV": "integer",
      "DATA": "integer",
      "CASE": "integer",
      "PRODUCT": "integer",
      "TOOL": "integer",
      "UNKNOWN": "integer"
    }
  },
  "failures": [
    {
      "tc_id": "string",
      "category": "ENV|DATA|CASE|PRODUCT|TOOL|UNKNOWN",
      "evidence": "string",
      "suggestion": "string",
      "blocking": "boolean",
      "potential_bug": "boolean"
    }
  ]
}
```

---

## multica_comment_payload.json

```json
{
  "multica_issue_id": "string",
  "status": "passed|failed|blocked",
  "comment": "string",
  "artifact_links": [
    {"type": "string", "path": "string"}
  ]
}
```
