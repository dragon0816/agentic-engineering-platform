# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/windows-preview-test-guide`
Base: `main` at `e5e97cda7c8c7e1c0ba905546d444706a16b3477`
PR: pending

## Goal

Make the two deployment roles explicit and independently installable: Personal
Agent Web + Bridge on company/test computers, and Shared Platform on the
Registry/Marketplace computer. Put a version-matched test manual inside each
artifact and surface the correct Agent + Bridge download in automated Hermes
validation Issues.

## Completed

- Added `START-HERE.md` to the existing `aep-windows-preview-<SHA>` artifact and
  explicitly identified it as the Personal Agent Web + Bridge role.
- The Agent guide covers Python 3.12 installation, the fixed local Gateway URL,
  Web startup, Ask, deterministic Workflow execution, Knowledge, Improve,
  Shared Platform synchronization, expected results and sanitized evidence.
- The Agent bundle builder now refuses to build without both operator guides.
- Added a separate offline Shared Platform bundle builder and Windows template.
  Its GitHub artifact is `aep-shared-platform-windows-<SHA>`.
- The Shared Platform bundle installs `aep-platform serve`, a loopback-safe
  `platform.json`, Registry workspace, start/verify/uninstall launchers and its
  own Traditional Chinese operator guide.
- Each role installer removes the other role's executable entry point. Shared
  Python contracts remain common, but the deployed processes are separate.
- Windows CI installs and verifies both bundles. It starts the Shared Platform
  on isolated CI ports, opens the real Member Marketplace over HTTP, confirms
  the durable SQLite Registry and uploads both artifacts.
- Hermes deployment validation remains pinned to the backward-compatible
  Agent + Bridge artifact name. Each generated Issue now contains its workflow
  run, artifact name and instruction to open the bundled `START-HERE.md`.
- Updated Architecture, Roadmap, Tasks, README and deployment documentation.

## In Progress

- Commit the coherent two-role packaging change, open a PR, wait for exact-head
  Windows/Python 3.12 CI, merge after green, then wait for merged-main artifacts.

## Remaining

1. Download the two merged-main artifacts and follow each bundled
   `START-HERE.md` on its intended computer.
2. Configure the Shared Platform computer's non-loopback address, TLS
   certificate/private key and firewall before a company Bridge connects.
3. The Shared Platform reference process still keeps members, invitations,
   sessions, authorizations and remote jobs in memory; only package metadata and
   bytes are durable in SQLite. Production durability remains future work.
4. Phase 7 workflow/source parity and E2E-01 physical DUT validation remain the
   active production-like work after deployment usability is confirmed.

## Architecture decisions made

- Agent + Bridge is the execution-plane deployment; Shared Platform is the
  control-plane deployment. They are separate artifacts from one source commit.
- The existing Agent artifact name remains `aep-windows-preview-<SHA>` for
  Hermes compatibility. Its role is made explicit in UI text, Issue text and
  the bundled guide rather than breaking the external allowlist now.
- Packaging may share the project wheel and contracts, while installers expose
  only the entry point for their deployment role.
- Shared Platform installs loopback-only by default. Non-loopback operation must
  supply TLS paths and deliberate firewall configuration.
- A missing guide is a build failure. Operator instructions are part of the
  product and must match the exact artifact revision.

## Verification

Supported target: Windows, Python 3.12 only. Ubuntu and browser automation were
not run.

```text
python -m pytest --ignore=tests/test_browser.py -q
1470 passed, 4 skipped in 65.21s

python -m pytest tests/test_windows_preview_bundle.py \
  tests/test_shared_platform_preview_bundle.py \
  tests/test_deployment_validation_loop.py -q
16 passed in 0.69s

python -m ruff check .
All checks passed!

python -m ruff format --check .
330 files already formatted

python -m mypy
Success: no issues found in 257 source files

python -m build --no-isolation --outdir <scratch>/build-two-bundles
Successfully built sdist and wheel

python -m pip check
No broken requirements found.

PowerShell parser over both bundle templates
PASS

Real Shared Platform offline package smoke on Windows/Python 3.12:
- built ZIP from the local wheel and downloaded dependency wheel set
- installed with --no-index
- verify.cmd PASS
- aep-host.exe absent from the Shared Platform role
- Member Marketplace HTTP GET PASS on an isolated port
- SQLite Registry created

git diff --check
PASS
```

## Known issues

- Ports 8765/8766 were already occupied on this development computer. The new
  process correctly refused to start without touching that listener. The smoke
  passed on isolated ports 18775/18776, and CI uses 18765/18766.
- The Agent + Bridge artifact still has its historical generic name for Hermes
  compatibility. Do not infer role from the name; read `START-HERE.md`.
- The Shared Platform package is a reference preview, not a production identity,
  HA, backup or fully durable control-plane deployment.

## Next Recommended Action

Commit and open the PR. Merge only after the exact head passes Platform
verification, then report the two merged-main artifact links and let the owner
test the Agent + Bridge package on the company computer and the Shared Platform
package on the shared computer.
