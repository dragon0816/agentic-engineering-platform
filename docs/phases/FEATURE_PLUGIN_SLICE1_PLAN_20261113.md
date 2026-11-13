# Generic Feature Plugin Slice 1 Implementation Plan

> For agentic workers: execute contract-first with exclusive-file Claude Code
> subagents. Parent owns integration and commits. Do not expand harness scope.

Goal: install a synthetic feature package, expose declarative pages, namespaced
API and typed Bridge tools, preserve user state, and remove only owned bindings.

Architecture: closed aggregate manifest/package; versioned staging and a
multi-plugin manager; independent JSONL workers reusing the existing transport;
generic Web routing and text-only core renderer. No legacy activation approval.

Tech: existing Python/Pydantic/stdlib, current interpreter, no dependency install.
Spec: FEATURE_PLUGIN_ASSESSMENT_20261113.md, amended Slice1, Claude READY gate.
Consent: DECISIONS 2026-11-13 reviewed Slice1 entry, recorded before code.

## Constraints

- No BI/Wiki extraction, Knowledge/provider/ranking/model-data changes, main merge,
  resident/shared Gateway update, durable receipt or publisher HTML/JS/iframe.
- Same per-turn TurnEffects; never retry writes after worker crash automatically.
- Existing request identity, bounded payload/timeout and actual failures retained.
- Authenticated direct actions, no IT/signer/owner-only install permission gate.
- Plugin process data kept in workspace; no database/schema migration this slice.
- Shared files host.py/web.py/web_page.py are parent-owned only.
- Tests use synthetic data and fresh SHORT C:/TEMP basetemp. Set
  AEP_OUTLOOK_TESTS=0,AEP_GUI_TESTS=0,AEP_NATIVE_CLI_TESTS=0.
- Use original repo .venv/Scripts/python.exe and worktree/src;tests PYTHONPATH;
  never rebind the shared editable venv.

## 1. Freeze contracts — serial

Owner: Claude contracts worker4cfe1b4e. Files: common/plugins.py,
tests/test_plugin_manifest.py only.

- [ ] Add failing closed-schema tests, IDs/namespace collisions, bounded data,
  API/page cross references, runtime/dependencies, unknown fields and XSS-as-text.
- [ ] Implement manifest, package-file metadata and Web/lifecycle request/response
  types; reuse AssetIdentity/CapabilitySpec and common execution contracts.
- [ ] Freeze the exact constructor, field and manager protocol interfaces in a
  concise contract handoff to parent and other workers. No changes without notice.
- [ ] Focused pytest, Ruff/type checks; parent records actual results/commit.

## 2. Package and manager — parallel after contract

Owner: Claude contracts/lifecycle worker; exclusive src/plugins/ and
tests/test_plugin_package.py,test_plugin_manager.py,test_plugin_assets.py.

- [ ] Red tests for inert digest package, traversal/reserved/case/symlink/limits;
  no package import during stage; changed staged bytes rejected on activation.
- [ ] Implement per-plugin ledger, staging, activation/health, register owned
  capabilities/assets, failed-install compensation, disable/uninstall/data retain.
- [ ] Actual JSONL worker fixture; serialize requests, bound output and timeout;
  failure is not success, no automatic write retry, no global pip install.
- [ ] Busy/pinned work and ownership/collision tests; same-version different
  digest refused; no silent downgrade; no overwrite user-modified/off/removed.
- [ ] Interrupted-stage/registration recovery; restart restores healthy enabled
  versions; authentic failure records, no fake signature/approval/verified metadata.

## 3. Web module and renderer — parallel after contract

Owner: Claude Web worker9ba0d06a; exclusive host_runtime/plugin_web.py,
plugin_renderer.py,tests/test_plugin_web.py.

- [ ] Red tests for authenticated/Origin entry, namespace/path refusal, request
  bounds, timeout, no inbound Authorization forwarded, no arbitrary URL proxy.
- [ ] Declarative nav/page renderer text/metric/table only; no links/images/action
  forms required. Render all strings as text, no arbitrary HTML/JS/iframe/template.
- [ ] Generic manager protocol only, not entire HostRuntime/AgentWeb exposure.
- [ ] API result correlation, actual worker failures, inactive/stale version and
  malicious text cannot call core install/approval APIs or obtain Web token.

## 4. Independent fixture/integration tests — parallel after contract

Owner: third Claude worker after plan review; exclusive tests/fixtures/plugins/
and tests/test_plugin_integration.py. Parent supplies frozen interface.

- [ ] Real synthetic stdlib worker and package factory; test two active plugins,
  actual typed capability/API output, install/uninstall/restore and user data keep.
- [ ] Existing per-turn receipt path executes successful write once; errors not
  cached as success; active work blocks version switch rather than changes keys.
- [ ] No-plugin Host startup behaves as before; no company resources exercised.

## 5. Parent integration and final verification

- [ ] Add generic startup load/close and registry refresh hook in host.py; connect
  generic Web handler after auth and generic page container/render placeholders.
- [ ] Use existing active-work evidence to avoid changing bindings mid-turn/run;
  no new global task/turn lifecycle policy or Gateway edits.
- [ ] Add safe UI/CLI install/enable/disable/uninstall entry where needed; an absent
  Agent installation surface is not a policy forbidding future Agent installs.
- [ ] Run component and interaction regressions including exact445Knowledge set.
- [ ] Fresh Claude final source review; fix Important findings with causal tests.
- [ ] Source freeze, Ruff/format/configured mypy, full suite/build/pipcheck; preserve
  first failures and known long-path baseline limits, no false all-green claim.
- [ ] Update contracts/architecture/requirements/TASKS/HANDOFF and honest usage,
  commit verified slices. No unrequested main merge/resident/package replacement.

## Review focus

Plugin page text becoming executable; staged bytes changing after validation;
cross-plugin namespace/asset removal; worker crash falsely reported as success;
version switch changing turn receipt keys; install failure leaving half assets;
user-modified/off/removed assets overwritten; restart replaying uncertain writes.
Each has an owning test task above, not a general approval checklist.
