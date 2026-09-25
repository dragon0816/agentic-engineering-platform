# Product gate E2E-04 — governed Software continuous evolution

Status: complete; merged in PR #101 after the exact head passed the
Windows/Python 3.12 verification workflow

## User scenario

An engineer reports through the Personal Agent that an exact published Software
version fails on a supplied example. The Software asset, rather than the user,
identifies its external repository and owner. The platform records expected and
actual behavior, evidence, example input/output, environment and acceptance
criteria in a standardized improvement request.

After the Software owner approves development, the normal Agent/Gateway route
invokes a Bridge-installed write capability. It validates the published
repository revision, reproduces the reported failure before mutation, then uses
the existing bounded Coding Harness to prepare and validate a change. Both the
issue case and committed repository regressions must pass. CI prepares an
in-memory PR/MR artifact and performs no external Git write.

Repository review, merge, release and Share Platform republish are explicit
human-controlled transitions. The new Software metadata links release evidence,
and the old exact version remains registered for rollback. Publishing metadata
does not install or authorize the Software.

The committed local fixture repository is under `tests/fixtures/e2e_04/`.

## Minimum implementation

```text
LocalAgent report
  -> Gateway -> Bridge -> software_evolution.capture_issue
  -> exact owner/repository-routed improvement request
  -> owner triage approval
LocalAgent development request
  -> Gateway -> Bridge-approved software_evolution.prepare_change
  -> validate pinned repository revision
  -> reproduce reported output before change
  -> existing CodingHarness
  -> issue case + repository regressions
  -> inert PullRequestCandidate
  -> human source-control review
  -> human merge evidence
  -> human release evidence
  -> approved SoftwareManifest vNext; vPrevious retained
```

## Automated acceptance

`tests/test_product_e2e_04.py` proves:

- Software metadata identifies owner, external repository/revision, interfaces,
  compatibility and release evidence without accepting source content;
- the report contains expected/actual behavior, evidence, example input/output,
  environment, acceptance criteria and trace;
- owner and repository routing come from the exact published asset;
- pending owner approval prevents workspace mutation;
- the reported output is reproduced on the pinned revision before mutation;
- the existing Coding Harness produces a reviewable exact change set;
- both the issue case and repository regression suite must pass;
- the inert source-control adapter performs zero external writes;
- an unreproduced issue produces no Harness run or PR candidate;
- a regression failure produces no PR candidate or release-ready result;
- a rejected repository review cannot be merged;
- review, merge, release and republish remain separate human transitions;
- the new exact version links release evidence and preserves rollback; and
- published Software metadata is still unavailable to Bridge execution unless
  a capability is separately installed and authorized.

Run the gate on the supported development target:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_product_e2e_04.py -q -p no:cacheprovider --basetemp .scratch\pytest-e2e04
```

CI runs only on `windows-latest` with Python 3.12 by owner decision. The package
compatibility declaration remains Python 3.11+.

## Architecture and migration decisions

- **REUSE** `LocalAgent`, `Gateway`, `BridgeExecutor`, installed Skills and
  `LocalPolicy`; report capture and development use no alternate path.
- **REUSE** the E2E-03 `CodingHarness`, confined workspace, declared validators,
  changes, regression cases, budgets and trace evidence.
- **ADAPT** the E2E-05 exact-version improvement and rollback lifecycle for
  Software while keeping source in its external repository.
- **ADD** Software metadata/catalog, report routing, pre-change reproduction,
  inert source-control preparation and explicit human review/merge/release
  records.
- **DO NOT MIGRATE** a source repository implementation. This gate composes
  existing platform components around a committed local fixture repository.
- **DEFER** production GitHub/GitLab adapters, actual PR/MR creation, merge,
  release automation and remote repository checkout.

## Gate

E2E-01 must not begin until this gate passes pull-request CI and merges. The
physical DUT phase may reuse this Software lifecycle, but its production-like
hardware evidence must remain separate from inert CI.
