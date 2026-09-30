# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/member-workflow-selection`
Base: `origin/main` at `d26d2de05acc9690f3fded8e710ba3fa58b73714`

## Goal

Continue Productization 1 with slice 2a: give an authenticated platform member
a provider-neutral entry point and generic page for selecting or revoking an
entitled Workflow for a bound Bridge, without treating the Bridge credential
as a browser session.

## Completed

- Added closed member contracts for catalog, select, revoke and selection
  replies. Requests cannot carry actor, groups, permissions, policy,
  approvals or decision time.
- Added a short-lived member-session reference. A trusted sign-in adapter may
  issue a session only from a current direct member authentication; an
  identity carrying a Bridge id or `bridge-access-token` is rejected.
- Stored only the session secret fingerprint. The issued secret is held in a
  deliberately non-serializable object whose repr is redacted.
- Added a transport-independent member service that checks the session,
  Bridge binding, platform membership, entitlement and existing selection
  rules before listing, selecting or revoking a Workflow.
- Added real HTTP endpoints at `/v1/member/catalog`, `/select` and `/revoke`.
  Plain HTTP is loopback-only; network exposure requires an SSL context.
- Added a generic dependency-free Workflow selection page. It accepts the
  short-lived session from an authenticated host in the URL fragment, removes
  the fragment immediately and keeps no browser storage.
- Proved over a real HTTP socket that select/revoke derives the actor and time
  on the platform, rejects an actual Bridge access token, refuses an unbound
  Bridge and does not change execution grants.
- Updated Architecture, Contracts, Roadmap, Tasks and the active
  Productization 1 specification after implementation validation.

## In Progress

- The implementation is pushed on `codex/member-workflow-selection` and open
  for review in PR #143:
  https://github.com/dragon0816/agentic-engineering-platform/pull/143
- Local verification and the first PR Platform verification run are green.
  Required-check review and owner merge remain for slice 2a.

## Remaining

1. Check PR #143's required Platform verification on its final head, then have
   the owner review and merge it.
2. Productization 1 slice 2b: connect the invitation-based shared-platform
   sign-in flow to trusted member-session issuance. Do not invent LDAP or
   reuse the Bridge credential.
3. After member sign-in is deployable, expose the member portal from the
   shared-platform process and link it from the Personal Agent Web.
4. Slice 3: expose the existing all-or-nothing synchronization as an explicit
   Web action with typed before/after state.
5. Continue with generic Workflow launch, grounded Knowledge asking and only
   then durable Registry storage.

## Architecture decisions made

- Member selection belongs to a separate Team Platform entry point. It is not
  another operation on the Bridge/platform wire.
- The authentication adapter decides who the member is. Member requests never
  carry identity or membership claims.
- The existing authorization registry remains the source of selection,
  entitlement and Bridge-binding rules; the page and HTTP layer add none.
- A Workflow selection affects synchronization state only. Capability grants
  and execution authorization remain unchanged.
- The in-memory session broker is a reference behind a trusted sign-in
  adapter, not a production identity provider or durable session database.
- No Telegram/GitHub coordination behavior, production database or execution
  path changed in this slice.

## Verification

Supported target: Windows, Python 3.12. Browser automation was not run per the
owner instruction; the member UI API was exercised through a real loopback
HTTP server.

```text
Focused integration:
python -m pytest tests/test_member_portal.py tests/test_member_authorization.py
  tests/test_platform_transport.py tests/test_agent_web.py
  tests/test_contracts.py -q
89 passed, 1 skipped (IPv6 loopback unavailable)

Full suite:
python -m pytest --ignore=tests/test_browser.py -q
1367 passed, 4 skipped

python -m ruff check .
All checks passed!

python -m ruff format --check .
296 files already formatted

python -m mypy src tests
Success: no issues found in 231 source files

python -m build
Successfully built agentic_engineering_platform-0.1.0.tar.gz and
agentic_engineering_platform-0.1.0-py3-none-any.whl

python -m pip check
No broken requirements found.

git diff --check
PASS

GitHub Platform verification run 36765721475
PASS in 3m58s, including pytest, Ruff, Mypy, build, pip check, Windows offline
preview install and artifact upload.
```

The four full-suite skips are existing environment conditions: symlink/link
privileges, IPv6 loopback and directory links. The managed worktree's old
`.venv` referenced a removed Python installation, so verification used the
repository's working Python 3.12.14 environment with this worktree's `src` on
`PYTHONPATH` and a writable project `.scratch` basetemp/cache. No Ubuntu run
was performed.

## Known issues

- There is no production invitation sign-in adapter yet. Tests provide the
  already-authenticated `AuthenticatedActor` that such an adapter must return.
- The member sessions, enrollment, packages and selections are still in-memory
  reference stores. Restarting the process loses them.
- The member portal is not yet wired into a deployed shared-platform command;
  this slice establishes and verifies its stable contracts and boundary.
- The Personal Agent Web remains read-only for shared selection until slice 2b
  supplies a real member sign-in/session handoff.
- GitHub Actions currently warns about Node.js 20 action runtimes and upgrades
  them to Node.js 24. Existing CI still passes; dependency upgrades remain a
  separate maintenance change.

## Next Recommended Action

Review and merge the slice 2a PR after exact-head CI passes. Then implement
slice 2b as a narrow invitation-based sign-in adapter that produces the
existing member session and opens the member portal; do not change the Bridge
transport, authorization registry or execution policy.
