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
