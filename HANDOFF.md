# Handoff

Date: 2026-09-30 (Asia/Taipei)
Branch: `codex/agent-web-marketplace`
Base: `origin/main` at `20b31e0828f5abd264054e90432684691f92b8ce`

## Goal

Start Productization 1 by making the existing Personal Agent Web interface a
truthful view of the shared platform. The first slice must let an enrolled
Bridge discover published assets while keeping publication, device selection,
installation and execution authorization separate.

## Completed

- Added the active Productization 1 specification and updated Roadmap/Tasks.
- Added the read-only `catalog` operation to the existing authenticated
  Bridge/platform wire.
- Added typed `CatalogRequest`, `CatalogReply` and Bridge-side
  `CatalogOutcome` contracts.
- Applied visibility/ownership entitlement on the platform from its trusted
  membership record. The request carries no groups or entitlement claims.
- Added an optional credential-checked package description for discovery.
- Extended the Personal Agent Web shared-platform tab to list published assets
  and visibly separate `published`, `authorized` and `installed` state.
- Preserved the existing all-or-nothing `sync` operation as the installation
  path. Catalog reads contain no artifact bytes and create no selection,
  installation or execution side effect.
- Added integration coverage over the real control-plane HTTP transport and
  real loopback Agent Web API, including before/after synchronization state.
- Updated architecture and contract documentation after validation.

## In Progress

- The implementation is committed as `233940e`, pushed and open for review in
  PR #142: https://github.com/dragon0816/agentic-engineering-platform/pull/142
- Local verification and GitHub Platform verification are green. Human
  review/merge remains.

## Remaining

1. Confirm PR #142 Platform verification, then merge the shared-catalog slice.
2. Define the member-authenticated selection entry point for slice 2. Do not
   use the Bridge access token as a general browser session.
3. Add select/revoke UI only after that identity boundary is approved.
4. Expose existing synchronization as an explicit Web action with typed
   before/after state.
5. Add the generic Workflow launch form through the existing
   Agent/Gateway/Workflow/Bridge path, followed by grounded Knowledge asking.
6. Add a durable Registry only after the catalog user path and contracts have
   been validated.

## Architecture decisions made

- Team Platform remains Registry/control plane; the local Bridge remains the
  execution plane.
- Web is a projection and ingress. It does not own routing, policy,
  installation, authorization or execution.
- Publication, device authorization and installation are three independent
  facts in the API and UI. None grants capability execution permission.
- Catalog entitlement is computed from authenticated actor plus trusted
  platform membership. Client-supplied groups are not representable.
- Catalog failure leaves already-installed local-first assets usable.
- Apps will later be a user-facing presentation of governed Software assets;
  no overlapping core asset type was added.
- No Telegram/GitHub orchestration or production database was added in this
  slice.

## Verification

Supported target: Windows, Python 3.12. Browser automation excluded per owner
instruction; the Agent Web API itself is tested over a real loopback socket.

```text
.venv\Scripts\python.exe -m pytest \
  tests/test_platform_transport.py tests/test_agent_web.py \
  tests/test_contracts.py tests/test_registry.py \
  tests/test_member_authorization.py -q
93 passed, 1 skipped (IPv6 loopback unavailable)

.venv\Scripts\python.exe -m pytest --ignore=tests/test_browser.py -q
1361 passed, 4 skipped

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m ruff format --check .
291 files already formatted

.venv\Scripts\python.exe -m mypy src tests
Success: no issues found in 226 source files

.venv\Scripts\python.exe -m build
Successfully built agentic_engineering_platform-0.1.0.tar.gz and
agentic_engineering_platform-0.1.0-py3-none-any.whl

.venv\Scripts\python.exe -m pip check
No broken requirements found.

GitHub Platform verification run 36732055855
PASS in 3m55s, including pytest, Ruff, Mypy, build, pip check, Windows offline
preview install and artifact upload.
```

The four full-suite skips are existing environment conditions: symlink/link
privileges, IPv6 loopback and directory links. No Ubuntu run was performed.

## Known issues

- The Registry and control-plane service remain in-memory references.
- Interactive selection lacks a member-authenticated Web entry point. The
  Bridge credential is intentionally not widened to serve that role.
- Existing packages without the new optional description still appear with
  governed owner/version/dependency/compatibility metadata and an empty
  description.
- The previous Telegram/Hermes coordination handoff was stale after PR #140
  merged. This handoff replaces it; live coordination behavior was not changed
  here.
- GitHub warns that the current `actions/checkout@v4`, `setup-python@v5` and
  `upload-artifact@v4` actions target deprecated Node.js 20. GitHub currently
  forces Node.js 24 and the run passes; dependency upgrades are a separate CI
  maintenance change.

## Next Recommended Action

After this PR is merged, design Productization 1 slice 2 as a narrow identity
and selection contract: an authenticated member selects or revokes one entitled
Workflow for one bound Bridge, with contract tests proving that publication is
still not execution permission.
