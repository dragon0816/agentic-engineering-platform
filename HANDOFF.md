# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/agent-profile-activation`
Base: `origin/main` at merge commit `4c23df7` (PR #161)
PR: pending

## Goal

Productization 2 slice 4: distribute inert exact Agent profiles and require one
explicit, validated local activation before a profile narrows Personal Agent
behavior.

## Completed

- PR #161 passed exact-head Windows/Python 3.12 CI and auto-merged; portable
  Knowledge can now be selected, installed and queried locally.
- Added `agent` to the member-selectable and synchronization-installable Agent
  Add-on kinds. Member requests still carry only Bridge and exact asset identity.
- Bridge synchronization validates a closed `AgentProfile` JSON artifact,
  requires its governance metadata to match the Registry package and installs it
  under a host-derived filename. Installation remains inert.
- Added host-local `ActiveAgentProfile` state and an explicit Personal Agent Web
  activation endpoint/UI. Activation validates the profile selection, installed
  exact Skills and Knowledge, separate capability selections, routing-model
  requirements and the absence of delegation before one atomic write.
- Host rebuild filters the existing Skill registry, Knowledge catalog and
  derived capability grants through the active profile. A profile cannot add a
  handler, manifest, grant, model or authority.
- Added a real HTTP E2E across member selection, control-plane synchronization,
  local Web activation, host rebuild and Skill -> Workflow -> Bridge execution.
  Selection and activation leave platform capability grants unchanged.

## In Progress

- Open the slice 4 PR, wait for exact-head Windows/Python 3.12 CI and auto-merge
  when green.

## Remaining

1. Productization 2 slice 5: explicit exact-version replacement/removal and
   rollback while retaining a usable prior version.
2. Run the complete Productization 2 exit proof and mark the milestone done.
3. Begin Productization 3 with category/compatibility contracts, then inert
   Bridge Extension staging before any executable extension runtime.

## Architecture decisions made

- **REUSE/ADAPT** `AgentProfile`, member selection, package synchronization,
  Personal Agent Web and the existing runtime registries. No second Agent or
  marketplace runtime was introduced.
- Profile installation and activation are separate. Publication, selection and
  installation still do not authorize execution.
- An active profile is a narrowing filter over existing local authority. Missing
  or revoked dependencies fail closed during activation/rebuild.
- Specialist delegation and concurrent Agents remain excluded; any
  `may_delegate_to` entry is refused in this milestone.
- Applying a new profile requires host restart so an already-running Gateway is
  never mutated halfway through a request.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu or browser automation.

```text
Focused member/platform/Profile suite:
30 passed, 1 skipped

Full supported suite:
python -m pytest --ignore=tests/test_browser.py -q
1419 passed, 4 skipped in 57.12s

python -m ruff check .
All checks passed!

python -m ruff format --check .
312 files formatted after final format pass

python -m mypy
Success: no issues found in 244 source files

python -m pip check
No broken requirements found.

python -m build --no-isolation --outdir <repo>/.scratch/build-agent-profile
Successfully built sdist and wheel.

git diff --check
PASS
```

The four skips are existing Windows environment conditions: symlink/link
privileges, IPv6 loopback and directory links.

## Known issues

- Profile activation reports `restart_required`; this slice intentionally does
  not hot-swap a live Agent while a request may be running.
- Local inventory is append-only. Version replacement/removal and rollback are
  the next slice.

## Next Recommended Action

Open and merge this verified slice. Then add one atomic member-facing exact
version replacement operation, retain installed prior bytes for rollback, and
add explicit cleanup rules that cannot remove the active or sole rollback
version. Do not let local rollback bypass synchronized authorization.
