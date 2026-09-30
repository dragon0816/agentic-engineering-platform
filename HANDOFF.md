# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/shared-platform-portal`
Base: `origin/main` at merge commit `a2bd302` (PR #145)
PR: https://github.com/dragon0816/agentic-engineering-platform/pull/147

## Goal

Continue Productization 1 with slice 2c: compose the existing Bridge API,
invitation sign-in, member sessions and Member Portal into one deployable
Shared Platform reference process, then expose the separate Member Portal
origin from Personal Agent Web without reusing or forwarding the Bridge token.

## Completed

- Added `SharedPlatformState`, one owner for the in-memory enrollment,
  Bridge-token, package, authorization, remote-control, artifact and member
  session references.
- Added `SharedPlatformApplication`, which constructs the Bridge and member
  services over those exact references and starts/stops both HTTP listeners as
  one lifecycle.
- Added secret-free `SharedPlatformConfiguration` and `BootstrapInvitation`
  contracts. Non-loopback listening requires certificate and private-key paths;
  invitation proofs and key values have no configuration fields.
- Added the `aep-platform serve` executable. When bootstrap invitations are
  present it requires an explicit delivery file, creates it exclusively, and
  does not print proof-bearing links as ordinary service status.
- Added `examples/shared-platform.json` and an operator guide covering the TLS,
  invitation-delivery and in-memory-reference limitations.
- Extended `PlatformBinding` with optional `member_portal_url`. It is validated
  as a credential-free origin and is never used by `PlatformClient`.
- Personal Agent Web now projects and renders the separate Member Portal link.
  Catalog traffic continues through the Bridge API and Bridge credential.
- Proved over real loopback sockets that invitation redemption, later device
  binding/token issuance, Bridge probe and member Workflow catalog all observe
  the same enrollment state.
- Updated Architecture, Contracts, Roadmap, Tasks and the active Productization
  specification after the implementation passed focused verification.

## In Progress

- PR #147 is open. Exact-head GitHub Platform verification is pending.

## Remaining

1. Owner review and merge this slice after its exact-head CI is green.
2. Productization 1 slice 3: expose the existing all-or-nothing synchronization
   as an explicit Personal Agent Web action with typed before/after and refusal
   state.
3. Add generic Workflow launch, grounded Knowledge asking and then durable
   Registry storage in that order.
4. Before generalized marketplace installation, define distinct installer
   contracts for Agent Add-ons, Bridge Extensions and independent Applications.

## Architecture decisions made

- **ADAPT** the existing in-repository control-plane and member references.
  Source repositories contain no overlapping shared-platform member process to
  migrate, so no new identity, Registry or execution implementation was added.
- Bridge API and Member Portal share control-plane state and process lifecycle,
  not credentials or authorization semantics.
- The Member Portal URL is trusted local navigation metadata. It carries no
  session, proof or Bridge credential and may not use plain HTTP beyond
  loopback.
- Invitation metadata belongs in configuration; invitation proof delivery is a
  separate runtime output. The output file is a secret-bearing deployment
  artifact and never a Registry asset.
- TLS certificate/private-key paths may be configured; key contents and
  passwords are never configuration or asset fields.
- This slice deliberately retains in-memory stores. A durable Registry remains
  after the validated Workflow/Knowledge user paths, per the approved roadmap.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu run was performed.
Browser automation was not run; HTTP behavior was exercised over real loopback
sockets.

```text
Focused Shared Platform/member/transport suite:
python -m pytest tests/test_shared_platform_app.py tests/test_agent_web.py
  tests/test_platform_transport.py tests/test_member_signin.py
  tests/test_member_portal.py -q
54 passed, 1 skipped

Full suite (browser test excluded per owner instruction):
python -m pytest --ignore=tests/test_browser.py -q --basetemp=<repo>/.scratch/...
1380 passed, 4 skipped in 40.82s

python -m ruff check .
All checks passed!

python -m ruff format --check .
302 files already formatted

python -m mypy src tests
Success: no issues found in 236 source files

python -m build --outdir <repo>/.scratch/dist-shared-platform
Successfully built sdist and wheel; wheel contains control_plane/app.py and
control_plane/cli.py.

python -m pip check
No broken requirements found.

Fresh isolated wheel install:
pip install --no-deps --force-reinstall agentic_engineering_platform-0.1.0-py3-none-any.whl
aep-platform --help
PASS; the packaged executable exposes the `serve` command.

Installed-wheel runtime smoke:
aep-platform serve --config <scratch-config-with-free-ports>
  --invitation-output <scratch-delivery>
Bridge API health: true
Member Portal health: true
Invitation count: 1; expected actor and URL fragment shape confirmed without
printing the proof.

git diff --check
PASS
```

The four full-suite skips are existing Windows environment conditions:
symlink/link privileges, IPv6 loopback and directory links. Test caches and
temporary files were directed to the repository's writable `.scratch` area.

## Known issues

- Restarting the reference process loses members, invitations, sessions,
  packages, selections and device records. It is not the durable Registry.
- The CLI bootstraps invitations but has no administration UI/API for later
  device registration, binding, package publishing or invitation management.
- The invitation delivery file must be protected and removed by the operator;
  no email or messaging delivery channel is included.
- TLS configuration validation and SSL-context construction are covered, but
  this slice did not run against a real internal certificate or network DNS.
- Existing Bridge installations must add `member_portal_url` to `host.json`
  before Personal Agent Web can show the link.

## Next Recommended Action

After this PR merges, implement Productization 1 slice 3 as one reversible Web
action over the existing `PlatformClient.synchronize` path. Show the catalog
state immediately before and after synchronization, preserve the current
all-or-nothing verification, and return typed unreachable/refused states
without adding installation logic to the page.
