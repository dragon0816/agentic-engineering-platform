# SOP Workflow autonomy: live diagnosis (2026-11-09)

Scope: diagnose the owner's resident AEP attempt, not repair its Workflow with
external code or change production. No new C4C query, restart or install.

## Direct evidence

Read the owner's persisted conversation, run results, installed manifest,
candidate record and telemetry through read-only local stores / AEP MCP.

- Current live browser/operate schema DOES include wait_for, header_table and
  pagination/key_columns. The earlier stale-Host observation is historical and
  is no longer the explanation for the current failure.
- Candidate wf-20261109-102227-3989e0 is now revision 2, source conversation,
  installed as engineering/c4c-sales-order-report@1.0.1. The Agent revised the
  externally submitted candidate, replacing its full browser procedure.
- Installed browser step has exactly four actions: open a C4C Home URL; click
  the Sales button; click dynamic CSS #__button22; read body text with look=false.
  It has no All selection, date-filter actions or pagination. The subsequent
  script parses that text. The approved run captured Home text, not order rows.
- In conversation-5767f95c3c1e47c986ef1910307bf483, approved execution and later
  form runs report succeeded / three successful steps while the last script
  exits 1 with "Could not find C4C Sales Orders headers in page text".
  A stale test workbook and summary remain in the files list.
- The same conversation initially supplies the lookup's full filename. The
  installed form nevertheless declares a required file field without a default;
  the script's internal setdefault does not prefill or satisfy that form.
  Later submitted values are directories. They reach execution instead of being
  rejected as invalid workbook inputs before browser work.
- The authoring turn made multiple browser calls and 19 model loop iterations;
  this is not evidence of no tools being offered or a turn-budget exhaustion.
  Later explanations have no tool_summary and advise manual navigation.

## Confirmed defects and mechanism

### P0: execution completion is confused with task success

RunPythonHandler returns a valid RunPythonResult even when exit_code is nonzero.
The Bridge/engine can therefore record successful capability completion while
the program failed. workflow/harness.py validates run.status and file existence;
files_nonempty checks neither program success nor run freshness. run_python.py
lists all files under output/, including prior-run fixtures.

Read-only minimal reproduction on current source: output_check(files_nonempty,
data={exit_code:1, files:[old_test.xlsx, bytes:8933]}) returns True. A nonempty
failure dictionary also passes data_nonempty. This agrees with actual failed
executions reported as successful; it is not a hypothetical concern.

Source: src/workflow/harness.py:34, :77;
src/capabilities/coding_change/run_python.py:170, :175.

### P1: insufficient observation and repair evidence

Browser tool observations provide at most 80 elements / 6000 page-text chars.
The conversation tool's actions schema is an array of generic objects rather
than the full typed WebAction schema. Failure returns a code without the failed
action index/target or a fresh page snapshot. There is no scoped DOM/AX inspection
or screenshot action in this tool contract. Codex's earlier external diagnostic
worker inspected DOM attributes/structure directly; that investigation route is
not equivalently available to the resident Agent through browser__operate.

This limits diagnosis of hidden duplicates, SAP expanders, split tables and
asynchronous controls. It does not prove every individual failure was caused by
the observation cap. The missing API/evidence is a confirmed capability gap;
its contribution to the model's choice to stop is an inference.

Source: src/host_runtime/bridge_tools.py:94;
src/capabilities/browser_session/handlers.py:55, :184, :209.

### P1: requirement coverage / readiness are guidance, not enforced gates

DRAFT_GUIDE already instructs running the reusable version and repairing it.
Nevertheless, check_reuse only requires that a draft tool was called after
one-off coding. Gateway accepts a textual answer when the model issues no more
tools. ChatCandidate holds the manifest/status, not a complete executable
requirement checklist with recorded target evidence. Installation approval
authorizes installation; install() does not independently prove a same-digest
successful run covering the requested All/date/all-page behavior.

The result is a scope reduction (full SOP -> currently visible page) that can
still become an installed asset. Stronger wording alone cannot prove compliance.

Source: src/host_runtime/chat_authoring.py:93, :201, :823;
src/agent/conversation_harness.py:256; src/agent/gateway.py:1212.

### P1: failure is not an automatic authoring continuation

Inline form execution records a user/result pair for the Agent to see later;
it does not itself enter a bounded authoring-repair task. In the observed runs
the false success further prevents a useful failure trigger. The Agent later
explains the failure but sends navigation work back to the user. Approval should
remain separate from technical validation; repair must preserve side-effect
deduplication and existing approval boundaries.

Source: src/host_runtime/web.py:5384 and its form execution caller;
src/host_runtime/chat_authoring.py:775, :1637.

### P2: supplied inputs are not owned as durable task inputs

The known workbook path is not bound into the runtime form declaration. Form
inference reads supplied text, while Gateway history is bounded to 12 messages.
Neither a script default nor old conversation text is a reliable task input
binding. Correct behavior is a stored file reference/default with provenance,
prefilled and validated as an existing workbook; ask only for truly missing
business information. The observed directory input should fail before execution.

Source: src/common/workflow_run_form.py:183;
src/agent/gateway.py:93; installed parameter declaration read through AEP MCP.

## Proposed implementation order (not implemented / not owner-approved design)

1. P0: distinguish program failure from successful invocation; identify outputs
   created/changed by this run, and reject stale files as success evidence.
   Regressions must reproduce exit_code=1 + leftover XLSX / summary.
2. Add origin-scoped browser inspection, full typed action schemas and precise
   failure/page evidence. Preserve Browser/Bridge authorization; do not give
   scripts SAP HTTP access or expose unrestricted runtime modification.
3. Persist an authoring task with supplied file/value origins, SOP requirements,
   observed targets, candidate digest and verified outcomes. Gate readiness on
   actual navigation/date/count/currency/output assertions. A fixture workbook
   is not live evidence, and incomplete coverage must not silently become ready.
4. Resume failed authorized trials into bounded diagnose/revise/retest work;
   retain human business decisions and normal installation/side-effect policy.
5. Bind known file inputs to forms and validate file-vs-directory early.

Acceptance: a fresh resident AEP conversation gets only the original request,
SOP and workbook. It discovers the UI, authors, trials and repairs using AEP
tools, then offers a verified candidate for normal approval. No Codex-provided
selectors/scripts or manual navigation/column/path transcription. Verify all
pages/current count and demonstrate a deliberate failure is correctly detected
and repaired. This is the missing product acceptance, distinct from externally
assisted execution of one good Workflow.

No implementation or model comparison was performed in this diagnosis. Current
evidence does not justify blaming model size alone or saying a model swap fixes
these contract, observation and lifecycle gaps.
