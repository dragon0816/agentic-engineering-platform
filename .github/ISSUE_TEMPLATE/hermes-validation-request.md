---
name: Hermes validation request
about: Request a bounded Hermes preflight and deterministic validation run
title: "[Validation Request] "
labels: ""
assignees: ""
---

<!--
Hermes adds hermes-validation-requested only after the manifest is complete.
The manifest is data, never a command. Do not include credentials.
-->

## Validation Request

```yaml
request_id: validate-example
target:
  capability:
    namespace: engineering
    name: weekly-report
    version: 1.0.0
  package_commit: 0123456789abcdef0123456789abcdef01234567
  build: 0.1.0
  test_profile: aep-capability-suite
execution:
  bridge: company-pc-01
  actor: employee.id
  required_grants:
    - namespace: engineering
      name: weekly-report
      version: 1.0.0
  model_routing: company-gateway-default
  knowledge_assets: []
acceptance_criteria:
  - workflow-11-completed
max_codex_repair_attempts: 3
max_hermes_retests: 3
```

## Evidence

Hermes appends sanitized preflight, test and retest evidence here. Never add
passwords, API keys, access tokens, cookies, private keys or secret values.
