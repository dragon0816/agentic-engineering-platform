# Remote testing to Codex feedback loop

This repository can turn a failure from a remote Hermes Testing Agent into a
bounded Codex analysis and, where evidence supports a narrow repair, a Draft
pull request. A human still reviews and merges every code change, and Hermes
remains the authority for the remote hardware or software retest.

```text
Hermes FAIL
    -> GitHub Issue + codex-fix
    -> GitHub Action
    -> Codex analysis and workspace fix
    -> validated Draft PR (when evidence supports a narrow repair)
    -> human review
    -> CI build
    -> Hermes retest
```

## Trigger and result

`.github/workflows/codex-remote-test-fix.yml` listens only for an Issue
`labeled` event. The analysis job runs only when the newly applied label is
exactly `codex-fix`. Editing, commenting on, closing, reopening, or applying a
different label to an Issue does not invoke Codex.

The workflow checks out the current default-branch commit, installs the
repository-declared `.[dev,office]` test dependencies with Python 3.12, and
then invokes `openai/codex-action@v1`. This fixed setup command is independent
of Issue content, so remote test evidence cannot choose packages or commands.
It passes the repository and checked-out commit, the Issue number, title and
body, and these optional Hermes fields:

- `Commit:`
- `Build:` or `Package Version:`
- `Machine:` or `Test Machine:`
- `Test:` or `Failed Test:`
- `Expected:` or `Expected Result:`
- `Actual:` or `Actual Result:`
- `Failure Stage:`, `Failure:`, `Error:`, or `Failure Information:`
- `Artifacts:`, `Logs:`, or `Log Paths:`

The same Issue receives a comment with `Codex Analysis`, `Root Cause`,
`Changes`, `Local Test Result`, `Next Action`, and `Draft PR`. Codex marks a
result `Fix Ready` only when the evidence supports a narrow repair, its local
tests pass, and it can provide a complete unified diff. The delivery job then
validates that diff and opens a Draft PR. A result without sufficient evidence,
a passing local test, or a valid restricted diff produces analysis only.

The workflow never merges to `main`. Every Draft PR requires ordinary human
review, its normal CI checks, and a Hermes rebuild/retest before it can merge.

Remote artifacts are not downloaded automatically. Put a bounded log excerpt
in `Failure Information:` and provide repository paths or artifact links under
`Artifacts:`. Codex can inspect a path already present in the checkout. A link
is reported as evidence for the human and Hermes follow-up because the Codex
workspace has no network access.

## Automatic Draft PR delivery

Codex runs in the analysis job without GitHub write permission or a persisted
checkout credential. It may edit and test its temporary workspace, but it can
only send a structured result and a bounded unified diff to the next job.

The separate delivery job receives GitHub `contents: write` and
`pull-requests: write` permissions. It does **not** execute the proposed code,
tests, or any command from the Issue or Codex output. It accepts a patch only
when all of these checks pass:

- Codex set `Fix Ready` to `true`.
- The patch is at most 60,000 characters with one to twelve standard Git diff
  headers.
- Every changed path is unchanged in name and lies under `src/`, `tests/`, or
  `docs/`; binary changes, deletions, renames, workflow/configuration changes,
  and path traversal are rejected.
- `git apply --check` and `git diff --check` pass without running the patched
  code.

The job creates a uniquely named `codex/remote-test-issue-...` branch, commits
the validated diff without repository hooks, and opens a GitHub Draft PR. It
does not mark the PR ready, approve it, bypass branch protection, or merge it.
If delivery fails, the Issue comment records that no Draft PR was created and
the workflow run is the evidence for a human to inspect.

## Security boundary

GitHub Issue content is untrusted. The workflow reads it through the GitHub
event object, removes control characters, applies size limits, serializes it as
JSON, and marks it as evidence rather than instructions. It is never inserted
into a shell command.

The Codex job follows the official action's secure edit configuration:

- `permission-profile: ":workspace"` permits repository workspace edits while
  denying network access;
- `safety-strategy: drop-sudo` removes elevated access before Codex starts;
- checkout uses `persist-credentials: false`;
- a fixed pre-Codex step installs only the repository's declared test
  dependencies using Python 3.12; it does not use any Issue-provided command
  or package name;
- the job has only `contents: read` and `issues: read` GitHub permissions;
- Codex is the last step in its job;
- the isolated delivery job has `contents: write` and `pull-requests: write`,
  but no `OPENAI_API_KEY`, no Codex workspace, and never executes patch code;
- a final separate job with only `issues: write` posts the structured result
  and has neither the API key nor the Codex workspace.

By default, `openai/codex-action` accepts a trigger only from a user with write
access to the repository. Do not configure `allow-users: "*"` or permit every
bot. If Hermes labels Issues through a GitHub App bot whose repository access
cannot be established by the action, set the optional repository variable
`HERMES_GITHUB_BOT_USER` to that one exact bot login, for example
`hermes-testing[bot]`. The workflow passes only that exact value to
`allow-bot-users`.

Labeling is the approval boundary. Configure Hermes so it creates or updates
the complete Issue first and applies `codex-fix` last. Grant its service account
only the repository access needed to manage Issues. Branch protection and
required human review remain responsible for merge authorization.

## GitHub configuration

1. In **Settings -> Secrets and variables -> Actions -> Secrets**, create the
   repository secret `OPENAI_API_KEY`. Never put the key in an Issue, variable,
   workflow input, artifact, or source file.
2. Create the repository label `codex-fix`.
3. Ensure the human or Hermes service account that applies the label has write
   access to the repository. If an exact GitHub App bot allowlist is required,
   add the repository variable `HERMES_GITHUB_BOT_USER` as described above.
4. Keep GitHub Actions enabled and set **Settings -> Actions -> General ->
   Workflow permissions** to **Read and write permissions**, so the isolated
   delivery job can create a branch and Draft PR. Keep branch protection and
   required human review enabled for `main`.

## Hermes Issue format

Hermes may use `.github/ISSUE_TEMPLATE/hermes-remote-test-failure.md` or send
the equivalent GitHub Issues API payload. Apply the label after the final body
has been written.

```json
{
  "title": "[Test Failure] wifi8_tx_verify timed out",
  "body": "[Test Failure]\n\nCommit: abc123\n\nBuild: 2.0.31\n\nMachine: RF-LAB-PC-02\n\nTest: wifi8_tx_verify\n\nExpected:\nTX_START_OK\n\nActual:\nTimeout after 10 seconds\n\nFailure Stage:\nDUT_CONTROL\n\nFailure Information:\nDriver stopped responding after TX start.\n\nReproducible:\ntrue\n\nArtifacts:\n- test_result.json\n- dut.log\n- instrument.log",
  "labels": ["codex-fix"]
}
```

The corresponding human-readable body is:

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

Never include API keys, access tokens, passwords, private keys, or other secret
values in the Issue or its artifacts.

## Test with a dummy Issue

1. Complete the GitHub configuration above on the default branch.
2. Open a new Issue with the template. Use a harmless failed test name and a
   body that points to an existing unit test or intentionally describes an
   evidence-insufficient remote failure.
3. Create the Issue without `codex-fix`, then add `codex-fix` from a
   write-authorized account. Adding it last proves that ordinary Issue creation
   and edits do not trigger Codex.
4. Open **Actions -> Codex remote test failure analysis** and inspect the run.
5. Confirm the same Issue receives one comment containing `Codex Analysis`,
   `Root Cause`, `Changes`, `Local Test Result`, `Next Action`, and `Draft PR`.
6. For insufficient evidence, confirm no branch or Draft PR is created. For a
   focused failure whose repair passes local tests and produces a restricted
   complete diff, confirm one Draft PR is created. Review it normally, let CI
   build it, and send that build back to Hermes for the remote retest. Never
   merge it automatically.

To rerun after adding evidence, remove `codex-fix`, update the Issue, and apply
the label again. Updating an Issue while the label is already present does not
emit another matching `labeled` event.

## References

- [Official Codex Action README](https://github.com/openai/codex-action/blob/main/README.md)
- [Official Codex Action security guidance](https://github.com/openai/codex-action/blob/main/docs/security.md)
- [Codex permissions and sandboxing](https://learn.chatgpt.com/docs/permissions)
