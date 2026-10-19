# Revising an installed Workflow from chat

Owner decision 2026-10-19. Decision record: `docs/DECISIONS.md` 2026-10-19 "The Agent revises an
installed Workflow by building on its real code".

## Problem

The owner asked the Agent to change the Issue Key fallback rule of an installed Workflow. The
Agent answered that the platform did not expose the Workflow's source and rewrote a new "v2"
from scratch. Three causes:

1. `authoring__get_workflow` said it showed "a drafted or installed Workflow" but read only chat
   candidates by `candidate_id`. A Workflow from the bundle, the Marketplace or the Shared
   Platform could not be read or revised.
2. A Workflow whose logic is a capability package shipped inside AEP had no readable source.
3. The rewrite embedded its whole logic as a fixed `coding/run-python` script, so it shared
   nothing with the original.

## What the Agent can do now

| Tool | What it does |
|---|---|
| `authoring__get_workflow` | `workflow` (`namespace/name@version`, `name@version`, `namespace/name` or a name; a name gives its highest installed version) shows an installed Workflow; `candidate_id` shows a draft. Returns parameters, steps with every input (an embedded script is a fixed input), checks, progress stages, secret names. Over 20,000 JSON characters it returns a slice (`truncated`, `total_chars`, `offset`, `next_offset`, `json_text`, `notice`); call again with `offset`. |
| `authoring__revise_workflow` | `workflow`, optional `title`. Copies the installed manifest into a chat candidate one version up (1.0.0 → 1.0.1, same name), `source: revision:<identity>`, `base_digest` = digest of the installed manifest, owner = the person, lifecycle draft. Asking again continues the open revision draft. |
| `authoring__show_capability_source` | `capability` (a package such as `weekly_report`, `capabilities.weekly_report`, or an installed capability target or name), optional `file`, `offset`. Read-only. Without `file` it lists the package's readable files. |

The flow the tool descriptions, `aep-workflow-creator` and the agent-mode policy teach:
get_workflow (installed) → revise_workflow → get_workflow (candidate) → draft_workflow with that
`candidate_id` and the whole Workflow → the in-chat install card → the person's **Install**.

## Rules

- **Who may read.** The owner and recorded contributors always may. Otherwise the Workflow must
  be published and either owned by a team, organization or service (it came with the bundle,
  the Marketplace or a Shared Platform selection, which already decided the person may use it)
  or visible to the organization. Another person's `private` or `team` Workflow answers
  `workflow_unknown`, the same as a missing one. Manifests never hold credentials
  (`RegistryContract`); secrets appear by name only.
- **Same name or fork.** The owner, or a co-editor (a name in `metadata.contributors`), keeps
  the name and the next version; a co-editor's version keeps the original owner. Anyone else,
  including a team-owned shipped Workflow, gets a fork `<name>-<actor>` (a numeric suffix when
  taken) at 1.0.0, owned by them; the tool says so (`forked`, `note`).
- **Version.** Editing a revision keeps the one version above the highest installed one; it does
  not climb with each edit as an ordinary candidate does.
- **What the draft format cannot express** is carried over from the Workflow a draft continues:
  `progress_steps`, `occupies_machine`, `secrets`, central execution and discovery categories.
  `run_alias` is not carried (two versions would claim one alias).
- **Installing.** The existing install path: a new file next to the old one. The old version
  stays installed and readable by its exact version; its file and run history are unchanged. The
  model has no tool that installs or approves; nothing edits an installed file or the AEP package.
- **Card.** The draft install card shows "Revision of X 1.0.0 → 1.0.1" (or "Fork of X as Y") and
  a summary: description, parameters added, removed or changed, changed steps and inputs, and for
  every multi-line fixed text (an embedded script) its line delta (`request.script +2/−1 lines`).
  A revision that changes nothing yet gets no card.
- **Capability source.** Only Python files and `manifest*.json|yaml` under one package folder of
  the installed `capabilities` package. Relative paths only: `..`, absolute paths, drive letters,
  caches and other files answer `capability_file_refused`; unknown packages
  `capability_package_unknown`. Lines that look like credentials are masked. Slices of 20,000
  characters. The answer says how to change behaviour: revise the Workflow (a parameter, or a
  `coding/run-python` step with the adjusted logic); the package is never edited.

## External agents (authoring MCP and `aep-host assets`)

`aep_show_installed_workflow` / `show-installed-workflow` and `aep_revise_workflow` /
`revise-workflow` exist with the same behaviour, limited by the PUBLIC rule: only installed
Workflows owned by the Host's owner and installed from an authoring draft on this Host
(`validation_refs` has `chat-candidate:`) are shown, the same drafts `aep_get` already shows.
Anything else answers `workflow_withheld` with a pointer to Agent Web's **Revise in chat**.
External agents have no capability-source tool.

## Agent Web

Capabilities, an installed Workflow: **Revise in chat** (44 px, `.btn`, light and dark) opens a
new session with "Revise the installed Workflow <identity>: " typed in. Nothing is sent until
the person sends it.

## Tests

`tests/test_workflow_revision.py` (fakes; a fixture modelled on the weekly report) and
`tests/test_workflow_revision_chat.py` (fake-model chat end to end, and the headless-browser
check; screenshots with `AEP_UI_SHOTS=.scratch/workflow-revise-ui`).
