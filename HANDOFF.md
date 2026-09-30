# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/invitation-member-signin`
Base: `origin/main` at merge commit `6a5c8d3c757bd08b0b9b736ee0fd70404166d171`
Implementation commit: `02d74503ef3bb2ab5c7b19cfb26af5e3a4ebe095`
PR: https://github.com/dragon0816/agentic-engineering-platform/pull/145

## Goal

Continue Productization 1 with slice 2b: connect the invitation-only shared
platform enrollment flow to the short-lived direct-member browser session from
slice 2a, without putting a secret in Registry assets or accepting a Bridge
credential as an interactive member sign-in.

## Completed

- Added `InvitationProofGrant`, a serializable secret-free record containing
  only invitation identity, actor, proof fingerprint, lifetime and state.
- Added `IssuedInvitationProof`, a deliberately non-serializable one-time
  return value whose repr redacts the generated proof.
- Added `InMemoryInvitationSignIn` as the provider-neutral reference adapter:
  it validates proof strength and expiry before issuing invitation metadata,
  gives unknown and wrong proofs the same answer, accepts the named invitation
  once and creates the existing short-lived direct-member session.
- Added real `POST /v1/member/sign-in` handling. It accepts only a distinct
  `Invitation` authorization scheme and an empty body; a request cannot claim
  actor, Bridge, membership, permission, policy or decision time.
- Added invitation URL-fragment handoff to the generic member page. The page
  removes the fragment immediately, redeems it and keeps the returned member
  bearer in memory only.
- Proved that sign-in creates no Bridge binding, asset selection, installation
  or execution grant and that a Bridge bearer cannot be used for member sign-in.
- Recorded the approved product taxonomy: Agent Add-ons, Bridge Extensions and
  independent Applications may share discovery/governance, but retain separate
  package, installer, runtime, health and rollback contracts.
- Updated Architecture, Contracts, Roadmap, Tasks and the active Productization
  specification after implementation validation.

## In Progress

- PR #145 is open, mergeable and ready for owner review. Local verification
  and exact-head Platform verification are green.

## Remaining

1. Owner review and merge PR #145 after confirming its green required check.
2. Expose the member portal/sign-in composition from a deployable shared-platform
   process and link it from Personal Agent Web. Keep the member and Bridge
   credentials separate.
3. Productization 1 slice 3: expose the existing all-or-nothing synchronization
   as an explicit member Web action with typed before/after and refusal state.
4. Before a generalized Marketplace installer, define separate installer
   contracts for Agent Add-ons, Bridge Extensions and independent Applications.
5. Continue with generic Workflow launch, grounded Knowledge asking and then
   durable Registry storage.

## Architecture decisions made

- Invitation metadata, invitation proof, member session and Bridge access token
  are four distinct records/credentials.
- The invitation proof is a high-entropy bearer delivered out of band. Only its
  fingerprint is stored and it can be redeemed once.
- A member session cannot outlive the proof that produced it and carries no
  Bridge identity or membership claim.
- Invitation redemption is control-plane membership work. It never authorizes
  local capability execution.
- The current source repositories contain no member sign-in implementation to
  preserve. This slice **ADAPTS** the repository's proven invitation registry,
  fingerprint comparison and member-session boundary instead of introducing a
  second identity system.
- Agent Add-ons extend the Personal Agent with governed assets; Bridge
  Extensions add local executable capabilities behind Bridge policy;
  Applications remain independently deployed software products.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu run was performed.
Browser automation was not run; HTTP behavior was exercised over real loopback
sockets.

```text
Focused member/enrollment suite:
python -m pytest tests/test_member_signin.py tests/test_member_portal.py
  tests/test_member_authorization.py tests/test_enrollment.py -q
46 passed

Full suite (repository-writable basetemp/cache, browser test excluded):
python -m pytest --ignore=tests/test_browser.py -q --basetemp=<repo>/.scratch/...
1374 passed, 4 skipped

python -m ruff check .
All checks passed!

python -m ruff format --check .
298 files already formatted

python -m mypy src tests
Success: no issues found in 233 source files

python -m build --outdir .scratch/dist-invitation
Successfully built sdist and wheel; wheel includes
control_plane/member_signin.py

python -m pip check
No broken requirements found.

git diff --check
PASS

GitHub Platform verification run 36773758708
PASS in 3m50s, including pytest, Ruff, Mypy, build, pip check, Windows offline
preview install and artifact upload.
```

The four full-suite skips are existing Windows environment conditions:
symlink/link privileges, IPv6 loopback and directory links. The first full
suite attempt could not create pytest's default `%TEMP%` directory in the
managed sandbox; rerunning with an explicit repository-writable `--basetemp`
produced the green result above. The worktree's stale `.venv` was not used;
verification used the repository's Python 3.12.14 environment with this
worktree's `src` on `PYTHONPATH`.

## Known issues

- Invitation proofs, member sessions, invitations, packages and selections are
  still in-memory reference stores and are lost on process restart.
- This slice covers initial invitation redemption. It does not add a durable
  identity provider, password/passkey recovery or persistent browser login.
- The invitation delivery channel is a trusted deployment concern; this code
  returns the out-of-band link but sends no email or message.
- The member portal remains a reference server and is not yet composed into a
  deployed shared-platform command or linked from Personal Agent Web.
- Agent Add-on, Bridge Extension and Application installers are architecture
  boundaries only; no dynamic Extension loader is implemented in this PR.

## Next Recommended Action

After PR #145 passes final-head CI and merges, add the smallest deployable
shared-platform composition that owns enrollment, invitation sign-in, member
sessions and the member portal, then link Personal Agent Web to that entry
point. Do not begin a generalized Extension/Application installer until that
member path is reproducibly usable.
