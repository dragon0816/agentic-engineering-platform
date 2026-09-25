# Remote testing to Codex feedback loop

This repository can turn a failure from a remote Hermes Testing Agent into a
bounded Codex analysis. It automates diagnosis and preparation of a minimum
fix; a human still reviews and merges any code change, and Hermes remains the
authority for the remote hardware or software retest.

```text
Hermes FAIL
    -> GitHub Issue + codex-fix
    -> GitHub Action
    -> Codex analysis and workspace fix
    -> human-reviewed fix/PR
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

The same Issue receives a comment with five sections: `Codex Analysis`, `Root
Cause`, `Changes`, `Local Test Result`, and `Next Action`. A fix prepared in the
runner workspace is ephemeral. The comment identifies the affected files and
change so a human can review it and prepare a branch, commit, and pull request.
The workflow never pushes, opens a PR, or merges to `main`.

Remote artifacts are not downloaded automatically. Put a bounded log excerpt
in `Failure Information:` and provide repository paths or artifact links under
`Artifacts:`. Codex can inspect a path already present in the checkout. A link
is reported as evidence for the human and Hermes follow-up because the Codex
workspace has no network access.

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
- a separate job with only `issues: write` posts the structured result and has
  neither the API key nor the Codex workspace.

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
4. Keep GitHub Actions enabled. Keep branch protection and required human
   review enabled for `main`.

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
   `Root Cause`, `Changes`, `Local Test Result`, and `Next Action`.
6. Confirm no branch, pull request, or merge was created. If the comment
   recommends code changes, review the named changes, prepare a normal PR, let
   CI build it, and send that build back to Hermes for the remote retest.

To rerun after adding evidence, remove `codex-fix`, update the Issue, and apply
the label again. Updating an Issue while the label is already present does not
emit another matching `labeled` event.

## References

- [Official Codex Action README](https://github.com/openai/codex-action/blob/main/README.md)
- [Official Codex Action security guidance](https://github.com/openai/codex-action/blob/main/docs/security.md)
- [Codex permissions and sandboxing](https://learn.chatgpt.com/docs/permissions)
