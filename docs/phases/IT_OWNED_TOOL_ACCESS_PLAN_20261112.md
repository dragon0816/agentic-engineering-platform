# IT-owned Tool Access Implementation Plan

> For agentic workers: use superpowers:executing-plans task by task in this
> isolated worktree. Steps use checkboxes; record red/green evidence and rulings
> in IT_OWNED_TOOL_ACCESS_LEDGER_20261112.md. One whole-branch review at completion.

Goal: every AEP Agent can discover/use/install tools executable under the actual
IT-managed environment, without AEP tool permission or installation approvals.

Architecture: keep typed Bridge execution as the common execution plane and use
the existing MCP manager for dynamic tools. Remove application permission gates,
not identity, truthful outcomes, evidence, at-most-once execution or Knowledge
query contracts. Skills guide tool use; they are not tool admission policy.

Tech stack: existing Python/Pydantic, Bridge, Gateway and stdio/HTTP MCP; no new
third-party dependency. Spec: IT_OWNED_TOOL_ACCESS_DESIGN_20261112.md.

## Global constraints and review focus

- Owner explicitly approved the four concrete harness scopes on2026-11-12.
- Worktree: it-owned-tools-20261112; original resident/package/main stay untouched.
- Use original repo .venv/Scripts/python.exe with this worktree src on PYTHONPATH.
- Do not change model/data policy, pretend IT approved, or forge approval refs.
- Do not weaken Knowledge tests or treat internal query/check helpers as general
  Agent tool ACLs. Preserve the same445 Knowledge baseline case identities.
- Critical inputs: unknown/unconfigured tool, stale install/version, duplicated
  effect after retry, real OS/provider refusal, native adapter lacking protocol.
  Each is explicitly tested in its owning task below.

## Task1: direct environment execution without tool grants

Files: capabilities/runtime.py, workflow/dispatch.py; tests/test_it_owned_tools.py,
test_dispatch.py, test_owner_policy.py and affected approval-contract tests.
Interfaces: retain LocalPolicy.authorize(context,spec)->ExecutionAuthorization
as a compatibility adapter and confirmation_needed(spec,origin)->bool. Do not
manufacture grants/approval records. Unknown targets still fail before execution.

- [x] Red: no-grant read/write/execute/external-side-effect reaches its recording
  handler once; old mismatched/missing grants cannot deny it; OS refusal remains
  failure; malformed arguments and unknown target never call a handler.
- [x] Green: remove application grant/approval admission, preserve real Bridge
  errors/validation/context and effect receipts.
- [x] Update old policy expectations to the new explicit owner contract, retaining
  stronger handler/output/failure assertions; run affected dispatch/owner suites.
- [x] Record and commit the coherent execution-contract slice.

## Task2: built-ins available without a referencing asset

Files: host_runtime/host.py and relevant lazy capability registration helpers;
tests/test_it_owned_tools.py and test_host_wiring.py.
Interfaces: existing InstalledCapabilities.discover/get/register; no COM access
or source-service call during discovery. Missing configuration is truthful setup
status, never an invented permission denial.

- [x] Red: clean profile/no reference discovers Outlook search/read/draft and
  available data/Excel/system blocks; zero mailbox/COM calls during construction.
- [x] Green: remove asset-usage registration gates; defer external dependencies
  until invocation. Preserve real integration configuration errors.
- [x] Run host wiring and external authoring catalog/Skill-binding regressions;
  record and commit the registration slice.

## Task3: common discover/describe/invoke and operating-system commands

Files: new host_runtime/tool_access.py; new capabilities/system_command/handlers.py;
host_runtime/host.py, mcp_server.py/assistant tools; tests/test_tool_access.py.
Interfaces: ToolAccess.catalog(query="",cursor=0,limit=40), describe(target),
invoke(context,target,arguments); each returns existing JSON/HostToolOutcome
contracts. CommandRequest carries argv,cwd,timeout; CommandResult preserves the
actual exit code/output. Execute through Bridge as system/run-command@1.0.0.

- [x] Red: all installed tool identities remain searchable/pageable; description
  gives real schema; invocation without selected Skill works and preserves actual
  failure. Same effect through a different alias/retry executes at most once.
- [x] Red: local fictional command succeeds, nonzero exit/timeout/OS-denied do
  not become success; no AEP folder/command permission prompt is created.
- [x] Green: implement common tools with real side-effect classification, reuse
  Bridge execution/turn effect records; no shell interpolation or command allowlist.
- [x] Verify Gateway/MCP expose the same underlying targets; commit this slice.

## Task4: agent installation and live MCP connection

Files: tool_access.py, mcp_servers.py, host.py and MCP wrappers;
tests/test_tool_access.py, test_mcp_servers.py and local fixture server tests.
Interfaces: ToolAccess.install_mcp(context,config) calls existing
McpHub.save(config,secrets) and connect(name), with IT-provided credential
references. Existing command capability installs other tooling under OS identity.

- [x] Red: agent connects a local fixture server with no approval, finds/calls its
  tool in the same conversation; install command executes once. Missing executable,
  authentication, package error, stale version and unsupported transport are real
  structured failures. No fake IT/owner approval is persisted.
- [x] Green: expose normal installation/connection and refreshed catalog, using
  actual existing manager return/status contracts; record any interface ruling.
- [x] Verify stdio and HTTP fixtures, no restart/no external network; commit.

## Task5: local Skill/Workflow installs without approval cards

Files: chat_authoring.py, external_authoring.py, mcp_server.py, asset metadata;
tests/test_external_authoring.py, draft/install and live-refresh fixture tests.
Interfaces: retain normal check/submit/install APIs; install directly with honest
local provenance and separate unverified quality status, not a forged review.

- [x] Red: valid local asset installs and is available to the same session with
  zero pending approval; broken schema/dependency/version conflicts fail honestly.
  Historical pending cards are not approved/replayed or silently counted as done.
- [x] Green: remove local installation/business-review gates; preserve actual
  verification evidence, ownership/version and shared publishing distinction.
- [x] Run authoring/install/continuation/idempotence regressions; commit.

## Task6: mailbox and native execution without AEP permission boundaries

Files: integrations/outlook_mail.py, capabilities/mail_read/handlers.py,
agent_mail.py, agent_mode.py/settings, conversation_backends.py; relevant tests.
Interfaces: existing read/search use IT-accessible messages; legacy scope fields
are at most ordinary query defaults, never deny filters. Draft remains draft;
send invokes the existing sender through a normal callable contract.

- [x] Red: fake mailbox outside old folder/date/exclusion ceiling is readable;
  requested query filters still work. Requested draft sends0; send calls1 without
  a card. Long/cut mail results are identified, not complete-thread claims.
- [x] Red: CLI tool exposure is not gated by Agent-mode flags/approval relay;
  AEP adds no command/folder deny rules; actual unsupported provider reports its
  limitation. External guards are never bypassed by this coding agent.
- [x] Green: remove AEP-added gates, retain actual authentication/OS errors and
  unchanged model/data eligibility; update UI/Skill text to the new contract.
- [x] Run mail/native adapter tests using fakes, no real mailbox/send; commit.

## Task7: Knowledge and integrated user-flow acceptance

Files: regression tests for generic discovery/effects plus existing Knowledge
and novice-flow fixtures; docs/CONTRACTS/ARCHITECTURE/REQUIREMENTS and AGENTS/CLAUDE
alignment only for the approved application-tool policy.

- [x] Prove ordinary Knowledge questions still retrieve/cite sources without
  writes; preserve query/helper isolation, citations, artifacts and route rules.
- [x] Compare the same445 baseline Knowledge cases, outcome IDs and failures.
  Baseline source is e69371e6; pre-change code at394ca4d2 is identical apart from
  documents, so existing recorded baseline/full proofs may be reused after Git
  object equivalence verification instead of repeating an unchanged full suite.
- [x] User-flow fixture: one prompt discovers an existing tool, installs a missing
  fixture tool, uses both and returns real output with no AEP approval cards.
- [x] Update obsolete approval-specific expectations with explicit new behavioral
  assertions; preserve all unrelated guarantees. Commit regression/docs slice.

## Task8: final verification, review and handoff

- [ ] Source-freeze once; Ruff check/format, mypy, focused checks then full pytest,
  build/pipcheck. Record first results and real failures; no repeated full suite
  without changes/failures. Do not build concurrently with full pytest.
- [ ] Whole-branch fresh review after implementation; fix substantive findings
  with red/green checks. A final reviewer may be used as required by execution
  Skill; no per-task delegation is needed.
- [ ] Update TASKS/HANDOFF/DECISIONS and acceptance evidence. Do not update the
  resident during active work, touch shared Gateway settings or silently replace
  the previous accepted package. Final packaging/deployment follows actual
  acceptance and the appropriate explicit owner delivery instruction.
