# Handoff — Phase 4 vault safety model (slice 1)

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-4/vault-safety`, based on `main` at `07379c8` (PR #21 merged —
Phase 3 complete).

## Goal

Phase 3 is complete against `docs/ROADMAP.md` (14 slices, 472 tests). The
owner asked for Phase 4 to begin directly. This slice writes the Phase 4
specification and delivers its first requirement: the vault safety model that
every later knowledge slice writes through. Requirements:
`docs/phases/PHASE_4_KNOWLEDGE.md` (slice 1); source decisions:
`docs/PHASE_4_MIGRATION.md`; contracts: `docs/CONTRACTS.md` ("Knowledge vault").

## Completed

- `docs/phases/PHASE_4_KNOWLEDGE.md`: the pipeline, the seven invariants carried
  from the source, slice 1 requirements, the outline of slices 2–9 (each needs
  its own requirements before work starts) and what is out of scope.
  `CLAUDE.md` now names it as the active phase specification.
- `docs/PHASE_4_MIGRATION.md`: source inspection of `knowledge_management`
  `vault/` at `2f5e6d0431c5b6af8fbee05c6c0a5779e1a84bb9`, the **ADAPT**
  decision with why not WRAP/REWRITE, a per-behavior disposition table and the
  intentional differences.
- Pinned excerpts `tests/fixtures/source_vault_ingest.txt` (the safety core of
  `ingest.py`) and `source_vault_conflicts.txt` (the whole `conflicts.py` minus
  docstring), with checksums in `tests/fixtures/README.md`; 12 characterization
  tests (`tests/test_source_vault.py`) drive them against temporary vaults.
- `src/knowledge/vault.py`: the layout as closed refusal codes
  (`immutable_area`, `outside_writable`, `escapes_vault`, `not_a_vault`);
  `WritePlan` / `PlannedPage` / `IndexEntry` / `PlanProblem` / `LinkRepair` /
  `VaultOutcome` contracts; `check_plan` with closed problem codes;
  `repair_wikilinks` and `ensure_conflicts_visible` reproduced exactly;
  `insert_index_entries` and `log_block` as pure functions; `Vault.apply` with
  dry run by default, backup before overwrite, whole-plan rejection, injected
  date and backup stamp, whole-or-nothing writes with rollback, and every
  target checked (including `create`/`update` against the vault) before any
  write. 20 regression tests (`tests/test_vault.py`); the one that plants a
  directory link from `wiki/` into `raw/` skips where links need privileges.
- Provenance in a sources page is typed: the plan carries a `KnowledgeSource`
  and the page must carry its `source_id:` and `source_sha256:` lines.

- PR #22 opened; pre-merge review applied (10 findings, seven of them real
  holes in a *safety* model, several reproduced by the reviewer): a link inside
  `wiki/` pointing at `raw/` could be written through, so the layout check now
  runs on the resolved location too; an apply was not atomic, so every target
  is checked first (directories, links, `create`/`update` against the vault)
  and a write that fails part-way is rolled back from what the vault held and
  raised as `write_failed`; a plan naming one page twice would back the first
  write up over the original (`duplicate_path` now); `written` claimed
  `index.md` even without entries; a caller's backup stamp could carry `..`
  (one path component now, automatic stamps carry microseconds); the root
  files matched by prefix (`index.md.bak` — exact match now); `Vault.read`
  could leave the vault; `PlannedPage.action` was carried but ignored
  (`create_exists` / `update_missing` now); contradiction notes were not
  trimmed as the source trims them. Ten regression tests added for these.

## In Progress

- PR #22 is open with the review posted; CI results for the final head are
  recorded on the PR.

## Remaining

- Review and merge this PR (the owner's standing pattern is an explicit
  "merge #N"; Phase 3 closure was pre-authorized, this is Phase 4).
- Slice 2 next: Drop → Raw with typed provenance and content-hash dedup
  (write its requirements section first).
- Slices 3–9 as outlined in the phase spec. Slice 3 will introduce optional
  extraction dependencies (PDF/PPTX/DOCX); license and maintenance must be
  recorded before adoption per the owner's rules.
- Deferred from Phase 3, each needing its own scope: a payload sweep,
  process-liveness or lease-based suspension, and the earlier deferred reviews.

## Architecture decisions made

- **ADAPT, not WRAP or REWRITE** (recorded in `docs/PHASE_4_MIGRATION.md`): the
  source's safety core is entangled with printing, `SystemExit` and an untyped
  plan dict at exactly the boundary the platform's contracts must hold; the
  behaviors themselves are proven on a real vault and are pinned, not
  reinvented.
- `drop/` joins `raw/` as immutable; `decisions.md` joins the writable set.
- The vault's runtime `CLAUDE.md` schema is not read by the platform: the
  conventions it encodes become contracts here (`docs/phases/PHASE_4_KNOWLEDGE.md`,
  "Out of scope").
- A `WritePlan` is data. The model that will propose one arrives in slice 5
  behind `ModelClient`; slice 1 validates and applies without one.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 504 tests (472 prior + 12 characterization + 20 regression; 1 skipped
#       on Windows without symlink privileges, runs on Linux CI)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS
.venv/Scripts/python.exe -m mypy
# PASS: 63 source/test files
.venv/Scripts/python.exe -m pip check
# PASS
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

One thing the characterization corrected in my own tests: the source strips
`.md` only from a link that carries a path, so `[[Qux.md]]` is left alone — the
same reasoning that keeps a working `[[CLAUDE.md]]` link working. Both the
excerpt and the adapted code agree; the first draft of the tests did not. Vault
directories live under pytest's temporary directory. No model, gateway,
network, real vault, job or n8n instance was invoked. Local pytest uses
`-p no:cacheprovider` because of temporary-directory ACLs on this machine; CI
runs ordinary pytest.

## Known issues / limitations

- No ingestion exists yet: nothing produces a `WritePlan` but a test. Drop →
  Raw (slice 2) and model-proposed plans (slice 5) are ahead.
- Dedup by `source_path` is deliberately not migrated; slice 2 replaces it with
  content-hash provenance and reports drift.
- The backup directory grows with every overwrite, as in the source; a backup
  retention policy is not defined.

## Next Recommended Action

Open the PR for `phase-4/vault-safety` against `main`, run the review, apply
confirmed findings and let the owner merge. Then write the slice 2 requirements
section in `docs/phases/PHASE_4_KNOWLEDGE.md` and implement Drop → Raw.
