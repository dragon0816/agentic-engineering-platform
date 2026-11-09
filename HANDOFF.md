# Resident SOP-to-Workflow autonomy diagnosis — 2026-11-09

## Current task and scope

Owner asks why AEP itself cannot autonomously build the Sales Order Workflow,
and why it sends browser navigation/column/path work back to non-programmers.
This turn is diagnosis only: no runtime changes, C4C execution, restart, approval
request or installed Workflow modification. Branch main; earlier browser/source
work and draft-submission history are in the evaluation documents below.

## What is now verified

- Live browser/operate schema now contains wait_for, header_table and pagination
  with key_columns. The earlier stale-Host observation no longer describes the
  current installation.
- Resident candidate wf-20261109-102227-3989e0 is revision 2, source conversation,
  installed engineering/c4c-sales-order-report@1.0.1. The Agent revised the
  externally submitted full-flow candidate into four browser actions: open Home,
  click Sales, click #__button22, read body text. No All/date/pagination actions.
- Read the owner's actual conversation, run records, candidate and telemetry.
  Trial and form runs capture Home; Python exits 1 with missing Sales Orders
  headers. Platform still says succeeded / three successful steps and lists an
  old test workbook/summary. See conversation-5767f95c3c1e47c986ef1910307bf483.
- Read-only current-source minimal reproduction confirms output_check accepts
  a failed Python result containing an old nonempty XLSX. data_nonempty also
  accepts a nonempty failure dictionary. No fake live pass was inferred.
- Browser conversation tool supplies generic action-object schemas and bounded
  text/80 elements, with no scoped DOM/AX/screenshot action. Code-only failure
  loses the failed action/target/current page. Codex's earlier diagnostic DOM
  inspection was not equivalently available through AEP's browser tool.
- Draft guidance already says repair/retest, but readiness/requirement coverage
  is not strongly enforced. Inline form results are stored for later chat, not
  automatically resumed into authoring repair. Installation is approval, not
  independent proof of full SOP coverage.
- A supplied full lookup path was not bound into the form (required, no default).
  Later directory inputs reach execution. Known files should be stored/prefilled
  and validated before running, beyond the bounded chat history.

## Verification and durable evidence

Detailed findings, source references, confidence limits and proposed priorities:
docs/evaluations/SOP_WORKFLOW_AUTONOMY_DIAGNOSIS_2026-11-09.md.

Used read-only SQLite connections for persisted evidence and AEP MCP catalog,
capability, list and show-installed. No source implementation/tests changed;
therefore no full-suite/build rerun for this documentation-only diagnosis.
Git diff --check is required before committing these records.

Previous evidence remains in C4C_LIVE_WORKFLOW_2026-11-09.md and
CHAT_DOCUMENT_ATTACHMENTS_2026-11-09.md under docs/evaluations. Those establish
externally assisted execution/attachments, not autonomous resident authoring.
The source/browser commit was c1a0ee90; draft visibility follow-up f3cbf62f.
Private tested package remains Documents/aep-workflows/c4c-sales-order-report.
Do not overwrite the installed v1.0.1 during diagnosis; it is failure evidence.

## Next recommended work (not implemented / proposed design)

First fix P0 program failure and current-run artifact semantics with regressions
for nonzero exit plus leftover XLSX/summary. Then scope browser inspection and
precise failure evidence, durable authoring requirements/inputs and bounded
repair continuation. Preserve deterministic execution, Bridge/origin policy,
per-turn side-effect deduplication and normal human installation/business approval.

Acceptance must use a fresh resident AEP conversation with original SOP/workbook,
without Codex-provided selectors/scripts, manual page switching or copied field
names. Verify All, supplied dates, every page/current count, conversions and new
output; deliberately inject a failure and verify correct failure/repair behavior.
Do not substitute another externally hand-built passing Workflow for this test.
