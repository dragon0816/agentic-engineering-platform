# Remote testing and local Codex repair loop

The repair loop uses GitHub as the durable queue and audit record, a trusted
development computer for Codex, and the company computer for Hermes validation.

```text
Hermes FAIL
  -> GitHub Issue + codex-fix
  -> GitHub Actions writes codex-local-request/v1
  -> local Codex worker (ChatGPT Pro login)
  -> branch + Draft PR + CI
  -> GitHub Actions writes hermes-next-action/v1
  -> Hermes exact-SHA retest
  -> owner reviews and merges
```

No automatic merge is permitted. GitHub-hosted runners do not receive ChatGPT
credentials and no longer invoke `openai/codex-action`. The local worker uses the
developer's existing `codex login` session; API-key billing is not part of this
path.

## Trust boundaries

Hermes creates or updates a failure Issue, then posts one fixed
`hermes-failure/v1` JSON comment containing the exact commit it tested. It reads
the comment back before applying `codex-fix`. GitHub accepts that label only when
the labeler exactly matches `HERMES_GITHUB_BOT_USER` and
`CODEX_EXECUTION_MODE` is `local-worker`.

The queue workflow turns the Issue into a `codex-local-request/v1` JSON payload
inside a comment authored by `github-actions[bot]`. Its base SHA comes only from
the latest valid failure payload authored by the configured Hermes account. The
whole payload is fingerprinted, so reapplying the label to unchanged evidence
does not create another request. A failed PR retest names that PR's exact head
SHA, preserving the previous repair in the next iteration.

The local worker accepts only that schema and author. Issue title and body stay
untrusted evidence. They never supply shell commands, test commands, branches,
paths or Codex instructions. Before `codex exec` starts, the worker removes
`GH_TOKEN`, `GITHUB_TOKEN`, `AEP_GITHUB_TOKEN` and `OPENAI_API_KEY` from its
environment. Codex runs with `workspace-write`; it cannot deliver GitHub changes.

After Codex exits, deterministic worker code checks the changed-path allowlist,
runs the repository's fixed pytest/lint/type-check baseline, commits and pushes a
branch, and opens a Draft PR. The local repair allowlist is `src/`, `tests/`,
`docs/`, and `HANDOFF.md`. Workflow, secret, hook and dependency changes require
a normal human-authored PR.

The handoff workflow accepts only a same-repository Draft PR from
`CODEX_LOCAL_WORKER_USER`, with the worker marker and branch prefix. It writes a
bot-authored `hermes-next-action/v1` payload containing the exact PR head SHA and
adds `hermes-retest-requested`. Hermes must execute its fixed profile, never PR or
Issue prose. A passing Hermes result asks the human reviewer to merge; it never
merges by itself.

## Optional shared Validation/Coding coordination group

A dedicated Coding Agent bot and Validation Agent bot may share one Telegram group to
remove the owner's manual copy-and-paste step. Telegram does not replace the
GitHub queue:

```text
Validation Agent writes implementation evidence/result to GitHub
  -> Validation bot posts one fixed event in the shared group
  -> Coding bot verifies the referenced Issue in GitHub
  -> Coding bot posts one terminal acknowledgement
  -> Coding Worker reports running/evidence-required/failed/PR-ready
     states to the same group
```

The owner starts the first validation with its scope and expected result,
coordinates exceptions in the group and retains merge authority. Hermes is the
current Validation Agent and Local Codex is the current Coding Agent. Those are
replaceable implementations of the roles; the coordination schema does not make
either product a permanent architecture component.

The Coding bot accepts only `/status` from the configured owner. It accepts
only `aep-agent-coordination/v1` JSON from the configured Validation bot in the exact
configured chat. General chat, instructions embedded in messages and commands
from either bot have no execution effect. Events require `hop=0`; acknowledgements
use `hop=1`, are terminal and must never be answered. The durable Telegram offset
and event ids prevent replay after process restart. A poll handles at most 25
updates and remembers at most 200 event ids.

Example Hermes group message after the corresponding GitHub evidence is already
present:

```json
{"schema":"aep-agent-coordination/v1","producer":"validation-agent","event_id":"hermes-132-validation-failed-001","event":"validation_failed","repository":"dragon0816/agentic-engineering-platform","issue":132,"request_id":"deployment-company-agent-36591676672","target_sha":"0123456789abcdef0123456789abcdef01234567","hop":0}
```

The bot replies with `aep-agent-coordination-ack/v1` after it can read that Issue.
The reply contains current GitHub state/labels and `hop=1`. Hermes must ignore
that acknowledgement and every `aep-telegram-worker-event/v1`; otherwise two bots
could create a reply loop.

Mechanism problems do not masquerade as implementation failures and do not need
a GitHub Issue. The Validation bot may send this bounded record instead:

```json
{"schema":"aep-agent-coordination/v1","producer":"validation-agent","event_id":"mechanism-company-agent-001","event":"mechanism_blocked","repository":"dragon0816/agentic-engineering-platform","issue":null,"request_id":"deployment-company-agent-36591676672","target_sha":"0123456789abcdef0123456789abcdef01234567","mechanism":{"code":"VALIDATION_POLLER_BLOCKED","summary":"The fixed profile did not start.","expected":"Consume the trusted request once and run the profile.","observed":"The poller stayed paused after setup.","evidence_refs":["hermes://runs/example/result.json"],"requested_response":"diagnosis"},"hop":0}
```

The Coding bot persists the bounded mechanism record and acknowledges
`coding_agent_review_required`. It does not run the text as code or a Codex
prompt. A later bounded handler may automate diagnosis. If the diagnosis needs
a repository change, the Validation Agent creates the normal typed GitHub Issue;
only that path may start implementation work.

Configure the four optional entries in the development computer's ignored
`.env/local.yaml`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_USER_ID`,
`TELEGRAM_HERMES_BOT_ID` and `TELEGRAM_CONTROL_CHAT_ID`. All ids are numeric; a
group chat id is normally negative. All four blank disables Telegram while the
GitHub worker continues. Both bots must be members of the configured group, and
Telegram/BotFather settings must permit the bots to receive the fixed messages
addressed to them. Use a dedicated bot token so another long-polling process does
not cause Bot API HTTP 409 conflicts.

## One-time GitHub configuration

After this implementation is merged, create these repository variables:

| Variable | Value |
|---|---|
| `CODEX_EXECUTION_MODE` | `local-worker` |
| `CODEX_LOCAL_WORKER_USER` | GitHub login used by this development computer, currently `dragon0816` |
| `HERMES_GITHUB_BOT_USER` | exact Hermes GitHub bot login |
| `HERMES_MERGE_REVIEWER` | GitHub login that reviews the final PR |

The workflows create the five `codex-local-*` labels when first used. Keep
`OPENAI_API_KEY` temporarily while the local path is tested, then delete that
repository secret after one dummy request reaches a Draft PR and Hermes receives
its exact-SHA request.

## One-time development-computer setup

Use Python 3.12. Install the repository and development dependencies, authenticate
Codex with the ChatGPT account, and create the ignored credential file:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,office]"
codex login
codex login status
Copy-Item .env\example.yaml .env\local.yaml
notepad .env\local.yaml
```

Put the development computer's fine-grained GitHub token in `GH_TOKEN`. Limit it
to this repository with Metadata read, Contents read/write, Issues read/write and
Pull requests read/write. Do not put the ChatGPT login or a live OpenAI API key in
the YAML file. The runner configures Git to use GitHub CLI's credential helper;
the token remains in the outer deterministic process and is removed from the
Codex subprocess environment.

Test one poll in the foreground:

```powershell
.\scripts\run-local-codex-worker.ps1 -Once
```

When that succeeds, install the per-user worker at logon:

```powershell
.\scripts\install-local-codex-worker-task.ps1
Get-ScheduledTask -TaskName "AEP Local Codex Worker"
```

The task runs one resident process which polls every 60 seconds. Durable request
state and temporary worktrees are under
`%LOCALAPPDATA%\AgenticEngineeringPlatform\codex-worker`. A failed workspace is
kept for diagnosis; a successfully delivered workspace is removed.

When the optional Telegram configuration is complete, that same resident process
also polls the dedicated coordination bot. There is no inbound port and no second
Scheduled Task. Telegram errors are logged once per changed failure code and do
not stop GitHub polling.

The worker resolves a native `codex.exe` or Windows `codex.cmd` entry point
before starting a repair; a PowerShell-only shim is not a valid subprocess
boundary. A successful Codex process must also write the requested structured
result file. Missing executable and missing-result failures remain terminal and
visible instead of being mistaken for an implementation result.

An operator may retry the same trusted request by re-adding
`codex-local-queued` after correcting the worker environment. The worker reuses
the preserved worktree only when its tracked and untracked Git status is clean,
and claiming the retry removes the queue label. A second failure therefore
stops again instead of polling forever.

## Hermes failure payload

The Issue body remains human-readable:

```text
[Test Failure]

Commit: abc123
Build: 2.0.31
Machine: RF-LAB-PC-02
Test: wifi8_tx_verify

Expected:
TX_START_OK

Actual:
Timeout after 10 seconds

Failure Stage:
DUT_CONTROL

Reproducible:
true

Artifacts:
- test_result.json
- dut.log
- instrument.log
```

Before adding `codex-fix`, the configured Hermes account must add and read back
this machine-readable comment. All fields are required; `target_sha` is the exact
commit installed and tested, and `failure_fingerprint` is Hermes' SHA-256 digest
of the normalized failure evidence.

```text
## Hermes Failure Evidence

<!-- {"schema":"hermes-failure/v1","producer":"hermes-testing-agent","request_id":"hermes-rf-lab-20260929-001","repository":"dragon0816/agentic-engineering-platform","source_issue":130,"target_sha":"0123456789abcdef0123456789abcdef01234567","build":"2.0.31","machine":"RF-LAB-PC-02","bridge":"bridge-tp401555","actor":"leo.chi","profile":"aep-company-agent-integration-v1","test":"wifi8_tx_verify","stage":"DUT_CONTROL","expected":"TX_START_OK","actual":"Timeout after 10 seconds","failure_code":"DUT_TIMEOUT","failure_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","artifacts":["test_result.json","dut.log","instrument.log"],"reproducible":true} -->
```

Never include access tokens, passwords, private keys, private file contents or
other secret values in Issues, comments or artifacts.

## Reproducible dummy test

1. Confirm the repository variables are set and the scheduled task is running.
2. Create a harmless failure Issue from the Hermes template without `codex-fix`.
3. Have the configured Hermes bot post/read back `hermes-failure/v1`, then add
   `codex-fix` last.
4. Confirm Actions posts one `Codex Local Request` comment and adds
   `codex-local-queued`.
5. Within about 60 seconds, confirm the worker changes the label to
   `codex-local-running`.
6. For sufficient evidence, confirm a `codex/remote-test-issue-*` Draft PR is
   opened and CI starts. If Codex names specific missing evidence, confirm GitHub
   posts a bot-authored `collect_evidence` request for Hermes. A failure that
   cannot be resolved by bounded evidence stops with `codex-local-failed`.
7. Confirm the Draft PR receives a bot-authored `Hermes Next Action` JSON comment
   with its exact head SHA and `hermes-retest-requested`.
8. Hermes retests that SHA. A pass notifies the configured reviewer, who decides
   whether to merge.

Editing an Issue does not trigger Codex. To submit changed evidence, Hermes posts
a new payload with the exact SHA it tested, removes `codex-fix`, then reapplies
it; the changed fingerprint becomes one new request.

When Codex requests bounded follow-up evidence, Hermes may add an optional
`evidence_details` object to the next `hermes-failure/v1` payload. The object is
accepted only from the configured Hermes identity and must contain the fixed
artifact identity, request/profile identity, sanitized SOP and Knowledge
invocations, their complete JSON results, and preserved passing evidence. Both
GitHub Actions and the local worker reject extra top-level fields, mismatched
SHAs or request IDs, non-JSON values, excessive nesting, oversized collections,
and payloads over 48,000 JSON characters. The content remains untrusted evidence
inside the Codex prompt and never supplies executable commands.
