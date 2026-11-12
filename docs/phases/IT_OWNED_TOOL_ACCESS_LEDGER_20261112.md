# IT-owned tool access execution ledger

Base:394ca4d2ccb271a88d45bdaf3978a43f24079a58.
Branch:it-owned-tool-access-20261112.
Worktree:C:/Users/Chi_L/.paseo/worktrees/2qnenase/it-owned-tools-20261112.

Owner scoped harness approval,2026-11-12:
「同意上述 harness 範圍並開始實作」, replying to the four-scope question
recorded in the design and DECISIONS. No additional consent is needed for tasks
inside that stated scope; expansion still requires new consent.

Plan self-review: requirements mapped to8 tasks; internal Knowledge helper
contracts/model eligibility preserved; actual IT decisions never fabricated.
No implementation yet. No process is active. Next: Task1 red tests.

## Evidence and rulings

- New managed worktree wks_9e3f85169bdceb9b created from the design commit;
  original main/accepted package/resident are untouched. No editable install or
  dependency rebind is performed in the shared virtual environment.

## Task1 — environment execution

Red: corrected task1-red.log has35fail/1pass; calls were blocked by legacy
permission/approval checks and Outlook was absent. The initial test fixture
omitted required central_required; that first run is preserved separately and
is not the causal red proof. Correcting the fixture changed no assertion.
Green: task1-green.log/xml64passed5.47s; Ruff check/format passed, mypy runtime.py
passed. Updated old default-deny/review-as-admission assertions to the owner's
new contract, retaining real handler count/output/error/context checks.
LocalPolicy is a legacy-compatible identity facade; no fake IT grant/approval
is created. Unknown targets, bad arguments and real OS errors remain failures.
Global lint/type/full/build remain for final source freeze; this is a verified
slice, not whole-feature completion. No resident/config/install change.

Task2 red: isolated no-reference Outlook discovery fails as expected2.27s;
no COM/mail access occurred. Test is in test_it_tool_discovery.py, outside the
Task1 commit, ready for the registration slice.

Ruling: retain LocalPolicy's constructor/add/confirm_writes interfaces only as
compatibility metadata while migrating callers; no method may gate execution.
This avoids breaking integrations before their registration/install migration.

## Task2 — portable registration and local assets

Red: task2-red.log1failed proves missing Outlook; expanded discovery red2failed/
1passed proves Skill-gated BI/contacts and member-selected local assets.
Green: task2-affected.log/xml52passed22.22s, including zero-COM discovery,
no-reference data/Outlook/BI/contacts and local assets independent of legacy tool
selections. Ruff passed; host.py mypy passed. Registration Knowledge isolation
and pipeline host checks46passed25.86s. Full445/full build remain final gates.

Removed13 asset-usage guards/setup assignments from portable registration and
unused policy imports/helpers. Removed grant/profile-capability admission and
fake runtime grant synthesis; preserved authenticated device checks and existing
Knowledge selections/model data approval. Old grants can coexist or be malformed
without becoming startup permission input. Diagnostics report actual installed
assets. Existing assertions were updated only for the explicit changed policy;
foreign-device and invalid-asset/secret-redaction assertions remain.

Ruling: profile procedure selection still controls which instructions fit a
role, not common tool access. Internal Knowledge query helpers retain their
query/check contracts. Configured-only integration descriptors/setup statuses
belong to Task3's common catalog, not a second registry policy. The new system
command block is also Task3; Task2 covers existing portable built-ins.

Next: commit Task2 and implement Task3 common catalog/description/invocation.
No test/build process remains; no resident or shared configuration was touched.

## Task3 — common execution contracts (implementation in progress)

Added common paginated catalog, schema description and Bridge invocation tools
to Gateway, authoring MCP and assistant MCP. External authoring returns status
metadata only; its pre-existing model/data boundary remains. Known integrations
without handlers are shown as needs_setup, independently of permission metadata.
system/run-command runs argv under the OS account, preserves actual exit code,
bounded/redacted output and real timeout/start failures. Windows timeout cleanup
terminates the command tree because a venv launcher can leave child pipe handles.

Red/green: common alias tests initially exposed duplicate writes and incorrectly
memoized reads. Gateway now resolves the actual capability effect identity and
classification, shared across generic/Skill aliases. Corrected fixture errors
(Skill namespace and result field name) are not treated as causal evidence.
Legacy approval callback does not block execution; actual environment refusals
remain unrecorded and are tested on repeat. Pending Host outcomes retain their
existing separate regression coverage.

task3-green.log/xml:112passed10.70s, covering common tools, command, effects,
host discovery, dispatch/contracts and authoring/assistant adapters. Ruff passes;
focused source mypy7files passed before the final offered-descriptor addition.
Interim whole-tree mypy is still running; do not claim it passed. A legacy test
still accesses removed LocalPolicy._grants, to migrate in Task5 with its original
technical-refusal assertion preserved. Whole-feature verification is pending.

Ruling: binding-specific execution timeout is runtime metadata, not permission;
the command handler owns its requested timeout with a bounded cleanup margin.
CapabilitySpec accepts side-effect descriptions without fabricated approval refs;
shared publishing governance is separate and unchanged by this contract removal.

Task3 checkpoint:112 focused passed plus the migrated legacy-grant assertion
1passed; whole-tree mypy1101files passed, Ruff check/format src/tests passed.
This is not full-suite/build acceptance. The interim whole-tree mypy first found
one stale private-grant assertion; it now asserts no grant admission/no fake
approval, rather than reaching into a removed implementation dictionary.
Task4 red:4failed confirms agent MCP installation interface is absent; tests
are deliberately not included in the Task3 execution-contract commit.

## Task4 — agent MCP connection and live catalog

Agent ToolAccess.install_mcp saves through existing McpHub with background
connection disabled, then connects synchronously in a worker thread. Gateway,
assistant and authoring MCP expose this operation. Credentials stay environment
references. No approval record, synthetic grant or restart. Catalog/invoke read
the live registry, so the static generic tools work in the SAME bounded model
conversation after installation. Skill selection is not involved.

MCP replacement/disable/delete disconnects its stale bindings; current schema is
registered on reconnect. Explicit MCP isError now yields a failed execution with
typed diagnostics, rather than success. Direct MCP aliases declare their effect
and resolve the same capability identity. A reconnect cannot reset a successful
effect receipt for the same logical target/arguments within the turn.

Evidence: task4-red.log4failed (missing interface); task4-green.xml/log22passed;
task4-conversation.xml/log27passed; task4-final.xml/log34passed7.07s (including
single-conversation install/catalog/invoke, stdio+HTTP fixtures, schema refresh,
disable, invalid transport/executable, real MCP error, effect regressions).
Whole-tree mypy1102files passed; Ruff check/format passed before final HTTP test,
which was formatted/import-sorted. Final source freeze still owes full checks.
No real install/network/mail was used; HTTP fixture listens only on loopback.

Next Task5: direct local asset install with honest unverified quality/provenance,
no approval cards; preserve central publishing rules and historical cards.

## Task5 — direct local asset installation and truthful receipts

Normal Gateway/authoring MCP run/install paths execute directly. Added Gateway
Skill draft/install tools and live procedure refresh. Local installations retain
pending business review, actual candidate/digest provenance and draft/validated
quality; an Install press or reference string is not business acceptance. No new
grant file or approval card. Old explicit request/decision APIs remain readable
and tested as history; no pending historical action is automatically decided.
Contract/dependency/name/version checks remain; unverified quality is visible,
not fabricated and not a local-install admission gate. Completion/coverage still
requires actual verification; dropping pagination is never verified by installing.

New direct execution exposed two real duplication gaps. Added run receipts shared
with Gateway (installation metadata does not repeat the procedure), plus Bridge
success-only normalized capability receipts shared across wrappers of the same
registry. Actual handler invocation is false on replay, warnings identify it;
failures/read calls are not memoized. Shared registry write lock protects receipt
check/execution/record across Bridge wrappers. No caller may reset a successful
receipt by reconnecting or installing in the same turn.

Evidence: task5-red4failed (missing direct semantics), live Skill refresh red,
repeat-run and generic-then-Workflow-write reds (actual duplicate handler calls),
invented-review-reference red (false approved metadata). New local tests passed;
task5-final.xml/log435passed133.90s across authoring/repair/input continuity/
pagination/preflight/history/revision/Knowledge isolation/effects/dispatch.
That broad run preceded the final metadata tightening; final provenance/related
tests task5-review-provenance.xml/log50passed33.17s. Earlier diagnostic run had
7 stale policy expectations/428passed; migrated only approval-as-admission
assertions, preserving stronger input, original-file, coverage and no-egress
checks. That diagnostic overlapped later edits and is not final acceptance.
Task5 focused mypy541files and Ruff passed before final metadata tightening;
final whole-feature static/full/build checks remain mandatory in Task8.

Task6 red (uncommitted test_it_tool_boundaries.py):4fail confirms legacy folder/
sender/date hiding, missing body continuation metadata, mode switches/cards and
generic file folder restriction. This red file is excluded from the Task5 commit.


## Task6 in progress — mailbox/native execution and cross-endpoint receipts

Uncommitted implementation removes application mail folder/sender/date admission,
read cards and native backend switches/permission relays; adds bounded mail body
continuations and explicit send-draft capability. Draft remains draft. Production
legacy mail aliases use the same Bridge target/turn receipts. Native HTTP turn
tokens now scope assistant and authoring endpoints to one TurnEffects record;
a loopback cross-endpoint test proves one handler invocation and token expiry.
No external provider guards/settings are bypassed. Codex uses native HTTP MCP
config with bearer token references in child environment, never token argv.
Model/data-routing requirements are unchanged.

General commands/Python validation use actual IT/OS identity. The EnvironmentRunner
shares typed subprocess execution with command capability, retains timeout,
redacted bounded output, real exit statuses and fresh-artifact evidence. Purpose-
specific coding/change writable/test contracts and Knowledge helper isolation
remain. Default Python execution no longer needs host coding roots, low-token
setup or a firewall rule. Desktop/browser output paths accept absolute accessible
paths; overwrite intent and actual path kinds remain validated.

Actual checks so far: task6-mail-native.xml85passed/1failed/2deselected34.70s;
sole remaining failure was new test importing SPEC as SEND_SPEC, corrected.
Initial Python adapter9failures/20passed exposed CRLF output and killed-process
exit compatibility; normalized text newlines and preserved timeout exit=None at
the Python adapter, without weakening failed-run/output JSON assertions. The
85pass run includes those corrected Python tests. task6-boundaries.xml17passed
5.38s includes direct preflight without cards or false verification and replay.
task6-mcp-lifecycle.xml22passed25.92s. New EOF/log redaction test first failed
because close killed the launcher without reaching child EOF; fixed by EOF-first
shutdown, owned-tree fallback and redacted stderr drain. No real mailbox/send.
Static review found native Knowledge read steps could be memoized by the new
wrapper; corrected classification and added fresh-read regression before final
verification. Final whole-tree lint/type/full/build are still pending.

Old decision/request APIs remain explicit compatibility paths. Preflight's old
request builder is private and tested as historical behavior; the normal model
tool directly returns the actual Bridge result. No historical pending cards are
auto-approved or replayed. Broad affected test run is in progress; no full suite,
build, resident deployment, push or shared Gateway change has occurred.


## Task6/7 focused acceptance and current verification boundary

Latest focused checks: task6-final-focused.xml118passed61.74s; task6-tail.xml
61passed/2live-Outlook-skipped84.50s. These cover direct read/draft/send, native
fake adapters, actual local Python, legacy SOP install, real trial-input reuse,
normal direct browser preflight, old-card compatibility and MCP connect/cleanup.
The updated one-conversation fixture now discovers/uses an existing validator,
installs a missing MCP fixture, discovers it and invokes it in the SAME turn:
five actual successful tool calls, one existing handler call, no approval files.
Earlier task6-affected3 had187passed/3failed/3skipped121.72s; those3 required old
approval records for actual input continuity. They now assert the same QA values
are replayed from actual trial history independently of removed/foreign/stale
legacy cards, and are included in the latest118passing focused tests. Stronger
same-actor/session/digest/run-history conflict checks remain unchanged.

Legacy SOP Studio had an additional preview-as-install-admission/fake-review
path. A new red proved direct installation was refused. It now accepts a valid
local draft, never fabricates business review or a successful full trial from a
preview, writes no grant, and the authenticated Web endpoint refreshes the live
workflow registry. Invalid/missing draft, missing capability and version conflict
remain real failures. The changed draft cannot inherit old preview evidence.
This is within the approved local-install scope, not new shared publishing policy.

Ruff check and format check passed (1158 files). Whole-tree mypy passed1112files
before the final small legacy-Studio/comment/test edits; final freeze recheck is
mandatory. Real native-provider tests now opt in with AEP_NATIVE_CLI_TESTS=1,
analogous to existing live Outlook/GUI checks: inheriting IT environment must not
silently use a developer's live credentials in routine tests. Fake CLI/ACP/MCP
protocol/error/data-policy assertions remain and have run. Actual provider help
was inspected read-only; no live provider model prompt, mailbox/send or C4C run.

Task7 Knowledge: exact baseline445 node IDs executed,445passed162.21s,0skipped.
knowledge-comparison.json proves identical445 identities AND outcomes, not merely
a count. Initial runner hit Windows argv length before pytest started; switched
to pytest.main in one Python process with the same exact node IDs (no dropped
cases). Raw log/JUnit retained. This measures deterministic regressions, not all
possible live model answers. Final frozen full-suite must compare the same445
again. No query ranking/evidence/model-data eligibility implementation was edited.
Knowledge helper scope and shared publication remain purpose-specific contracts.

Updated application Settings copy, backend tool exposure, MCP tool descriptions,
creator/Knowledge guides and AGENTS/CLAUDE/requirements/architecture/contracts to
avoid instructions to wait for removed local approval gates. AGENTS22, IT/OS
permissions, actual outcomes, dry-run intent and model/data policy remain intact.
No resident, delivered package, shared Gateway, remote branch or main changes.
Task8 whole-branch independent review, frozen full suite, build and pipcheck are
still pending. This is NOT final feature completion or deployment acceptance.
