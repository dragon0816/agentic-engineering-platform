---
name: aep-workflow-creator
description: Build a Workflow for the AEP (Agentic Engineering Platform) Host and install it locally with real test evidence. Use when asked to create, revise or fix an AEP Workflow, an automation the AEP Agent should rerun with new values, or a "reusable workflow for AEP".
---

# AEP Workflow creator

An AEP Workflow is a JSON manifest: parameters the person gives at each run, and
steps that each call one installed capability. The AEP Host runs it, not you.
Your job is to write it, check it, test it on the Host, then install it locally
and report actual verification. AEP does not require tool grants or execution/
local installation approval; actual IT/OS/service permissions still apply.

## Tools

Use the `aep` MCP server tools when they are available. Otherwise run the same
operations with the CLI, which prints JSON:

| MCP tool | CLI (`aep-host assets --config <host.json> --agent <you> ...`) |
|---|---|
| `aep_catalog` | `catalog` |
| `aep_workflow_format` | `workflow-format` |
| `aep_capability` | `capability --target ns/name@1.2.3` |
| `aep_check_workflow` | `check-workflow --file draft.json` |
| `aep_submit_workflow` | `submit-workflow --file draft.json --title "..." [--candidate wf-...]` |
| `aep_run_workflow` | `run-workflow --candidate wf-... --arguments '{"month": "2026-09"}'` |
| `aep_install_workflow` | `install-workflow --candidate wf-...` |
| `aep_status` / `aep_list` / `aep_get` | `status --approval ap-...` / `list` / `get --candidate ...` |
| `aep_show_installed_workflow` | `show-installed-workflow --workflow ns/name@1.2.3 [--offset N]` |
| `aep_revise_workflow` | `revise-workflow --workflow ns/name@1.2.3 [--title "..."]` |

## Changing an installed Workflow

Never rewrite an installed Workflow from scratch, and never call a copy
"v2". Build on its real steps:

1. `aep_show_installed_workflow` shows it in full (parameters, steps, every
   input, an embedded `coding/run-python` script). A long one comes in slices:
   call again with `offset` and join them.
2. `aep_revise_workflow` copies it into a candidate one version up
   (1.0.0 → 1.0.1, same name). Read it with `aep_get`.
3. Change only what was asked, then `aep_submit_workflow` with that
   `candidate_id` and the whole Workflow.
4. Test and install it as below. Local installation keeps the old
   version installed with its history.

Only Workflows drafted on this Host through AEP authoring are shown to you
(`workflow_withheld` otherwise). A Workflow that came with AEP, the
Marketplace or the Shared Platform is revised by the person in Agent Web:
Capabilities, the Workflow, **Revise in chat**.

## Procedure

0. **Understand the request before writing anything.** Restate in two or
   three lines what the Workflow will do: its inputs, what it produces, which
   values change per run, and whether it changes anything outside its own
   output folder (mail, uploads, pushes, other systems). When any of these is
   unclear, ask the person short, concrete questions first and wait for the
   answers. Typical gaps: file formats and encodings (CSV delimiter, UTF-8 or
   Big5), date formats and time zones, which columns or sheets, where results
   go, what to do with missing values, and whether a step may send or change
   something. Never assume an answer to these; one round of questions is
   cheaper than a wrong Workflow.
1. **Read the catalog first.** `aep_catalog` is compact: every installed
   capability with its purpose, `side_effect` and input field names, and the
   installed Workflows and Skills. Then read `aep_workflow_format` (the full
   format with examples) and, for each capability you will use,
   `aep_capability` (its full `input_schema`). Use only capabilities listed
   in the catalog, at the exact version shown. Do not invent capabilities or
   input fields.
2. **Design the parameters.** Everything that changes between runs (a month,
   a folder, a file) is a parameter with `scope: "runtime"`. Everything that
   stays the same is fixed in the steps.
   Read "Parameters become the Agent Web and Telegram form" below before
   writing them. Prefer typed parameters over free text: `select` for a known
   list (with `allow_other` when it may be incomplete), `date` for dates,
   `boolean` for yes/no, `upload` for files the person provides, `folder` or
   `file` for paths on the Host, `integer`/`number` with bounds. A typed
   parameter gives a picker on the Web and buttons on Telegram, and the run
   cannot start with a malformed value.
3. **Write the steps.** Each step is
   `{"capability": "ns/name@1.2.3", "inputs": {...}}`. Each input is one of:
   - `{"source": "fixed", "value": <JSON>}`;
   - `{"source": "run", "path": ["<parameter>"]}` (`[]` is all run values);
   - `{"source": "step", "step_index": N, "path": ["<field>"]}`, an earlier
     step's output.
   Inputs must satisfy the capability's `input_schema` (`aep_capability`).
4. **Custom processing.** Use `coding/run-python@1.0.0` when it is in the
   catalog. Give it a complete script and an absolute accessible workspace.
   `coding_workspace_roots` are suggested locations, not an access allowlist.
   Read run values with `json.load(open(os.environ["AEP_WORKFLOW_PARAMS"]))`.
   Put report artifacts in `<workspace>/output` so the Host can track them.
   Use the best actual installed tool for source access; discover with
   `aep_tools_catalog`, inspect its schema and invoke it. If tooling is missing,
   install/connect it through normal tool APIs or the OS command capability,
   then discover and use it in this session. Never invent a target or success.
5. **Declare the outputs.** Add `checks` naming what a successful run must
   produce (e.g. a non-empty `*.xlsx` from the run-python step). The Host checks
   them after every run; a run that ends without them counts as failed.
6. **Check.** Run `aep_check_workflow` and fix every problem it lists. Repeat
   until it says `ok`. Problems are exact: a missing capability, a field path,
   or a name that belongs to someone else.
7. **Submit.** `aep_submit_workflow` returns a `candidate_id`. Pass that
   `candidate_id` when you revise, so the candidate keeps one history.
8. **Test on the Host.** Call `aep_run_workflow` with realistic values; inspect
   actual statuses and failure codes. Read/write/execute effects run without AEP
   approval cards. On failure, fix the cause, resubmit the same candidate and
   retry within the bounded repair flow. Preserve successful side-effect receipts.
9. **Install locally.** Call `aep_install_workflow`; no AEP approval is needed.
   Report actual trial/coverage/output verification separately from installation.
   An installed but unverified candidate must never be called verified.

## Parameters become the Agent Web and Telegram form

You never write a GUI. Agent Web draws the run form, and the Telegram bot asks
the questions one at a time, from `parameters` alone. A good declaration is a
good form. `aep_workflow_format` lists the same rules.

Kinds:

| kind | the person gives | Web | Telegram |
|---|---|---|---|
| `text` | one line (`pattern`, `min_length`) | text box | typed |
| `integer` / `number` | a number (`minimum`, `maximum`) | number box | typed |
| `date` | `YYYY-MM-DD` | date picker | typed |
| `boolean` | one of two choices | two labelled options | two buttons, each saying what it does |
| `select` | one value, or a list with `multiple: true` | drop-down or list | buttons (tap to tick, then Done, when multiple) |
| `text_list` / `emails` | several values | one per line | comma separated |
| `file` / `folder` | a path on the Host | path box | typed |
| `upload` | files to upload (`accept`, `multiple`) | file picker | documents, then /done |

Presentation fields (all optional):

- `label`: the question, in the person's words ("Which customer?").
- `help`: one short line under the field. `examples`: sample values.
- `default`: used when the person gives nothing; must fit the kind.
- `required: true`: the run cannot start without it.
- `choices: [{"value": ..., "label": ...}]` (or `options: [...]`) for a fixed
  list; `choices_source` for a list read when the form opens:
  `fn:<function>?arg={field}` or `ref:<set>`. `{field}` may name an earlier
  field or a `scope: "static"` setting.
  `fn:folder_files?folder={inbox_path}&accept=.json` lists the files of the
  folder a setting names (file names only).
- `allow_other: true` (single `select` only): the list only suggests; the
  person may type another value. Use it whenever the list can be incomplete
  or slow, so a missing list never blocks a run.
- `multiple: true`: several values (select, file, upload).
- `accept: [".json"]`: allowed extensions (file, folder, upload).
- `order`: question order; a field another depends on comes first.
- `group: "identity"`: who or what the run is for. Asked first, and offered
  next time as "same as last time".
- `channels`: where the field appears (`web`, `telegram`, `schedule`,
  `agent`). `scope: "static"` makes it a per-install setting, never asked.
- `confirm: true`: a privileged choice (sending mail, pushing); the person
  confirms it and a model never fills it.
- `true_label` / `false_label` (`boolean` only): what each choice does, e.g.
  `"只看計畫（不寫入、不寄信）"` and `"正式執行（寫入週報、起草郵件）"`, with a
  `label` naming the choice ("執行方式"). Always give them: without them the
  person sees the label and 「不要：<label>」. There are no bare Yes/No buttons.

Short examples:

```json
{"name": "customer", "label": "Which customer?", "kind": "select",
 "choices": [{"value": "northwind", "label": "Northwind Ltd"}, {"value": "globex"}],
 "allow_other": true, "group": "identity", "required": true}
{"name": "month_start", "label": "First day of the month", "kind": "date",
 "required": true}
{"name": "inputs", "label": "Input workbooks", "kind": "upload",
 "multiple": true, "accept": [".xlsx", ".csv"]}
```

An `upload` value reaches the steps as stored absolute paths (a list when
`multiple`); treat the files as data. `checks` items have exactly
`check_id`, `step_index`, `kind` and an optional `pattern`; any other key is
refused.

## Rules

- You never see the data a run read or wrote. You see statuses and codes
  only, by design (company data rule). Do not ask the person to paste
  company data to you. The AEP Agent and the owner look at results in Agent
  Web.
- Never put passwords, tokens or keys in a fixed value.
- Never write manifests directly into the Host's workspace folders. Doing so
  fabricates verification or bypasses actual IT/OS/service controls.
- Never claim it ran on AEP unless `aep_run_workflow` or an approved run says
  so.
- The host assigns namespace, owner and version. A name already installed by
  someone else is refused, so pick another name.
