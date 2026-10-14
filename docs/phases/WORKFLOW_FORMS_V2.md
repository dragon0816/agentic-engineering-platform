# Workflow forms v2 (owner decisions 2026-10-15)

Workflow authors declare typed parameters (`WorkflowParameter`) and AEP draws
the Agent Web form and the Telegram question flow from them; nobody writes GUI.
This slice closes the gaps found when porting n8n Workflow 13 (release
package): dynamic `fn:` lists on the Web, "pick or type" lists, Telegram
multi-select, picking files from a folder, real uploads and "same as last
time". It also replaces the three-run release procedure with one Workflow,
`engineering/rs-wmt-package-release@1.0.0`.

The old rs_workflow_system dashboard and bot (`ops-dashboard/static/app.js`
`paramField`, `telegram_pack.py`, `telegram_bot.py`) are a read-only behaviour
reference. Nothing of n8n is ported or used.

## A. Framework

### A1 `fn:` lists on Agent Web

The Web form treats every `choices_source` (`ref:` and `fn:`) on a `select`
as dynamic: it asks `/api/workflow-options` and asks again when a field the
source depends on changes. A Telegram flow and the engine already did.

### A2 `allow_other` ("pick or type")

`WorkflowParameter.allow_other: bool = false`, only on `select`, not with
`multiple`. Meaning: the listed choices are suggestions; any nonempty text is
accepted. Every other check (`required`, `pattern` does not apply to select)
still applies.

- Validation (`parameter_value_problem`) skips the "must be a declared choice"
  rule; the engine skips its dynamic-choice check for the field, so a slow or
  broken choice function never blocks a run.
- Agent tool schema: no `enum`.
- Agent Web: a text input with a `<datalist>` of the choices and a Refresh
  button (the old dashboard's combo box).
- Telegram: the choices as buttons; a typed value is accepted as is.

Choice functions fail soft: an error, a missing setting or a timeout is "no
list" (`unavailable`); a form then shows an empty list with a hint, and with
`allow_other` the person just types.

### A3 Telegram multi-select

A `multiple` select with known choices shows one button per choice (data
`pick:<n>`), a tap toggles a check mark by editing that message's keyboard,
and a `Done` button (`pick:done`) moves on. Typing the values (comma or line
separated, or 1-based numbers) still works. Up to 96 choice buttons, 3 per row
(`MAX_BUTTONS`; Telegram allows 100 buttons a keyboard). Single-select buttons
send the value, or `#<n>` when the value is longer than Telegram's 64-byte
callback limit.

### A4 Files in a folder (`fn:folder_files`)

A built-in read-only choice function:
`fn:folder_files?folder={inbox_path}&accept=.json` lists the regular files
directly in the folder (no subfolders, no hidden files, no links), filtered by
extension (comma separated, case-insensitive), sorted by name, at most 500.
Each value is the bare file name, so a value can never point outside the
folder. The folder must be an absolute, existing directory.

A placeholder may now name a `scope: static` setting as well as an earlier
runtime field. The manifest validator accepts a static name in any position
(settings are not asked); `ChoiceSources.resolve` binds static names from the
install's settings (they override run answers, which may not carry settings
anyway); `/api/workflow-options` never waits for a static name.

### A5 Real uploads (`kind: upload`)

Store: `<workspace>/workflow-uploads/<set>/<field>/<name>` with
`host_runtime/workflow_uploads.py`. `<set>` is `up-<UTC timestamp>-<hex>`, one
per form fill (Web) or flow (Telegram). Rules, checked before writing:

- size at most 25 MB a file (`MAX_UPLOAD_BYTES`), at most 20 files a field;
- the extension must be in the field's `accept` (when `accept` is declared);
- the name is sanitized (`attachments.safe_name`: no folders, no characters
  Windows refuses); an existing name in the same folder gets a numbered name;
- the field must be a runtime `upload` field of an installed Workflow.

The run value is the stored absolute path (a list when `multiple`). The engine
(`WorkflowEngine(upload_root=...)`, set by the host) rejects a run whose
`upload` value is not a file inside the store (`workflow_upload_outside_store`),
so neither a model nor a typed path can pass an arbitrary file off as an
upload. Uploaded bytes are data for the Workflow's steps; they are never read
as instructions and never sent to a model by this feature. Sets older than 30
days are pruned when a new set is created.

- Agent Web: `<input type=file accept multiple>`; each chosen file is posted
  (base64 JSON, as chat attachments are) to `POST /api/workflow-uploads`; the
  field lists what was stored; Run is refused while an upload is in flight.
  The schedule form, which has no live person to upload, keeps the path box.
- Telegram: the flow asks the person to send the files as documents one by
  one, then `/done` (or `/skip` when optional). Each document is checked
  against `accept`, the 25 MB store limit and Telegram's 20 MB bot download
  limit before it is downloaded, then stored the same way. A flow started
  where no store exists keeps the old rule (a required upload is refused and
  points to Agent Web).

### A6 Same as last time (`group: identity`)

`<workspace>/identity-presets.json` keeps, per member and per Workflow
(`namespace/name`, any version), the last identity-group values of a run that
passed validation and was dispatched. Only text, number, boolean and lists of
text are kept; a value that looks like a credential is never stored
(`reject_embedded_secrets`). It is local to this computer.

- Agent Web: `POST /api/workflow-identity` returns the values; the form shows
  "Use last values: ..." which fills the identity fields (and refreshes lists
  that depend on them).
- Telegram: when the flow has identity fields and a preset exists, the first
  question is "Same as last time? company: Foxconn, chipset: kt326" with
  `Yes` / `Change`. Yes fills them and skips those questions.

### A7 Authoring format for external coding agents

`WORKFLOW_FORMAT` (catalog of `aep-host assets` / MCP) and the
`aep-workflow-creator` Skill document every `ParameterKind` and the
presentation fields. The `checks` example no longer carries `note`, which
`WorkflowOutputCheck` (closed contract) rejects; the explanation moved to a
separate key.

## B. `engineering/rs-wmt-package-release@1.0.0`

One Workflow, started by name (`/run rs-wmt-package-release` in Telegram, the
Workflows list in Agent Web); no numeric alias. The old preview loses alias 13.
Steps: `release-package/prepare` -> `release-package/commit` (branch and
fingerprint from step 0) -> `release-package/push` (branch and commit from step
1, `push` from the run). The three step Workflows stay for advanced use.

- `dryRun` (default on): prepare writes the working copy and reports the plan;
  the commit step skips ("dry run") and the push step skips.
- `push` (default off, `confirm`): the push step pushes only the commit this
  run made (it reads the commit step's record and checks branch, HEAD, a clean
  tree and origin, never forced). Off: skipped ("push not requested").
- The Workflow's effect is `external_side_effect`, so every Telegram run is
  confirmed with a tap and each capability keeps its Bridge approval policy.

Fields: `companyName` (text, identity), `chipsetId` (select,
`fn:release_package.chipsets`, allow_other, identity), `chipsetVersion`
(select, `fn:release_package.versions?package={chipsetId}`, allow_other,
blank = newest published), `info` (text, identity), `cmpKtOption`
(KT160/KT161), `generalTestcaseVersion` (select,
`fn:release_package.versions?package=rs-wmt-general-testcase`, allow_other),
`notes`, `testPlans` / `configurations` / `overlays` (multi select from
`fn:folder_files?folder={inbox_path}&accept=...`), `testPlanUploads` /
`configurationUploads` / `overlayUploads` (upload, multiple, same accept),
`suffix`, `releaseVersion`, `dryRun`, `push`.

Upload design: the prepare step accepts upload paths only inside the host's
upload store (`PrepareHandler(upload_root=...)`, trusted host configuration),
checks each is a regular file with an allowed extension for its kind, and
copies it straight into the branch (`testplans/`, `configurations/`,
`overlay/`). The inbox is not written. Two inputs with the same destination are
refused. The working copy, inbox and origin keep the isolated-root rules.

Choice functions `release_package.chipsets` (readiness table
`/api/chipsets`, else the package index root's `rs-wmt-*` names) and
`release_package.versions` (PEP 503 index of one package, releases before dev
builds, newest first) read the Workflow's `artifactory_base_url` /
`readiness_base_url` settings, use a 5-second timeout and fail soft. Tokens
come from the host environment (`ARTIFACTORY_TOKEN`, `OPS_TOKEN`) exactly as
the prepare step reads them, and are never returned.

Install: the shipped manifest goes through the owner's normal path (draft,
then Install in Agent Web). Its settings are per Workflow, like the three step
Workflows'.

## Out of scope

Editing an existing chat message for anything but multi-select toggles; drag
and drop; uploads in the schedule form; remembering non-identity fields.
