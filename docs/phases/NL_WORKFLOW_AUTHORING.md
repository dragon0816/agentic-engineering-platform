# Natural-language Workflow authoring and modification

Status: agreed direction (2026-10-05), to start after the rs_workflow_system
migration; building blocks are extracted during that migration. Owner
decisions are recorded in `docs/DECISIONS.md` (2026-10-05).

## Goal

1. A person describes a task to the Agent in natural language and the Agent
   produces a runnable Workflow combining web operations with content
   capture, Excel integration, email and GitLab operations.
2. A person asks the Agent in natural language to change an existing Workflow.

## Principle: the Agent composes; code generation is the exception

A Workflow is an ordered composition of capabilities (typed contract,
declared side effect) plus one parameter declaration (per-install settings
vs run-time parameters, from which every form is generated). The Agent
composes existing capabilities; the bounded coding harness (E2E-03) produces
a new capability only when a needed building block is missing, and that
capability is a candidate without execution rights until approved.

## Generating a Workflow

1. Clarify the request (site and fields, workbook and sheet, recipients,
   GitLab project) in conversation.
2. Plan steps, map each to an installed capability, and list missing ones.
3. Missing blocks: the coding harness drafts a script-tool package with tests
   in a sandbox; it stays a candidate.
4. Generate the `WorkflowManifest` (steps, data flow, parameter declaration).
5. Check contract, dependencies and side-effect classification; dry-run with
   write capabilities in preview mode; show the step graph, generated forms and
   dry-run result in Agent Web.
6. The owner approves; install; runs still need grants, and sending email
   always needs a per-run approval.

## Modifying a Workflow

1. Load the installed version and explain it in plain language.
2. Propose a new version as a diff (steps, data flow, parameters); a
   published version is never edited in place.
3. Regression: the previous version's parity and evaluation cases plus new
   cases for the change.
4. Approve and publish the new version; the previous version stays
   installable for rollback.

## Building blocks needed (extracted during migration)

| Family | Existing | To extract (source workflow) |
|---|---|---|
| Web + content capture | `integrations/browser.py` (Edge persistent profile) | navigate, extract structured content, screenshot, SSO session handling (W03 C4C, W06b portal) |
| Excel | COM writer (W10/W11) | read range, upsert rows, write sheet, with dry run (W03, W07, W10) |
| Email | Outlook draft (W11) | draft and send (send always approved per run) (W06b, W11, W14) |
| GitLab | none | projects, pipelines, branches, merge requests, controlled push (W12, W13) |

Each migrated job keeps WRAP parity; the operations inside it are also
extracted as reusable capabilities with typed contracts and dry run, so the
migration itself shows which tools the Agent needs.

## Owner decisions (2026-10-05)

1. The owner may approve Agent-generated Workflows alone.
2. Web capture covers internal sites (C4C, portals) and external sites.
3. Generated Workflows are private by default; at publication the publisher
   chooses who may install them.
4. Extract building blocks during the migration.

## Safety rules for external and internal web content

- Captured page content is data, never instructions: it is never placed in a
  prompt as guidance, and tool calls cannot be triggered by page text.
- External sites never receive company credentials or the corporate Edge
  profile; internal sites use the persistent profile only for allowlisted
  origins.
- Captured content keeps its data classification; internal content is not
  sent to an unapproved model endpoint.
- Every web, Excel, email and GitLab capability declares its side effect;
  writes need grants, sends and pushes need per-run approval.

## Phases

| Phase | Scope |
|---|---|
| P1 | Building-block capabilities from the migration (web, Excel, email, GitLab) with typed contracts and dry run |
| P2 | Natural language -> composed Workflow: chat entry, clarification, generated parameter declaration, dry-run preview, candidate, approval |
| P3 | Natural language -> modified Workflow: versioned diff, regression, approval, publish, rollback |
| P4 | Missing blocks: coding harness -> script-tool package with tests -> review |
