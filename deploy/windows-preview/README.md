# Company Bridge host — Windows technical preview

This preview proves a credential-free, per-user installation and company-device
configuration before the shared-platform enrollment transport exists. It installs
a resident Agent that runs the Skills and Workflows you place in its workspace.

It ships the capabilities the GTM weekly report needs — a bounded read of a file
inside the workspace, a Jira search, a workbook reader and the workbook writer —
and the Skill and Workflow that run them. None of that does anything until you
configure a Jira site and a workbook under `integrations`; `aep-host doctor`
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

The GTM weekly report's first half runs here: the week's Jira issues planned
against the workbook's scratch sheet, with nothing written. The workbook is
read without Excel, by a library the bundle already carries, so there is
nothing to install. Add the Jira site and the report's settings to
`host.json` and map the Jira API token like every other secret:

```json
"integrations": {
  "jira": { "base_url": "https://your-site.atlassian.net", "email": "you@company.com",
            "credential": { "name": "jira_token" } },
  "weekly_report": { "workbook_path": "C:/Users/you/OneDrive/Report/SDE_Weekly_Report.xlsx" }
},
"credentials": [{ "secret": "jira_token", "environment_variable": "AEP_JIRA_TOKEN" }]
```

`weekly_report` takes the source job's other settings with the same defaults
(`temp_sheet`, `week_style`, `jql`, `max_issues`, `markers`, the colours);
`aep-host doctor` reports whether the site, the secret, the library and the
workbook are all in place without contacting anything. Then write the shipped
manifests into the workspace and grant the four read capabilities in
`grants.json` (or choose them on the shared platform and `sync`):

```powershell
aep-host export-assets --out workspace\assets
aep-host ask --config host.json "weekly.preview 2026_31W"
```

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

Writing is a side effect, so the capability requires an approval: the grant
for `weekly-report/apply` must carry an `approval_ref` (or the member's
decision on the shared platform must). Without one the plan is still made and
the write is refused.

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

**This writer has not yet been run against a real workbook by anyone.** Try it
on a copy first and compare the result with the old Host Bridge's.

## Remove

`uninstall.cmd` shows what it would remove. `uninstall.cmd -Apply` removes only the
versioned preview installation. The extracted bundle and exported enrollment JSON
remain until you remove them yourself.
