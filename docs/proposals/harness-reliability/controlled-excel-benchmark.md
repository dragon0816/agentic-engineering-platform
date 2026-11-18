# Controlled native-loop Excel repair experiment

2026-11-18, machine 141, harness/reliability-141. One synthetic trial using
gpt-5.6 through the existing AEP model adapter and gateway
http://172.25.228.59:4000/v1. Credentials came from private delivery and were
resolved in memory; no credential value or private reference is stored here.

## Fixture and execution

Disposable ignored workspace `.scratch/live-excel-repair-1`, fictional CSV:

```csv
Item,Quantity,Price
Fixture-A,2,3
Fixture-B,4,5
```

Requested output: `output/items.xlsx`, sheet `Items`, exactly these headers and
numeric values, preserving order:

```text
Item       Quantity Price Total
Fixture-A  2        3     6
Fixture-B  4        5     20
```

Used actual Gateway.converse, coding Skill/run Workflow, Bridge, RunPythonHandler,
Windows RestrictedRunner and SqliteLocalState. Only coding__run was offered;
existing explicit fixture grants authorized its disposable workspace. Model had
five allowed turns. No corporate data, BI vault or live host state was read.
The test fixture's network-rule probe is stubbed as in test_run_python; this does
not certify a production firewall configuration or network containment.

At the handler's first run, a scratch-only wrapper replaced the model's script
with `print('INJECTED_FIXTURE_FAILURE: repair and run again'); raise SystemExit(1)`.
The real restricted process therefore failed with a known observed exit, not an
unknown side effect. Subsequent calls ran the model's unmodified generated script.
The request explicitly told the model to inspect failures, rerun and read back
the workbook. An independent host-side openpyxl read compared the saved rows and
headers exactly, with `data_only=True`; success required actual workbook values.

## Result

```json
{
  "passed": true,
  "conversation_status": "answered",
  "failure_code": null,
  "model_turns": 3,
  "worker_calls": 2,
  "workbook_oracle_passed": true,
  "operations": [
    {"status": "failed", "code": "python_execution_failed"},
    {"status": "completed", "code": null}
  ]
}
```

Scratch script and machine result: `.scratch/live-excel-repair.py` and
`.scratch/live-excel-repair-1/result.json`. This was a single live trial, with no
automatic test-run retries. It confirms current adapter/loop recovery for this
known-exit fixture; no rate, parity, cost or broad reliability claim follows.

The independent oracle belongs to this experiment. Generic AEP task completion
does not thereby acquire an Excel business-schema validator. Exit 0/file existence
alone remain insufficient for arbitrary workbook correctness. The historical SOP,
PDF, deployment SHA and execution trace were not available, so this is not a
reproduction or attribution of the original incident.

## Negative verification control

A separate scratch experiment created a readable, nonempty `wrong.xlsx` with
header `WrongColumn` and value `wrong-value`. A synthetic succeeded coding tool
observation was given to the actual
`agent.conversation_harness.check_answer(text, tools, roots)` function.
Both existing checks (`no_unbacked_action_claim`, `named_outputs_exist`) passed,
while an independent comparison against Item/Quantity/Price/Total failed.
Machine result: `.scratch/verification-boundary/result.json`.

This confirms the existing checks' scope; they do not assert Excel semantics.
It does not claim an existing declared schema check was overridden, or that an
`answered` conversation is a formally verified TaskContract. Existing portable
CompletionCheck kinds are nonempty/sha256; excel.read-sheet can supply structured
workbook data, but no generic mandatory Excel acceptance binding was verified.
Before expanding the runtime contract, obtain an actual task oracle and decide
how its required checks attach to the existing Workflow/Skill/Task mechanisms.
The owner was asked for the original SOP/template and expected calculation rules.
