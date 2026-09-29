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

Hermes creates or updates a failure Issue, records complete sanitized evidence,
reads the result back, then applies `codex-fix`. GitHub accepts that label only
when the labeler exactly matches `HERMES_GITHUB_BOT_USER` and
`CODEX_EXECUTION_MODE` is `local-worker`.

The queue workflow turns the Issue into a `codex-local-request/v1` JSON payload
inside a comment authored by `github-actions[bot]`. The payload contains a
default-branch SHA, the last ten bounded comments from the configured Hermes
account, and a SHA-256 fingerprint. Reapplying the label to unchanged evidence
does not create another request. A new Hermes evidence comment changes the
fingerprint and permits exactly one new attempt.

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

The workflows create the four `codex-local-*` labels when first used. Keep
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

## Hermes failure payload

Hermes should report these fields in the Issue body before adding `codex-fix`:

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

Never include access tokens, passwords, private keys, private file contents or
other secret values in Issues, comments or artifacts.

## Reproducible dummy test

1. Confirm the repository variables are set and the scheduled task is running.
2. Create a harmless failure Issue from the Hermes template without `codex-fix`.
3. Have the configured Hermes bot add `codex-fix` last.
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

Editing an Issue does not trigger Codex. To submit changed evidence, Hermes removes
and reapplies `codex-fix`; the changed fingerprint becomes one new request.
