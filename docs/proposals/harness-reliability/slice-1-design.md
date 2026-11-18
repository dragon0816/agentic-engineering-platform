# Reliability slice 1 — revalidated design

2026-11-18. User authorized implementation/testing on harness/reliability-141.
Baseline ad532e2db3acd04c11289145665a62353eddcc79 differs from the frozen review.
The reviewed cd19a5b statements must not be treated as current inventory.

## Revalidated requirements and red tests

CLI _ask already returns nonzero for failed capability/Workflow; no exit-code migration is needed now.
This baseline contains coding.run_python, a native conversation tool loop, model-backed coding and telemetry.
The previous claim that these are absent is obsolete for this branch.

After giving inert fixtures explicit existing policy grants, tests/test_harness_reliability.py has
7 expected failures and 2 passing controls: resident repair exhaustion is wrapped succeeded;
process exit 1, timeout and unknown outcome let the dependent sentinel run; Draft refusal is hidden;
capability timeout wording omits continuing-execution uncertainty; MCP is_error is invalid_input.
Successful process execution and intentional negative diagnostic data pass as controls.
No historical incident attribution is established.

## Smallest contract change

Keep CapabilityResult, Workflow/Skill schemas, installed handler protocol and permissions unchanged.
Add a host-runtime-only CapabilityTaskFailed exception, a specialized CapabilityRefused,
carrying a CLOSED failure code, the handler's existing typed output Contract and needs_input flag.
Bridge validates that output against the installed output model before retaining it in an existing
non-success CapabilityResult.data. Invalid carried output becomes invalid_output.
The public failure message stays generic; raw exception text is never exposed.
Semantic task failures remain non-retryable. All existing handler return paths stay compatible.

CodingHarnessHandler maps only non-validated CodingHarnessResult, preserving structured command failures
and needs_input. RunPythonHandler maps only its declared process contract: timed_out, exit None or
nonzero exit; original exit/output/files evidence is retained for existing consumers.
No generic JSON-key interpretation, output-schema replacement or retry is introduced.

Draft retains its intentionally informative output contract. Existing local UI/CLI show the known
Draft refusal code and refusal preview without dumping its echoed SOP/request. Telegram shows only
closed codes; no tool payload. All surfaces show capability failure codes and explicitly warn that a
Bridge-level timeout may leave work running. Executor-level timeout remains a distinct code.

MCP explicit tool errors use an existing closed CapabilityRefused code mcp_tool_failed, preserving
non-retryability and secrecy. Its discovery-only timeout is documented rather than silently applying
new retry/deadline semantics to remote operations.

## Test and verification sequence

Red composition tests -> explicit adapter mapping/Bridge typed handling -> focused suite ->
full pytest (shared runtime touched), ruff lint/format, mypy, build, pip check -> real scratch
restricted-runner check and synthetic gateway smoke when feasible.
Read existing BI-related regression results; do not edit BI implementation or real vaults.
No GitHub issue, PR, push/merge, running-host restart, firewall modification or architectural expansion.

Further work depends on these results. Artifact acceptance must reuse existing current-baseline
task/completion validation rather than adding the obsolete proposed verification engine.
A fresh correct Excel oracle and historical SOP inputs remain required before claiming the historical
task fixed. Unknown-effect ownership, durable host wiring and any unsupported containment change
remain separately scoped; no blind timeout replay.
