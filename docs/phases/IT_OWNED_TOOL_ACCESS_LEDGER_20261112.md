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
