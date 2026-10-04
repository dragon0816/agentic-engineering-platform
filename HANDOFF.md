# Handoff

Date: 2026-10-04 (Asia/Taipei). Branch: main. Goal: build a six-layer Agent harness shared by Workflow/Task execution, Knowledge Asking and Coding. The owner wants Knowledge tested first in Agent Web with a Skill, while avoiding Knowledge-specific core logic.

## State and decisions

- Commit `680eb34` added a typed evidence-gap assessment for a product/market matrix cell. This is a Knowledge pilot, not the common harness. It passed focused matrix/Web tests, Ruff and touched-source mypy.
- The owner clarified that the common harness must cover all three domains. `docs/phases/HARNESS_6_LAYER_INCREMENTAL.md` now orders shared plan, bounded state loop, Knowledge-first vertical test, Workflow/Task and Coding adapters, cross-domain validation and Agent Web proof.
- G1 adds optional `SkillHarnessGuidance` to Skill manifests and a provider-neutral `AgentHarnessPlan` built from an existing TaskContract. Skill guidance can request evidence, context and fallback, but cannot add capability grants, remove Host completion checks or exceed the Task retry budget. The plan always ends in a validation stage.
- Three test Skill manifests cover Knowledge, Workflow and Coding. The Knowledge fixture is a validated 1.1.0 candidate for the main Knowledge Asking Skill; the published 1.0.0 Skill is untouched. The candidate owns the procedure; later adapter code should only map retrieval and Raw citations into common observations.
- Focused checks after G1: `pytest -q tests/test_agent_harness_plan.py tests/test_routing.py tests/test_gateway_task_execution.py` passed 44 tests; Ruff and mypy on touched code/tests passed; `git diff --check` passed. Full repository verification is deferred to the owner's merge checkpoint.

## Next work

1. Commit the clean G1 slice. Then build G2 as a bounded, serializable state machine over the shared plan: route, plan, context observations, execute, independent validation, and structured `needs_input`/failure. Add negative cases for all three domains before binding a live provider.
2. Use the candidate Knowledge Asking Skill in G3 to test exact installed Vault coverage, bounded retrieval, citations and independent answer validation in Agent Web. Diagnose each failure as routing, Skill planning, data coverage, retrieval, execution or validation. Do not treat co-mentions as market fit.
3. Bind existing exact Workflow/Task and Coding execution in G4 without replacing their deterministic logic or Bridge policy; finish cross-domain acceptance and Web proof.

## Operational context

The existing Agent Web on 127.0.0.1:53582 was started before these harness slices. Do not claim it is running G1/G2 until it is deliberately restarted at the Web-proof stage. The current local token is stored only in ignored owner-ACL-restricted `.scratch` startup output; do not print or commit it. `RS_Knowledge` is owner-approved public data. Do not ask the owner to reset the User-scope LiteLLM key merely because a separate shell process cannot see it.
