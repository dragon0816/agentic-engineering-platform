# Company Bridge host — Windows technical preview

This preview proves a credential-free, per-user installation and company-device
configuration before the shared-platform enrollment transport exists. It installs
a resident Agent that runs the Skills and Workflows you place in its workspace.

It ships the capabilities the GTM weekly report needs — a bounded read of a file
inside the workspace, a project board reader, a workbook reader and the workbook writer —
and the Skill and Workflow that run them. None of that does anything until you
configure a project board and a workbook under `integrations`; `aep-host doctor`
says whether you have. It contains no Git, browser, email, DUT or instrument
adapter, so it cannot run workflow 13.

**Nothing here is installed from a package index.** The bundle carries every
wheel it needs and installs with `--no-index`, so it works on a machine whose
pip points at a company index, or at nothing at all. The platform itself is not
published to any index, public or internal.

## Prerequisite

- 64-bit Windows 10 or 11
- 64-bit CPython 3.12 available as `python`, or its full path

The bundle is offline: its `wheels/` directory contains every Python dependency.
Do not add a password, token, cookie or API key to `host.json`.

## Install and inspect

Extract the zip somewhere short, such as `C:\aep`. Windows refuses a path of
260 characters or more, and Explorer silently leaves out the files that would
need one, so a bundle extracted inside a downloaded artefact folder can arrive
incomplete. The installer measures this before it verifies anything and says
so, but extracting shallowly avoids it.

Open Command Prompt in the extracted bundle and enter the platform actor/user:

```bat
install.cmd -Actor employee.id
```

The default Bridge ID is `bridge-<windows-computer-name>`, normalized to lowercase.
The installer prints it before making changes. A computer name is only a stable
device label; it does not authenticate the device. If two enrolled computers have
the same name, use the optional override `-BridgeId bridge-company-001`.

If Python is not on PATH:

```bat
install.cmd -Actor employee.id -PythonExe "C:\Python312\python.exe"
```

The installer verifies every bundled file, creates a versioned virtual environment
under `%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0`, writes only
non-secret device metadata, and runs `aep-host doctor`. It does not contact the
shared platform or any company system.

Run the checks again and export the JSON that will later be submitted through an
authenticated enrollment flow:

```bat
verify.cmd
"%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\.venv\Scripts\aep-host.exe" enrollment-request --config "%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\host.json" --output enrollment-request.json
```

Inspect `enrollment-request.json` before transferring it. It is identity and
capability-advertisement metadata, not proof that the device may execute anything.

## Run the resident Agent

`aep-host doctor` reports `resident agent: pending` until this Bridge knows who
may use it. Everything the Agent reads lives in the workspace the installer
created:

```text
workspace\membership.json        who may use this Bridge
workspace\grants.json            what those people may run (optional; nothing by default)
workspace\authorization.json     what the members chose, once the shared platform tells this Bridge
workspace\assets\skills\*.json   installed Skill manifests
workspace\assets\workflows\*.json installed Workflow manifests
workspace\telegram.json          the Telegram ingress (optional)
workspace\state.sqlite           what is installed and what has run (the Agent creates it)
```

`membership.json` names this device and its one bound owner. Until the
authenticated enrollment transport exists, you write it yourself from the same
values as `host.json`:

```json
{
  "device": { "bridge_id": "bridge-your-computer", "registered_by": "employee.id",
              "device_kind": "company_workstation", "windows_account_mode": "dedicated_user",
              "resource_scope": "corporate_internal", "local_isolation": "single_user" },
  "bindings": [{ "bridge_id": "bridge-your-computer", "actor": "employee.id", "role": "operator" }]
}
```

Nothing runs until `grants.json` says who may run what. Every capability
this package ships declares that it needs an approval, the reads included, so
**every grant carries an `approval_ref`**; a grant without one is no grant,
and the dispatch is refused without naming a cause. For the one capability
this package ships on its own, `workspace\grants.json` reads:

```json
[
  { "actor": "employee.id",
    "asset": { "namespace": "filesystem", "name": "read-file", "version": "1.0.0" },
    "permissions": ["filesystem.read"], "policy_refs": ["filesystem-read-policy"],
    "approval_ref": "CHANGE-1234" }
]
```

Then ask the Agent to do something, and see what this Bridge has run:

```bat
aep-host ask --config host.json "files.read C:\...\workspace\notes.txt"
aep-host status --config host.json
```

A route resolves whether or not it may run. Installing a Skill or Workflow is
not permission to execute it: a dispatch is refused unless `grants.json` names
the actor, the capability, its required permissions and policy, and an approval
reference when the capability's policy asks for one.

When the shared platform has told this Bridge what its members chose, that
arrives as `workspace\authorization.json` and replaces `grants.json`; having
both is refused. Only the Workflows and Skills named there are installed, and
the grants are derived from the tool selections against each capability's own
declaration, so a decision never has to name a permission.

`--namespace` selects which namespace a request addresses; pass `-Namespace`
at install time to record a default in `host.json`.

## Telegram (optional)

Add `workspace\telegram.json` with the bot's numeric senders mapped to platform
actors, and map the token's name to an environment variable in `host.json`:

```json
{ "credential": { "name": "telegram_bot" }, "bridge_id": "bridge-your-computer",
  "namespace": "engineering", "senders": [{ "sender_id": 123456789, "actor": "employee.id" }] }
```

```json
"credentials": [{ "secret": "telegram_bot", "environment_variable": "AEP_TELEGRAM_BOT_TOKEN" }]
```

Never put the token in a file. Set the environment variable for your Windows user
and run `aep-host telegram --config host.json`, which polls outbound only and needs
no inbound firewall rule. A sender that is not in the map is ignored.

On a company workstation, a mapped sender still has to be this Bridge's one bound
owner: a request on anybody else's behalf is refused. On a shared test workstation
the machine runs as a virtual member of its own, so a mapped sender's request runs
as that member and records who asked. **This file is therefore the access list for
a shared machine.** Disabling somebody on the shared platform does not close this
door — removing their entry here does — so offboarding has to include editing it.

## Shared platform (optional)

Once somebody who administers this device has bound it on the shared platform
and issued its access token, add the platform to `host.json` and map the
token's secret to an environment variable, exactly as for the Telegram token.
The value is never in a file.

```json
"platform": { "base_url": "https://platform.internal:8443",
              "token_id": "token-0123456789abcdef", "credential": { "name": "platform_token" } },
"credentials": [{ "secret": "platform_token", "environment_variable": "AEP_PLATFORM_TOKEN" }]
```

A platform beyond this computer is reached over `https`; plain `http` is
accepted on loopback only. Then:

```powershell
aep-host probe --config host.json   # does the platform still know this host as its member?
aep-host sync  --config host.json   # install what the member decided this device may run
aep-host jobs  --config host.json   # run the platform's jobs until Ctrl+C (--once to poll once)
```

`sync` writes `authorization.json` and the chosen Skill and Workflow manifests
under `workspace\assets\`, and refuses to run while a hand-written
`grants.json` is present: the two are different answers to one question, so
remove `grants.json` before the first sync. Everything is verified before
anything is written; a refusal leaves the workspace untouched.

When the platform cannot be reached, every command says so and changes
nothing: the token, the authorization and the installed assets stay where
they are, and `ask` keeps working with them. Only the platform itself telling
this host that its token is revoked or its binding withdrawn is a revocation,
and even then nothing local is deleted; being bound again is an action on the
platform.

## Weekly report preview (optional)

The GTM weekly report's first half runs here: the week's tracked items planned
against the workbook's scratch sheet, with nothing written. The workbook is
read without Excel, by a library the bundle already carries, so there is
nothing to install. Add the project board and the report's settings to
`host.json` and map the board's token like every other secret. The token
needs **both** project access and access to the repository the board's issues
live in: with only the first it reads the board and none of the notes on it,
which looks exactly like a week in which nobody wrote anything, and the run
refuses rather than report that.

```json
"integrations": {
  "github_project": { "owner": "your-account", "project_number": 1,
                      "credential": { "name": "board_token" } },
  "weekly_report": { "workbook_path": "C:/Users/you/OneDrive/Report/SDE_Weekly_Report.xlsx" }
},
"credentials": [{ "secret": "board_token", "environment_variable": "AEP_GITHUB_TOKEN" }]
```

`weekly_report` takes the source job's other settings with the same defaults
(`temp_sheet`, `week_style`, `jql`, `max_issues`, `markers`, the colours);
`aep-host doctor` reports whether the site, the secret, the library and the
workbook are all in place without contacting anything.

Then write the shipped manifests into the workspace:

```powershell
aep-host export-assets --out workspace\assets
```

and grant the capabilities in `workspace\grants.json` (or choose them on the
shared platform and `sync`). **Every one of them declares that it needs an
approval, the reads included, so every grant carries an `approval_ref`.** A
grant without one is not a weaker grant; it is no grant, and the run stops
with `permission_denied` at the first step. Use whatever reference your team
records the approval under.

```json
[
  { "actor": "employee.id",
    "asset": { "namespace": "weekly-report", "name": "resolve-window", "version": "1.0.0" },
    "permissions": ["weekly-report.plan"], "policy_refs": ["weekly-report-policy"],
    "approval_ref": "CHANGE-1234" },
  { "actor": "employee.id",
    "asset": { "namespace": "github", "name": "search-project", "version": "1.0.0" },
    "permissions": ["github.read"], "policy_refs": ["github-read-policy"],
    "approval_ref": "CHANGE-1234" },
  { "actor": "employee.id",
    "asset": { "namespace": "excel", "name": "read-scratch-sheet", "version": "1.0.0" },
    "permissions": ["excel.read"], "policy_refs": ["excel-read-policy"],
    "approval_ref": "CHANGE-1234" },
  { "actor": "employee.id",
    "asset": { "namespace": "weekly-report", "name": "plan", "version": "1.0.0" },
    "permissions": ["weekly-report.plan"], "policy_refs": ["weekly-report-policy"],
    "approval_ref": "CHANGE-1234" }
]
```

The four above are the preview. Writing needs a fifth, in the next section.
`membership.json` has to name you as well, or this Bridge admits nobody and
`doctor` says the resident Agent is pending. Then:

```powershell
aep-host ask --config host.json "weekly.preview 2026_31W"
```

A run that fails says how many steps finished, which is where it stopped:
none means the grants, one means the board, two means the workbook.

The answer is the plan: which rows would be upserted, which comment blocks
would be prepended in red, what was skipped and why, and a digest of the
scratch sheet as it stands. It is the same plan the source's `--dry-run`
printed.

### Writing it into the workbook

`weekly apply` runs the same four steps and then writes the plan through
Excel itself, so the machine needs Excel installed. The bundle already carries
the reader (`openpyxl`) and the Excel bridge (`pywin32`), so there is nothing
to install:

```powershell
aep-host ask --config host.json "weekly.apply 2026_31W"
```

Writing is the one side effect here, so `weekly-report/apply` is granted
separately from the four reads. It needs `excel.write` and its own policy
reference, and an `approval_ref` like every other grant:

```json
{ "actor": "employee.id",
  "asset": { "namespace": "weekly-report", "name": "apply", "version": "1.0.0" },
  "permissions": ["excel.write"], "policy_refs": ["weekly-report-write-policy"],
  "approval_ref": "CHANGE-1234" }
```

Without it the plan is still made and only the write is refused, so
`weekly preview` keeps working on a host that may not write.

Before it writes, it backs the workbook up, copies it somewhere your sync
client is not watching, and **checks the scratch sheet is still the one the
plan was made against** — if somebody edited it in between, the run is
refused rather than written. A run that does not finish leaves the real
workbook exactly as it was and tells you where the staged copy is. Close the
workbook first: a file Excel has open is refused before anything is copied.

Two things to expect the first time. Every run retires last week's marks
across the whole scratch sheet before making this week's, so a red `Comments`
cell or a tinted `Key` cell you applied *by hand* loses its colour — never its
text. And your own `Status` colours are left alone; only cells holding exactly
the job's own pink are cleared.

### The weekly mail

`weekly mail` reads the board, counts the week's effort and saves a draft in
Outlook. **It never sends.** Nothing in this platform can send a mail: the
adapter has no call that delivers one, and a test reads its source to keep it
that way. A person opens the draft, reads it, and presses send, or does not.

```powershell
aep-host ask --config host.json "weekly.mail 2026_31W"
```

It does not read or write the workbook, so it is its own workflow and its own
grant: somebody who may draft the mail need not be somebody who may write the
team's file.

```json
{ "actor": "employee.id",
  "asset": { "namespace": "weekly-report", "name": "mail", "version": "1.0.0" },
  "permissions": ["outlook.draft"], "policy_refs": ["weekly-report-mail-policy"],
  "approval_ref": "CHANGE-1234" }
```

What the mail says, and what it counts:

- **Effort is tickets, not hours.** This project records no worklog and has no
  points field, so there are no hours to weigh. The mail says that on its face.
- **Only what somebody worked on.** An item whose timestamp moved because a
  field was edited is not work, so it is left out — and the ones left out are
  *named*, not just subtracted. A week that matched sixty-three items and
  counted four is either right or badly wrong, and only a reader told both
  numbers can tell which. Set `"mail_requires_activity": false` under
  `weekly_report` to count everything the week matched instead; the mail then
  says which question it answered.
- **A ticket naming several instruments counts once under each**, so the
  instrument totals add up to more than the number of tickets. That is
  deliberate and the mail says so rather than hiding it.
- The pie chart is drawn by this package itself, with no charting library, so
  it needs nothing installed and adds nothing to this bundle. Its legend is the
  table beneath it, with a colour per row: the labels stay selectable text and
  every number survives if the reader's mail client blocks images.

Who it is addressed to is configuration, and empty is the safer default — the
draft then has no recipients and the person who opens it fills them in:

```text
"weekly_report": {
  "mail_to": ["sde-team@example.com"],
  "mail_cc": [],
  "mail_subject_prefix": "GTM weekly report"
}
```

**This drafter has not yet been run against a real Outlook by anyone.** Like
the workbook writer before it, it is written to the documented object model
and is unproven until you run it.

This writer has now been run against a real team workbook once, on
2026-09-24, and an earlier build of it renamed the previous week's sheet
instead of adding this week's. That defect is fixed and pinned by a test, and
the run takes a backup before touching anything — but try it on a copy first
and compare the result with the old Host Bridge's.

## A model (optional)

Without one, this Agent matches commands and runs Workflows. It does not
reason about anything else: a request that matches no installed command is
answered with `needs_input`, not a guess. That is the whole behaviour of every
host before this section existed, and it is a reasonable one to keep.

With one, a request that matches nothing is shown to a model along with the
Skills installed *here*, and the model may pick one of them. It can pick only
what is installed: a name it invents is refused, and the run never starts.

A company's LiteLLM gateway serves an OpenAI-shaped API, which is what this
speaks. In `host.json`:

```json
"models": {
  "catalog": {
    "endpoints": [
      { "alias": "company",
        "provider": "openai_compatible",
        "model": "gpt-5.5",
        "base_url": "https://your-gateway.example/api",
        "credential": { "name": "llm_gateway_token" },
        "capabilities": {
          "reasoning": "high", "tool_calling": true, "structured_output": true,
          "streaming": true, "max_context_tokens": 128000 } }
    ]
  },
  "routing_alias": "company",
  "allow_remote_models": true
}
```

and, beside `credentials`, the variable that holds the key:

```json
{ "secret": "llm_gateway_token", "environment_variable": "AEP_LLM_TOKEN" }
```

**The key never goes in this file.** It goes in that environment variable,
exactly like the board token. `doctor` reports the endpoint, and reports the
variable by name when it is not set — never its value.

### `allow_remote_models` is a line somebody has to write

An endpoint's `local` flag says where the model *runs*. A company gateway runs
inside the company but not on this computer, so it is not local, and this host
refuses to route through it until the configuration says `allow_remote_models`.

That line is the statement that **an engineer's words leave this computer** for
that gateway. It is not something this platform should decide quietly on
anybody's behalf, so there is no default that turns it on. A model running on
this machine — an Ollama on `localhost` — needs no such line, because nothing
leaves.

`routing_alias` may also be left out. The catalog is then configured for
capabilities to use and nothing chooses what to run, which is a reasonable
thing to want.

## Without typing commands

Everything above is one `aep-host` command, and nobody runs a weekly job that
way for long. Four things in this folder do it for you. They find the
installation themselves; if you installed somewhere else, edit the `ROOT` line
at the top of each.

| Double-click | What it does |
| --- | --- |
| `chat.cmd` | Opens a window and lets you talk to the Agent on this computer. |
| `weekly-preview.cmd` | Runs the dry run and prints the plan. Writes nothing. |
| `weekly-apply.cmd` | Asks, then writes the plan into the workbook. |
| `weekly-mail.cmd` | Saves this week's mail as a draft in Outlook. Sends nothing. |

`weekly-preview.cmd 2026_39W` names a week; with no argument it is this week.

`chat.cmd` is the same Agent the command line and Telegram reach, with the
same grants and the same refusals — a window is an ingress, not a shortcut
past anything. Type a command such as `weekly.preview 2026_39W` and the plan
comes back in the window. It takes one request at a time, because two runs at
once would be two runs against the one workbook. A console window stays open
behind it; that is where a configuration problem is reported.

### On a schedule

```powershell
.\schedule-weekly.ps1                  # every Friday at 16:00
.\schedule-weekly.ps1 -DayOfWeek Monday -At 09:00
.\schedule-weekly.ps1 -Remove
```

This registers a Windows scheduled task that runs the **preview** and writes
nothing. Writing stays something a person does, because it changes the team's
workbook. The task runs as you, not as SYSTEM: the workbook, the board token
and Excel all belong to your account, and a task running as SYSTEM would see
none of them — so it runs when you are signed in.

## Remove

`uninstall.cmd` shows what it would remove. `uninstall.cmd -Apply` removes only the
versioned preview installation. The extracted bundle and exported enrollment JSON
remain until you remove them yourself.
