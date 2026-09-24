# Handoff — E2E-05 governed Knowledge evolution

Updated: 2026-09-25 (Asia/Taipei).
Branch: `codex/e2e-05-knowledge-evolution`.
Base: E2E-03 merged to `main` by PR #99 (`15f88eb`).
Implementation commit: `2444bb1`.
Pull request: #100, open against `main`.

Progress across all phases remains in `docs/TASKS.md`. This file records the
current stopping point and the constraints another coding agent must preserve
without relying on conversation history.

## Completed

- Merged E2E-03 in PR #99 only after its exact head passed the single
  Windows/Python 3.12 CI job.
- Added exact-version `KnowledgeManifest` and an in-memory `KnowledgeCatalog`
  that admit only published, digest-matching local vaults and retain prior
  versions for rollback.
- Added grounded query records that bind exact asset/version, trace, answer and
  cited passages; every answer sentence must cite immutable Raw evidence.
- Added structured improvement requests containing the original answer,
  citations, user feedback, expected information, reproduction and acceptance
  criteria. Feedback alone cannot mutate published Knowledge.
- Added a separately approved maintainer-triage transition and a Bridge-installed
  `knowledge_evolution.create_candidate` write capability. It copies the base
  vault to a new root, applies a typed `WritePlan`, and removes partial output on
  failure.
- Bound candidates and validation evidence to complete content, Raw and decision
  digests plus the ordered new/regression evaluation set.
- Kept domain-owner approval separate from validation, Bridge execution
  authorization and publication.
- Added a committed miniature vault and deterministic E2E gate from question to
  corrected version, including exact old-version rollback.
- Added negative paths for Wiki-only unsupported claims, regression failure and
  reintroduction of an exact claim persisted as rejected in `decisions.md`.
- Confined candidate paths to a Bridge-configured workspace and proved that
  content drift after validation invalidates the evidence.
- Updated Architecture, Contracts, Roadmap, Tasks, README and the E2E-05 gate
  record only after focused and full tests passed locally.

## In Progress

- Wait for PR #100's exact-head Windows/Python 3.12 CI result and merge only if
  it passes.

## Remaining

- Replace this section with exact commit, PR, CI and merge evidence after those
  steps complete.
- E2E-04 software continuous evolution remains blocked until E2E-05 merges.
- E2E-01 physical DUT/chipset engineering remains blocked behind E2E-04 and
  requires later company-host evidence.
- Do not resume the older Phase 7 workflow backlog as part of this product gate.

## Architecture decisions made

- **REUSE** the resident `LocalAgent`, `Gateway`, `BridgeExecutor`, installed
  Skills and `LocalPolicy`; no second agent/runtime was introduced.
- **REUSE** Phase 4 `Vault`, `QueryEngine`, Raw provenance, `WritePlan`, decision
  records and immutable-Raw behavior.
- **WRAP** exact-version query as a Bridge `read` capability and candidate vault
  creation as a Bridge `write` capability requiring execution approval.
- **ADD** only the missing improvement/version/evaluation contracts and the
  in-memory exact-version catalog needed for the product gate.
- **DO NOT MIGRATE** another source implementation; existing migrated Knowledge
  components already supply the proven behavior needed here.
- Feedback, maintainer triage, automated validation, domain approval,
  publication and execution authorization are independent transitions.
- A candidate is created in a new vault root. Raw remains byte-identical and the
  published base is never edited in place.
- Published versions retain exact content/evidence digests. Validation evidence
  cannot authorize content that changed after evaluation.
- Persisted `- reject:` decisions block exact rejected claims before candidate
  writes. Broader semantic contradiction detection is deferred and must not be
  claimed by a later agent.
- The catalog is an inert in-memory/local-vault proof, not a production Registry,
  database or remote Knowledge service.

## Exact verification commands and results

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

The four skips are existing host-dependent cases: two Windows link privilege
checks, IPv6 loopback availability and a directory-link privilege check. No
Ubuntu or Python 3.11 validation was run, per owner instruction.

## Known issues

- Routing and answer synthesis in the gate use a scripted provider-neutral model
  so CI stays deterministic and inert. A live model endpoint is not E2E-05
  acceptance evidence.
- Rejected-claim protection currently enforces exact persisted phrases. The
  decision record is durable, but semantic-equivalence detection is deferred.
- The catalog and vault paths are process-local. Production Registry/database,
  remote asset transport and distributed locking remain outside this gate.
- The candidate write has a trusted configured target root; production workspace
  allocation still belongs to a later host/control-plane adapter.
- `.claude/` is untracked user-owned state and must not be committed, modified or
  removed.

## Next Recommended Action

Finish Windows/Python 3.12 verification, open and merge the E2E-05 PR only after
its exact head passes CI, then rewrite this handoff with final evidence. Only
after that may the next owner begin E2E-04 from `PRODUCT_ACCEPTANCE_TESTS.md`.
They must preserve exact Knowledge version rollback, immutable Raw, grounded
citations, persisted decisions and the separation of validation, business
approval, publication and execution authorization.
