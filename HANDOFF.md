# Handoff — Codex remote-test loop is live; Python test setup awaiting review

Updated: 2026-09-26 (Asia/Taipei).
Branch: `fix/codex-action-test-environment`.
Base: `main` at `5dc6dffa3f144cd8d28f58d382157ed56cfd22a5`.

## Completed

- PR #105 is merged. It supplies the governed `codex-fix` Issue-label loop in
  `.github/workflows/codex-remote-test-fix.yml`, its Hermes Issue template,
  documentation and static contract tests.
- The live pipeline was exercised on Issue #106. After the repository secret
  name and API billing were corrected, GitHub Actions run `36159459225`
  completed successfully and posted the five-section Codex result to the same
  Issue. The result correctly made no source edit: the reported commit and
  artifacts were unavailable and the evidence was insufficient for a narrow
  implementation fix.
- This branch adds a fixed Python 3.12 pre-Codex environment: checkout with
  credentials disabled, `actions/setup-python@v5`, then the repository-owned
  `python -m pip install -e ".[dev,office]"`. This is independent of Issue
  content, so untrusted remote evidence cannot select commands or packages.
- The Codex Action remains workspace-only, no-network and without GitHub write
  permission. The separate comment job still owns the sole `issues: write`
  permission. No push, PR creation or merge is automated.
- The workflow contract test now proves the declared Python setup and install
  occur before `openai/codex-action@v1`; the remote-loop documentation records
  this boundary.

## In Progress

- Create, review and merge the small PR for the Python test-environment
  preparation. No code or platform contract changes are included.

## Remaining

- After the PR merges, remove `codex-fix`, add an evidence-complete dummy
  report to Issue #106, then apply `codex-fix` again. Confirm the Action runs
  the named pytest subset rather than failing before collection.
- Hermes should attach or quote bounded, relevant artifacts and identify the
  actual tested commit. Multiple unrelated failures in one Issue make root
  cause analysis weaker, even though the full body is preserved as evidence.
- Existing product work is unchanged: E2E-01's real company-host DUT validation
  remains owner-run and pending; CI remains inert.

## Architecture decisions made

- The remote feedback loop is a governed integration entry point. It does not
  alter Registry/Bridge boundaries, execution authorization or asset contracts.
- Issue content remains data, never executable instruction. Fixed environment
  preparation is repository-owned and runs before the prompt is built.
- A successful local test run is supporting evidence only. Hermes retains
  responsibility for rebuild and remote/hardware retest; human review retains
  merge authority.

## Exact verification commands and results

Windows / Python 3.12:

```text
.venv\Scripts\python.exe -m pytest tests\test_codex_remote_test_workflow.py -q -p no:cacheprovider
4 passed in 0.02s

.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_browser.py -p no:cacheprovider --basetemp .scratch\pytest-codex-test-env-full
1293 passed, 4 skipped in 33.15s

.venv\Scripts\ruff.exe check .
All checks passed

.venv\Scripts\ruff.exe format --check .
265 files already formatted

.venv\Scripts\mypy.exe src
Success: no issues found in 130 source files

.venv\Scripts\python.exe -m build --no-isolation --outdir .scratch\dist-codex-test-env
Successfully built sdist and wheel

.venv\Scripts\python.exe -m pip check
No broken requirements found

PyYAML safe-load of .github/workflows/codex-remote-test-fix.yml
YAML parsed

git diff --check
passed
```

The four skips are existing Windows link-privilege and IPv6-loopback cases.
The default `dist` output file was locked by another Windows process, so the
same build was run successfully to the ignored `.scratch\dist-codex-test-env`
directory. No Ubuntu or Python 3.11 validation was run locally, per owner
instruction.

## Known issues

- A remote report without the checked-out commit or accessible artifact content
  should result in analysis and requested evidence, not a guessed code change.
- The workspace changes Codex makes are intentionally ephemeral; the Issue
  comment provides the human-reviewable change description. The workflow never
  commits, pushes, creates a PR or merges.
- `.claude/` is user-owned local state. Do not commit, modify or remove it.

## Next Recommended Action

Review and merge the pending test-environment PR. Then rerun Issue #106 using
one focused, reproducible remote failure with the exact commit, bounded error
excerpt, expected/actual result and safe artifact references.
