# Workflow 13 source contract and first AEP slice

Source: read-only `dragon0816/rs_workflow_system` at
`896046e8fe2170d21f9213e56e5ce2f93c05ba43d`, especially
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
