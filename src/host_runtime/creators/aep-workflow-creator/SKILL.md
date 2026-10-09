---
name: aep-workflow-creator
description: Build a Workflow for the AEP (Agentic Engineering Platform) Host and submit it for the owner's approval. Use when asked to create, revise or fix an AEP Workflow, an automation the AEP Agent should rerun with new values, or a "reusable workflow for AEP".
---

# AEP Workflow creator

An AEP Workflow is a JSON manifest: parameters the person gives at each run, and
steps that each call one installed capability. The AEP Host runs it, not you.
Your job is to write it, check it, test it on the Host, and ask the owner to
install it.

## Tools

Use the `aep` MCP server tools when they are available. Otherwise run the same
operations with the CLI, which prints JSON:

| MCP tool | CLI (`aep-host assets --config <host.json> --agent <you> ...`) |
|---|---|
| `aep_catalog` | `catalog` |
| `aep_check_workflow` | `check-workflow --file draft.json` |
| `aep_submit_workflow` | `submit-workflow --file draft.json --title "..." [--candidate wf-...]` |
| `aep_run_workflow` | `run-workflow --candidate wf-... --arguments '{"month": "2026-09"}'` |
| `aep_install_workflow` | `install-workflow --candidate wf-...` |
| `aep_status` / `aep_list` / `aep_get` | `status --approval ap-...` / `list` / `get --candidate ...` |

## Procedure

1. **Read the catalog first.** `aep_catalog` gives `workflow_format`, every
   installed capability with its `input_schema` and `side_effect`, and the
   installed Workflows. Use only capabilities listed there, at the exact
   version shown. Do not invent capabilities or input fields.
2. **Design the parameters.** Everything that changes between runs (a month,
   a folder, a file) is a parameter with `scope: "runtime"`. Everything that
   stays the same is fixed in the steps.
3. **Write the steps.** Each step is
   `{"capability": "ns/name@1.2.3", "inputs": {...}}`. Each input is one of:
   - `{"source": "fixed", "value": <JSON>}`;
   - `{"source": "run", "path": ["<parameter>"]}` (`[]` is all run values);
   - `{"source": "step", "step_index": N, "path": ["<field>"]}`, an earlier
     step's output.
   Inputs must satisfy the capability's `input_schema`.
4. **Custom processing.** Use `coding/run-python@1.0.0` when it is in the
   catalog. Give it a complete script and an absolute workspace folder under
   one of the catalog's `coding_workspace_roots`; put the script's input files
   in that folder's `input/` (only `output/` is writable). The
   script reads run values with
   `json.load(open(os.environ["AEP_WORKFLOW_PARAMS"]))`, writes only under
   `<workspace>/output`, and puts run values in output file names. Systems the
   person signs in to are reached only through `browser/operate` or
   `desktop/operate` steps, never fetched by the script.
5. **Declare the outputs.** Add `checks` naming what a successful run must
   produce (e.g. a non-empty `*.xlsx` from the run-python step). The Host checks
   them after every run; a run that ends without them counts as failed.
6. **Check.** Run `aep_check_workflow` and fix every problem it lists. Repeat
   until it says `ok`. Problems are exact: a missing capability, a field path,
   or a name that belongs to someone else.
7. **Submit.** `aep_submit_workflow` returns a `candidate_id`. Pass that
   `candidate_id` when you revise, so the candidate keeps one history.
8. **Test on the Host.** `aep_run_workflow` with realistic test values.
   - A read-only Workflow runs now and returns step statuses and failure
     codes.
   - Anything else returns an `approval_id`. Tell the person it waits for
     their approval in Agent Web, then poll `aep_status`.
   - When a step fails, fix the cause, resubmit with the same `candidate_id`,
     and run again.
9. **Ask to install.** Once a run succeeds, call `aep_install_workflow` and
   tell the person to approve it in Agent Web. It is reusable only after
   approval.

## Rules

- You never see the data a run read or wrote. You see statuses and codes
  only, by design (company data rule). Do not ask the person to paste
  company data to you. The AEP Agent and the owner look at results in Agent
  Web.
- Never put passwords, tokens or keys in a fixed value.
- Never write manifests directly into the Host's workspace folders. Doing so
  bypasses the owner's approval.
- Never claim it ran on AEP unless `aep_run_workflow` or an approved run says
  so.
- The host assigns namespace, owner and version. A name already installed by
  someone else is refused, so pick another name.
