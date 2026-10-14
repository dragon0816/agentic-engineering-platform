# Workflow 13 source contract and first AEP slice

Source: read-only `dragon0816/rs_workflow_system` at
`896046e8fe2170d21f9213e56e5ce2f93c05ba43`, especially
`host-bridge/jobs/release_package.py`, `_release_yaml.py`,
`tests/test_release_yaml.py`, `tests/test_release_dry_run_plan.py`, and
`workflows/13_release_package.json`. Strategy: **PRESERVE + ADAPT**. The
original repository remains unchanged.

The original job takes `companyName`, `chipsetId`, `generalTestcaseVersion`,
`cmpKtOption`, optional per-run overrides and input files. It chooses or creates
`[company]_[chipset]_[info]` from a template branch, pins two requirements,
places selected files into `testplans`, `configurations` or singular `overlay`,
and renders a commented `release.yaml`. A missing `chipsetVersion` is resolved
from the newest published package first, with the readiness table as fallback.
The branch's current `VERSION` increments in base 16 per component, starting at
`0.0.1`; an explicit per-run version overrides that. A dry run prepares the
working copy but never commits or pushes. The job serializes access to the
shared working copy, never automatically retries an uncertain run, and requires
an explicit non-dry-run decision for commit/push. Source test coverage includes
the exact wording of the plain-language preview.

This first AEP slice ports the source's pure YAML/requirements/version/status
rules and runtime form hints. `plan_release` validates required values, branch
segments and bare local inbox names, computes file digests, and projects
`requirements.txt`, `release.yaml` and destination paths without writing.
`prepare_dry_run` writes those files only to an existing Git checkout within an
explicit allowed root, checks source digests and destinations before writing,
and never invokes Git, a network service, commit or push. An isolated temporary
Git repository test verifies this behavior. The plan deliberately requires an
explicit chipset version and refuses upload sets until those read/transfer
capabilities are wired; it does not silently guess versions or fetch customer
files. The source's `PARAMS_SCHEMA` is carried as form metadata, not authority
to execute or push.

An installed `release-package-preview` Workflow and `release-package-guide`
Skill expose a read-only step. Static Host settings name an existing local
checkout and inbox. The preview verifies `.git/HEAD` names the requested
branch, then reads its current `release.yaml` to project the next version and
compares intended file bytes without changing the checkout. It refuses a
missing or different branch; it cannot yet create a branch from the template,
resolve a version from the package index, transfer upload sets or offer an
array-valued file chooser in the generic Workflow form. The source-compatible
runtime schema is retained for those later controls. This preview does not
claim full Workflow 13 parity.

An independently named `engineering/release-package-apply-isolated@1.0.0`
Workflow exposes the source-compatible file-preparation portion only. It has no
numeric `/run 13` alias. The Host registers its write capability only when
`integrations.isolated_release_apply` supplies an `IsolatedApplySettings`
configuration with an explicit checkout, inbox and allowed root. Invocation
still requires a local capability grant and a separate approval reference.
The allowed root must carry the exact `.aep-isolated-release-root` marker and
the Git checkout must have no configured remote. A checkout lock refuses
concurrent preparation; stale source files or a changed `release.yaml` refuse
execution. On success the step writes the projected local files and reports
`prepared=true`, `committed=false`, `pushed=false`. It cannot commit, push or
contact a remote. Agent-to-Bridge tests cover no-grant refusal, missing-approval
refusal, and approved preparation in a marked temporary checkout. This is a
testable intermediate slice, not production release execution.

Before enabling full release execution, add typed Bridge read
capabilities for published-version/readiness lookup, governed upload transfer,
serialized checkout and Git status, and policy-classified write/commit/push
steps. Compare normalized files and Git diff in an isolated test repository,
then collect company-host dry-run parity evidence. Publishing a Workflow asset
cannot grant release authority. No production repository push is authorized by
this slice.

## Release run up to the commit (2026-10-08)

The owner asked for Workflow 13 to be migrated, up to the commit; push comes in a later round. The source checkout used is `C:\Users\Chi_L\Documents\claude\n8n_workflow_system` at the pinned revision above (the earlier hash in this document had one extra character).

AEP splits the source job into two Workflows, each a separate approved run:

- `engineering/release-package-prepare@1.0.0` runs capability `release-package/prepare@1.0.0`, which covers the source's `resolve`, `checkout` and `write` steps:
  - It finds the chipset version: the newest published release on the PEP 503 index (dev builds are never chosen), then the readiness table.
  - It clones or fetches the repository, then checks out an existing branch (with `reset --hard origin/<branch>`) or creates one from the template.
  - It writes `requirements.txt`, the named inbox files and `release.yaml` the way the source writes them: text mode for the generated files, `copy2` for inputs.
  - It reports the source's dry-run plan and a fingerprint, and keeps a record of what it prepared in the checkout's `.git`. It never commits.
- `engineering/release-package-commit@1.0.0` runs capability `release-package/commit@1.0.0`. It commits only when the branch and fingerprint the person reviewed match the record, and the branch, HEAD and every changed file are unchanged. The commit message follows the source's subject and quoting (`_quote_for_git`). It skips a dry run and an unchanged release. It never pushes.

Both capabilities are `write` with `approval_required`, and they run under a lock, one run per working copy. Git runs as an argument list with no shell and never prompts.

Until push is approved, the settings accept only a local origin inside a root carrying `.aep-isolated-release-root`; https and ssh remotes are refused with `remote_not_isolated`.

Adaptations from the source:
- Inputs are validated before anything is written. The source wrote `requirements.txt` before it checked the inbox names.
- Upload sets (the source's ops dashboard) are refused with `upload_sets_not_supported`, because on AEP files arrive as attachments and that route is not wired yet.
- The source derives the working-copy folder from the part of the URL after the last `/`, so a backslash Windows path would put it in the wrong place. AEP accepts either separator.

Parity (`benchmarks/w13_parity`, run p001): the source job ran unchanged, through a stand-in Bridge that runs PowerShell inside the isolated root and refuses `git push`. AEP ran prepare and then commit on an identical copy. All four cases match: a new branch from the template, an existing branch, a dry run and an explicit version. The comparison covered branch, state, versions, requirements, the changed count, committed/pushed, the commit message and every committed blob hash (or, for the dry run, the status and the bytes of changed files).

Still open: push with its own approval against the real GitLab, the pipeline watch, upload sets from attachments, and a dry-run comparison against the real release repository.

## Push (2026-10-15)

The owner asked for the n8n workflow (`workflows/13_release_package.json`: manual
trigger, parameters, Bridge job `release_package`, success or failure summary) to be
ported in full. Its parameters map to `release-package-prepare` (the n8n `dryRun`,
`testPlans`, `configurations`, `overlays`, `chipsetVersion` and the identity fields), its
commit to `release-package-commit` and its push to a third Workflow:

- `engineering/release-package-push@1.0.0` runs capability `release-package/push@1.0.0`
  (`external_side_effect`, risk high, approval required). Its run values are the branch
  and the commit id the commit step reported. The commit step now records that commit in
  the checkout's `.git`; push refuses (`not_committed`, `stale_commit`) unless it matches,
  and refuses a changed branch, HEAD or working tree (`checkout_changed`) or an origin
  that is not the configured repository (`origin_changed`). It runs
  `git push -u origin <branch>` (the source's command and 900 s timeout), never forced;
  a commit already on origin is reported as `already on origin`.
- The per-install setting `remote_release` (default off) lets `release_repo_url` be the
  real repository: an https or ssh URL with no user, password or token in it
  (`remote_url_invalid` otherwise). The working copy and inbox must still be inside the
  marked root. With it on, the prepare plan names the push and the GitLab project path,
  as the source's dry-run plan does.

The n8n summary node's fields come from the three results: branch and branch state
(prepare), commit (commit), pushed and project path (push). Not carried: upload sets
(the n8n workflow names inbox files, so it never used them) and the pipeline watch
(a separate source job).
