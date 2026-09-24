# Handoff — E2E-05 complete; E2E-04 is next

Updated: 2026-09-25 (Asia/Taipei).
Branch: `main`.
E2E-05 pull request: #100, merged as `0f7437027af783f416d68b24bd7c6de746624f92`.
Verified PR head: `31c48709cdf40454dfee6cf4a7d64ba3b91415e7`.
CI run: `36038167378`, job `107763372657`, passed in 3m26s.

Progress across all phases remains in `docs/TASKS.md`. This file contains the
current stopping point and constraints needed to continue without chat history.

## Completed

- E2E-02, E2E-03 and E2E-05 are merged in the approved order through PRs #98,
  #99 and #100.
- E2E-05 adds exact-version `KnowledgeManifest` records and an in-memory
  `KnowledgeCatalog` that admits only published, digest-matching local vaults and
  retains previous versions for rollback.
- `knowledge_query.ask` runs through the resident Personal Agent, Gateway and
  Bridge. A grounded answer binds exact asset/version, trace, answer and Raw
  passages, and every sentence must cite Raw evidence.
- Feedback becomes a structured `KnowledgeImprovementRequest` with the original
  answer/citations, expected information, reproduction and acceptance criteria.
  It cannot mutate the published Knowledge version.
- Maintainer triage approval is required before candidate development. Candidate
  creation is a separately authorized Bridge `write` capability confined to a
  host-configured workspace.
- Candidate creation copies the base vault, applies a typed `WritePlan`, removes
  partial output on failure, preserves Raw byte-for-byte and retains the settled
  decision record.
- Validation binds the exact candidate content and ordered new/regression cases.
  A regression failure blocks approval, and any post-validation content drift
  invalidates the evidence.
- Domain-owner approval remains separate from technical validation, Bridge
  authorization and publication. Publishing creates vNext while the old exact
  version remains queryable.
- Exact claims persisted as `- reject:` in `decisions.md` cannot be reintroduced
  by a later candidate plan.
- The product gate uses a committed miniature vault and a deterministic scripted
  model; CI remains inert and performs no production side effects.

## In Progress

- None. Stop here by owner instruction after Phase 3 / E2E-05.

## Remaining

- E2E-04 software continuous evolution is the next gate in
  `docs/PRODUCT_ACCEPTANCE_TESTS.md`. It has not started.
- E2E-01 physical DUT/chipset engineering remains blocked behind E2E-04 and
  will require later validation on an enrolled company computer.
- The older Phase 7 workflow backlog remains separate from this fixed product
  E2E sequence; do not resume it by inference.

## Architecture decisions made

- **REUSE** resident `LocalAgent`, `Gateway`, `BridgeExecutor`, installed Skills
  and `LocalPolicy`; there is no second agent/runtime or query path.
- **REUSE** Phase 4 `Vault`, `QueryEngine`, Raw provenance, `WritePlan`, decision
  records and immutable-Raw behavior.
- **WRAP** exact-version query as a Bridge `read` capability and candidate vault
  creation as a Bridge `write` capability requiring execution approval.
- **ADD** only the missing version, feedback, candidate and evaluation contracts
  plus an in-memory exact-version catalog for this gate.
- **DO NOT MIGRATE** another source implementation. Existing migrated Knowledge
  behavior already supplied the required base.
- Feedback, maintainer triage, automated validation, domain approval,
  publication and execution authorization are independent transitions.
- Published versions and validation evidence carry exact digests. Validation
  evidence cannot authorize different or later-modified content.
- Rejected-claim enforcement is exact phrase matching. Semantic-equivalence
  detection is deferred and must not be claimed as implemented.
- This is an inert local proof, not a production Registry/database, remote vault
  service, live-model evaluation or automatic issue/repository integration.

## Exact verification commands and results

Local Windows/Python 3.12:

```text
.venv\Scripts\python.exe -m pytest tests\test_product_e2e_05.py -q -p no:cacheprovider --basetemp .scratch\pytest-e2e05-focused-final
5 passed in 0.49s

.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .scratch\pytest-e2e05-full-final
1296 passed, 4 skipped in 68.51s

.venv\Scripts\python.exe -m ruff check .
All checks passed

.venv\Scripts\python.exe -m ruff format --check .
244 files already formatted

.venv\Scripts\python.exe -m mypy
Success: no issues found in 196 source files

.venv\Scripts\python.exe -m build --no-isolation --outdir .scratch\build-e2e05-final2
Successfully built sdist and wheel

.venv\Scripts\python.exe -m pip check
No broken requirements found

git diff --check
passed
```

GitHub Actions on PR #100:

```text
Platform verification / verify
run 36038167378, job 107763372657
Windows, Python 3.12
passed in 3m26s
```

The four local skips are existing host-dependent cases: two Windows link
privilege checks, IPv6 loopback availability and a directory-link privilege
check. No Ubuntu or Python 3.11 validation was run, per owner instruction.

## Known issues

- A live model/provider has not been used as E2E-05 acceptance evidence.
- Rejected-claim protection currently enforces exact persisted phrases.
- The catalog and vault paths are process-local; production Registry/database,
  remote asset transport and distributed locking remain outside this gate.
- Production candidate workspace allocation still needs a host/control-plane
  adapter behind the same confined Bridge capability.
- `.claude/` is user-owned local state. Do not commit, modify or remove it.

## Next Recommended Action

Read `PRODUCT_VISION.md`, `PRODUCT_ACCEPTANCE_TESTS.md`, `docs/ARCHITECTURE.md`,
`docs/TASKS.md` and this handoff. Prepare the E2E-04 software continuous
evolution plan from its user-level acceptance scenario before changing code.
Reuse the E2E-03 Harness and E2E-05 improvement/evidence/approval boundaries.
Do not weaken exact versioning, external validation, rollback, or the separation
of business approval, technical policy, publication and execution permission.
