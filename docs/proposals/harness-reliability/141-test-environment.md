# 141 isolated Harness test environment

Date: 2026-11-18. Status: branch and isolated model-test environment ready; no Harness implementation started.

## Workspace and baseline

- Machine: OpenLab01, Ethernet 172.25.228.141.
- Branch: harness/reliability-141.
- Worktree: C:/Users/OpenLab/Documents/workspace/aep-harness-reliability-141.
- Base: local main ad532e2db3acd04c11289145665a62353eddcc79 from C:/Users/OpenLab/Documents/Codex/2026-11-04/task/aep-inspect.
- This is a different baseline from the earlier independent review at cd19a5b055b0caf635ecb07d3e3b086f3c4560b0. Old findings must be revalidated before implementation.
- Own Python environment: .venv. No existing BI environment, runtime, host.json, vault, database or running service was modified.
- No source/runtime fixes, new host service, GitHub issues, commits, pushes, PRs or merges.

## Gateway verification

- API root: http://172.25.228.59:4000/v1.
- Model: gpt-5.6.
- Credentials: supplied through a private secret card; not included in report, JSON configuration, source, or Git.
- Raw authenticated models request: HTTP 200, 11 models, gpt-5.6 listed.
- Raw minimal chat completion: HTTP 200, exact OK reply.
- Actual AEP ModelBinding -> ModelClients -> OpenAICompatible.generate smoke: exact OK with no Failure.
- The initial adapter run used the prior existing interpreter to read this worktree's source and passed in 2172 ms.
- After creating the dedicated .venv, one adapter call returned model_http_error after 7875 ms; its status/body was not recorded, so cause and retryability are unknown. A single manual retry succeeded in 1484 ms. No automatic retry code was added.
- Therefore connectivity and basic adapter use are confirmed; continuous reliability, streaming, tool calling, structured output, real BI tasks and production host routing are not established by these checks.

## Isolated test configuration and commands

The ignored .scratch/gateway-models.json contains a non-secret ModelBinding fragment plus credential-name mapping. It is not a complete host.json and does not activate a running host. It declares only conservative basic capabilities. Existing host data-approval/authorization requirements remain unchanged; no approval record was fabricated.

The ignored .scratch/gateway-smoke.py imports this worktree's src, validates ModelBinding, resolves the key from AEP_GATEWAY_59_KEY (or an explicitly supplied private secret file), submits only the synthetic prompt Reply exactly OK, and exits nonzero on failure. It does not read BI content, mutate any vault or print credential values. max_tokens_field is configured as max_completion_tokens.

From this worktree, with the key provided to the process through an approved secret mechanism:

```powershell
.\.venv\Scripts\python.exe -B .scratch\gateway-smoke.py
```

Do not copy a credential into the command line, Git files, or this report. The private card's file path is deliberately not persisted here.

## Offline model regression result

Initial attempt using the older shared interpreter failed during collection because tzdata was absent; no test pass was claimed for that attempt. Created this worktree's own .venv and installed the local editable package plus pytest. This installs dependencies into the new environment, not a Harness framework.

Dedicated environment:
- Python 3.12.14
- pydantic 2.14.3
- pytest 9.2.0
- tzdata 2026.6

Exact successful command (PYTHONDONTWRITEBYTECODE=1):

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/test_openai_compatible.py tests/test_clients.py tests/test_catalog.py tests/test_host_models.py tests/test_models_proof.py -q -p no:cacheprovider --basetemp .scratch\pytest-gateway-isolated
```

Result: **69 passed in 3.42 seconds**. These use fixture/fake model transports, not live BI data. No full suite, lint/type check, build or end-to-end reliability benchmark was run. Live smoke is a separate check.

## Isolation and next action

.venv and .scratch are ignored by existing repository rules. Scratch/configuration and test output belong only to this worktree. The old AEP main checkout and the separate personal-proof checkout stayed clean on their original branches.

This is the original setup snapshot. The owner subsequently authorized implementation/testing and selected existing-state operation ownership. Follow slice-1-results.md, slice-2-results.md and controlled-excel-benchmark.md for current results. The setup itself did not approve a verification DSL, new framework or containment redesign.


## Owner restriction: no Telegram on 141 reliability tests (2026-11-19)

The owner reports interference with daily Telegram work. All reliability tests on
141 must leave Telegram disabled: use synthetic/local workspaces, never copy the
daily host's telegram.json, never run the telegram poller, and never invoke
build_runtime/web against the daily host configuration for a test. If a future
isolated host fixture includes a Telegram config, disable it using the existing
telegram.disabled.json mechanism before launch. Never clear global/user tokens
or alter another host/bot's configuration.

Inspection found no telegram.json in this reliability worktree, coordinator root
or the installed preview host workspace, and no running reliability benchmark.
The benchmark builds only browser/Python/export tools and does not build Telegram.
It now explicitly removes TELEGRAM_* and AEP_TELEGRAM_* variables from its own
process before setup, so child tools cannot inherit these daily bot settings.
This does not modify persistent Windows environment, existing services or any
other process. The original SAP review ZIP remains frozen; this change applies
to future test runs and is recorded separately in Git.
