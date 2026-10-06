# SOP to Workflow on the Bridge

Owner request 2026-10-06: give the Agent workflow steps or an SOP PDF, discuss
it in natural language, and get a Workflow that runs on this system; the
generated Workflows need web and Excel operations. This is the first slice of
`docs/phases/NL_WORKFLOW_AUTHORING.md` (P1 building blocks + P2 generation),
started before the rs_workflow_system migration ends, at the owner's request.

## Owner decisions (2026-10-06)

1. Web steps replay fixed targets recorded at authoring time; no model runs
   when the Workflow runs. A changed page stops the step with a typed failure.
2. A generated Workflow is installed only after a preview run the owner
   approves: read steps run for real, write steps only say what they would do.
3. Discussion state lives in a dedicated Workflow authoring session, not in
   chat history.
4. The SOP PDF is uploaded in Agent Web.
5. Harness structure changes are discussed with the owner before they are
   built. Designs A and B below were approved by the owner on 2026-10-06.

## What exists (2026-10-06)

- `workflow-author/draft`: SOP text or PDF (pypdf, text only) to a checked
  `WorkflowManifest` draft composed of installed capabilities; single shot,
  no parameters, no clarification.
- `integrations/browser.py`: CDP over a stdlib WebSocket; navigate, element
  list, click/fill by index with a page-changed guard, screenshot. Not
  wrapped as a capability.
- Excel: openpyxl reader and a COM writer; capabilities are all
  Workflow-specific.
- `PersonalWorkflowAuthor` / `publish_validated_workflow`: used only by tests.

## Harness structure changes (approved 2026-10-06)

### A. Preview run in the Workflow engine

`WorkflowEngine.execute(..., mode="preview")`. A step whose capability side
effect is `read` runs; any other step is not dispatched. It is recorded as
planned, with its resolved inputs. A capability may implement an optional
`preview(inputs)` that computes what it would do without doing it (for
example, the rows an Excel upsert would add or change). A step whose inputs
come from a step that did not run is planned too. A preview never writes the
run journal as a real run, has its own status `previewed`, and is refused for
a Workflow that has no read step to show. Grants still apply: a preview runs
only what the actor may run.

### B. Workflow authoring session

A durable record per authoring effort, `workspace/authoring/<id>.json`. It
holds:
- the SOP source (the uploaded PDF's stored path and its text digest);
- the discussion turns;
- the current draft;
- open questions;
- recorded web targets;
- the last preview;
- the status: `drafting -> needs_input -> ready -> previewed -> approved -> installed`.

The model may draft, ask questions and propose web targets. Only the owner,
in Agent Web, may approve and install. That action writes the manifest to
`assets/workflows/` and adds grants, and it is not a tool the model can call.

## Slices

| Id | Slice | Harness change |
|---|---|---|
| W1 | Practice target: a loopback practice web app, a practice workbook, a sample SOP PDF | no |
| W2 | Web building blocks on `browser.py`: open, read/extract table, fill and click by recorded label target; origin allowlist in host.json | no (new capabilities) |
| W3 | Excel building blocks: read range, upsert rows, write sheet, with `preview` | no (new capabilities) |
| W4 | Preview run (design A) | yes |
| W5 | Authoring session (design B) | yes |
| W6 | Drafter: parameters, clarification questions, missing capability as `needs_input`, recording web targets | no |
| W7 | Agent Web: PDF upload, authoring panel (discussion, draft steps, preview, approve and install) | no |
| W8 | Live run on the practice target, then one real SOP chosen by the owner | no |
| W9 | Business cards (after W1-W8): photo -> local OCR -> confirmed fields -> contacts database -> org chart | no (new capabilities; channel rule change below) |

## Business cards (W9, owner decisions 2026-10-06, revised the same day)

Reference: the owner's Hermes skill `C:\Users\Chi_L\Downloads\business-cards-skill`
(`SKILL.md`, `scripts/cards.py`), which the owner rates highly. It works well
because the model reads the photo itself, through the same local LiteLLM
Gateway (`127.0.0.1:4000`, gpt-5.5), not because of OCR.

- Photos come from Agent Web upload or Telegram. Telegram accepts photos only
  from allowed senders; every other attachment is still refused. This changes
  the channel rule that refused all attachments.
- Reading: the Gateway model reads the photo, as Hermes does. The owner
  approves sending business-card photos to the internal Gateway. This needs
  the model's `vision` capability and a data-approval record for card
  images; no other personal data is sent. This replaces the earlier
  local-only decision.
- Output, adopted from the Hermes skill: one JSON object with name, company,
  department, title, phone (desk, extension kept), mobile, email, address,
  website and notes (romanised forms go in notes), plus `uncertain`, the
  fields that were blurred or inferred. Omit a field rather than invent it.
  The confirmation asks only about the `uncertain` fields.
- Storage: append-only local SQLite in the workspace. Every scan is a row;
  queries take the newest row per (name, company), and a re-scan reports
  what changed ("上次是研發部經理，現在是協理"). The photo stays local. The 14
  cards in Hermes' `cards.db` are imported once with their history; Hermes'
  database is not changed.
- Chart: grouped by company and department, people sorted by title
  seniority, rendered with Graphviz (installed). Every render says it is not
  a reporting chart, because cards carry no reporting lines. People with
  `uncertain` fields are marked.
- Replies answer the question asked and never dump the store.
- The cards are the second generation target, used to check that SOP to
  Workflow works for more than the first case.
