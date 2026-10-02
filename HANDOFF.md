# Handoff

Date: 2026-10-02 (Asia/Taipei)
Branch: main. This is a local source change; no push or preview installation was performed.

## Current objective and scope

The owner approved continuing beyond the completed Phase 0 audit to the next executable Agent/Orchestrator checkpoint, then validating it. The approved sequence and data policy remain in docs/MULTI_BACKEND_ORCHESTRATOR_PHASE0.md, docs/MULTI_BACKEND_ORCHESTRATOR_JEV_PLAN.md and docs/DECISIONS.md. This checkpoint is an explicit Gateway task run through the Host CLI. It does not replace ordinary Agent Web chat or Workflow launching.

## Completed

- Added an optional exact tool-name allowlist and one-to-five-turn bound to Gateway conversation requests. An explicit empty allowlist exposes no tools. Both model-visible tools and Gateway dispatch bindings are filtered; the default ordinary conversation catalog is unchanged.
- Added GatewayTaskExecutor and LocalAgent.run_task. Local actor/device admission runs first. The task executor checks supported TaskContract shape and installed read-only capability scope, then requires the exact host-approved Gateway for UNCLASSIFIED context. ApprovedModelClient remains the final policy check on every complete provider request. There is no native-backend fallback.
- Added aep-host run-task --config <host.json> --prompt <question> for a text-only task and --task <task.json> for an explicit TaskContract. A validated answer is written to the Host workspace's task-artifacts directory.
- Persisted append-only completed steps, unresolved requirements and error codes in TaskRunState. No objective, answer bytes or model reasoning are stored in the SQLite run record. Host-owned CompletionValidator rereads actual answer bytes before a task can become validated.
- Updated docs/ARCHITECTURE.md, docs/REQUIREMENTS.md, docs/ROADMAP.md, docs/DECISIONS.md and docs/TASKS.md. The slice design is docs/ORCHESTRATOR_GATEWAY_TASK_SLICE.md.

## Verification

- Full local selection: 1,560 passed, 4 skipped, 2 existing machine-specific tests deselected. Command: PYTHONUTF8=1; .\.venv\Scripts\python.exe -m pytest tests --ignore=tests/test_browser.py -q -p no:cacheprovider --basetemp .scratch/pytest-task-exec-full -k 'not test_capability_workspace_is_interactive_in_a_real_browser and not test_a_machine_with_the_bridge_and_no_excel_says_which'.
- Ruff passed on src and tests; mypy passed on 288 source files.
- Offline sdist and wheel build passed under .scratch/dist-gateway-task-20261002; both new runtime modules were included. The run-task CLI help loaded successfully.
- Focused tests verify admission and policy refusal before model calls, read-only scope, no hidden Workflow execution, tool-progress evidence, restart persistence, artifact validation failure and ordinary conversation compatibility.
- No live LiteLLM request was made: this shell does not have LITELLM_MASTER_KEY in the Agent process environment. The installed Windows preview was not upgraded with this source build.

## Remaining work and risks

- The runnable checkpoint is CLI-only. Connect ordinary Agent Web ingress to the same task-state and completion path without changing deterministic slash-command or Workflow routes. Native Codex/Claude task adapters still need containment and complete-context policy tests.
- Backend switching remains disabled. Before a transition, inventory every transferred material and re-authorize the complete context for the destination; a task's declared classification is not sufficient.
- The first validator proves artifact presence, non-empty bytes or a specified digest. It does not prove factual or domain correctness.
- The task executor supports one answer output and installed read-only capability commands; resource references, arbitrary workspace access, write tools and Workflow commands are intentionally outside this slice. Existing Bridge grants still decide every attempted read capability.
- Workflow migration, static/runtime parameter UI, Marketplace defaults, SOP-to-Workflow, Knowledge and Skill integration evidence remain in docs/TASKS.md. The optional JEV adapter remains disabled pending egress authorization and a golden benchmark.
- A local operator can validate the new path after installing this build and starting an Agent process with LITELLM_MASTER_KEY: aep-host run-task --config <host.json> --prompt "What can you do?" The configured Gateway must retain the owner-approved exact company route at http://127.0.0.1:4000/v1.

## Recommended next steps

1. Review the CLI task run and durable state on the test host with a real Gateway credential.
2. Connect the ordinary Ask page to a task-state path only for suitable natural-language turns, preserving slash/Workflow semantics and admission.
3. Implement full-context transition authorization before any native task backend, then migrate and validate the pinned source Workflows.
