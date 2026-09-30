# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/web-knowledge-asking`
Base: `origin/main` at merge commit `59d0542` (PR #151)
PR: pending

## Goal

Complete Productization 1 slice 5: list exact installed Knowledge versions and
ask one grounded question from Personal Agent Web through the normal local
Agent, exact Knowledge capability and Bridge policy, preserving Raw citations.

## Completed

- Added `KnowledgeAskRequest`, a closed exact-asset and question contract. It
  cannot claim actor, Bridge, route, model, Vault or authorization and rejects
  embedded credential material.
- Personal Agent Web lists only Knowledge manifests that have an exact trusted
  host binding. It exposes identity, domain, owner and visibility and never
  returns `vault_root`.
- Added authenticated loopback `POST /api/knowledge/ask`. The host supplies its
  actor, Bridge and trace, then sends the established `KnowledgeQueryRequest`
  through `LocalAgent.execute_capability` to `knowledge-query/ask@1.0.0`.
- Reused the existing Knowledge catalog, deterministic retrieval, configured
  model adapter, grounded-record validation and Bridge policy. The Web layer
  owns no retrieval or synthesis logic.
- The page provides an exact Knowledge selector and question form and displays
  the grounded answer, trace/request identifiers and every returned Raw
  citation location and passage.
- Added real-socket integration tests for listing without Vault disclosure,
  exact successful querying with citations, bearer protection, closed request
  fields, embedded-secret rejection and Bridge permission refusal.
- Updated Architecture, Contracts, Roadmap, Tasks and the active Productization
  specification after implementation validation.

## In Progress

- Local implementation and the supported verification baseline are green.
- Commit, push, pull request and exact-head CI remain to be completed.

## Remaining

1. Commit and open the slice 5 pull request, wait for exact-head Platform
   verification, and merge automatically when green under the owner's
   2026-10-01 instruction.
2. Productization 1 slice 6: replace the in-memory shared Registry references
   with the smallest persistent implementation that preserves current service,
   transport and Bridge execution contracts.
3. After all Personal Agent Web slices merge, use the repository roadmap and
   product acceptance documents to define and begin productization stages 2
   and 3 without inventing parallel architecture.

## Architecture decisions made

- **ADAPT** the existing `KnowledgeQueryHandler`, `KnowledgeCatalog`,
  `QueryEngine`, model binding and `LocalAgent.execute_capability`. There is no
  competing source-repository Web query implementation to migrate.
- An exact member selection is deterministic and bypasses intent routing, but
  it adds no authority: Local Agent admission and Bridge capability policy
  remain mandatory.
- Local Vault paths and model selection are trusted host configuration. They
  are absent from the browser contract and installed-asset projection.
- `KnowledgeAnswerRecord` stays the answer contract. Personal Agent Web returns
  its grounded Raw passages and provenance unchanged rather than defining a
  second citation format.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu run was performed.
Browser automation was excluded per owner direction; the Web boundary was
exercised over real loopback sockets.

```text
Focused Web + Knowledge + model-host suite:
python -m pytest tests/test_agent_web.py tests/test_product_e2e_05.py
  tests/test_host_models.py -q --basetemp=<repo>/.scratch/...
53 passed

Final focused Web suite after typing correction:
python -m pytest tests/test_agent_web.py -q --basetemp=<repo>/.scratch/...
30 passed

Full supported suite:
python -m pytest --ignore=tests/test_browser.py -q
  --basetemp=<repo>/.scratch/...
1392 passed, 4 skipped in 53.80s

python -m ruff check .
All checks passed!

python -m ruff format --check .
302 files already formatted

python -m mypy
Success: no issues found in 236 source files

python -m pip check
No broken requirements found.

python -m build --outdir <repo>/.scratch/build-web-knowledge
Successfully built sdist and wheel.

git diff --check
PASS
```

The four skips are existing Windows environment conditions: symlink/link
privileges, IPv6 loopback and directory links. An exploratory full run that
included `tests/test_browser.py` produced 1404 passes plus 9 Edge launch
failures because this environment did not publish a debugging port; the owner
explicitly excluded browser automation from the local baseline.

## Known issues

- Grounded answer synthesis needs an explicitly configured host model; no
  hidden or default provider is selected.
- Installed/configured Knowledge still lives in the local filesystem. Shared
  catalog metadata remains in memory until Productization 1 slice 6.
- The page asks one exact version at a time and does not yet capture Knowledge
  improvement feedback; the existing continuous-evolution contracts remain
  separate from this bounded query slice.

## Next Recommended Action

After this PR merges, implement the durable shared Registry as a separate
slice. Persist the already validated control-plane records with a small store,
preserve every current service/transport contract, and keep Bridge execution
and local Agent state outside that store.
