# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/skill-marketplace`
Base: `origin/main` at merge commit `792e427` (PR #155)
PR: https://github.com/dragon0816/agentic-engineering-platform/pull/157

## Goal

Begin Productization 2 with the first Agent Add-on Marketplace E2E: select an
exact shared Skill in the member Web interface, synchronize it, rebuild the
host and prove the Personal Agent uses the Skill's deterministic command.

## Completed

- Added Productization 2 and planned Productization 3 specifications grounded
  in Product Vision and the existing Agent Add-on / Bridge Extension /
  independent Application architecture boundary.
- Generalized the authenticated member catalog from Workflow-only to exact
  Workflows and Skills. Other kinds remain refused until they have compatible
  package and activation contracts.
- Member select requests still carry only Bridge id and asset identity. The
  platform derives `workflow` or `skill` from trusted Registry metadata; a
  client-supplied kind is rejected by the closed contract.
- Updated the dependency-free member UI to show add-on kind and selection.
- Added a real-socket E2E crossing member selection, Personal Agent Web sync,
  control-plane HTTP, all-or-nothing Bridge install, host rebuild, Skill
  registry, deterministic routing, Workflow engine and Bridge policy.
- Proved that selecting a Skill does not add or widen capability grants and
  that an unsupported Knowledge kind cannot enter this install path.
- Updated Architecture, Contracts, Roadmap and Tasks after the green path.

## In Progress

- PR #157 is open at implementation commit `2dfaa25`. Exact-head Platform
  verification must pass before the owner-authorized automatic merge.

## Remaining

1. Wait for PR #157 exact-head Windows/Python 3.12 verification and merge it
   automatically when green.
2. Productization 2 slice 2: define and implement one path-safe portable
   Knowledge package containing an exact manifest plus immutable Raw and
   curated Wiki content, with no publisher-controlled local Vault path.
3. Continue slices 3–5 sequentially; Productization 3 runtime implementation
   begins only after Productization 2 has a reproducible exit path.

## Architecture decisions made

- **REUSE** the existing package, device selection, platform synchronization,
  Skill manifest and Skill registry contracts. The missing behavior was a
  Workflow-only member projection, not another installer.
- Derive add-on kind from the Registry package. The member cannot relabel a
  Skill as a Workflow or decide installation semantics.
- Skills remain procedure/routing data and may target only an existing typed
  Workflow or capability. This slice introduces no executable plug-in loader.
- Keep Knowledge and Agent profiles out of the Skill/Workflow installer until
  their portable package and activation contracts are explicit.
- Productization 3 keeps Bridge Extensions separate from independent Apps;
  its process isolation, signature and activation policy decisions remain
  explicit gates before executable extension work.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu run was performed.
Browser automation was excluded per owner direction.

```text
Focused member/platform suite:
python -m pytest tests/test_member_portal.py tests/test_skill_marketplace.py
  tests/test_platform_transport.py tests/test_shared_platform_app.py -q
31 passed, 1 skipped

Final Skill/member/Personal Web suite:
python -m pytest tests/test_skill_marketplace.py tests/test_member_portal.py
  tests/test_agent_web.py -q
38 passed

Full supported suite:
python -m pytest --ignore=tests/test_browser.py -q
1404 passed, 4 skipped in 54.97s

python -m ruff check .
All checks passed!

python -m ruff format --check .
307 files already formatted

python -m mypy
Success: no issues found in 239 source files

python -m pip check
No broken requirements found.

python -m build --outdir <repo>/.scratch/build-skill-marketplace
Successfully built sdist and wheel.

git diff --check
PASS
```

The four skips are existing Windows environment conditions: symlink/link
privileges, IPv6 loopback and directory links.

## Known issues

- The member portal currently requires the user to enter the Bridge id; a
  later UX slice can project the member's bound devices without changing
  selection authority.
- Portable Knowledge, Agent-profile activation, add-on removal and rollback
  are not part of this first slice.
- Platform member/session/selection records remain reference in-memory state;
  only Registry package metadata and artifacts are durable.

## Next Recommended Action

After PR #157 merges, implement Productization 2 slice 2 as a contract-first
portable Knowledge package. Reuse `KnowledgeManifest`, Vault provenance and
the existing all-or-nothing synchronization boundary; refuse traversal,
identity mismatch, digest mismatch and any package-supplied absolute Vault
path before writing.
