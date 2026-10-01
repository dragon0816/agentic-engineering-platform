# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/marketplace-lifecycle-ui`
Base: `origin/main` at merge commit `0df644d` (PR #172)
PR: #175 — https://github.com/dragon0816/agentic-engineering-platform/pull/175

## Goal

Complete Productization 3 slice 5 and its exit path: show local Bridge
Extension lifecycle evidence and independent Applications through the existing
Personal Agent Web/member marketplace boundaries without weakening their human
gates or combining their runtime semantics.

## Completed

- Productization 3 slices 1–4 are merged through PR #172.
- Added an atomic, secret-free `ExtensionLifecycleSnapshot` store. The bounded
  manager records active, unhealthy, disabled and rollback transitions by exact
  version and preserves failed-upgrade evidence while allowing only one current
  active/rolled-back runtime.
- Extended the host layout with identity-derived Extension staging and lifecycle
  paths.
- Personal Agent Web now lists only valid staged packages, joined with optional
  local runtime evidence. It shows staged/active/refused/unhealthy/rolled-back/
  disabled state, declared capabilities and the company/shared-device approval
  gate. It provides no activation endpoint.
- Renamed the direct-member page to Shared Capability Marketplace. Its Agent
  Add-on behavior is unchanged, and it now lists entitled independent
  Applications from `/v1/member/applications`. Only declared Web UI integrations
  become external links; API/MCP/Workflow metadata is descriptive.
- Updated architecture, contracts, roadmap, tasks and the Productization 3
  specification after the implementation passed its focused tests.
- Productization 3 is complete in repository code and has a reproducible
  Windows/Python 3.12 verification path.

## In Progress

- Wait for PR #175 exact-head Windows/Python 3.12 CI and auto-merge when green.

## Remaining

1. Run a production-like owner test from a packaged Windows preview when the
   team is ready to exercise a real signed Extension package and external App.
2. Choose the next approved product milestone before adding marketplace
   mutation semantics for Applications or broader Extension administration.

## Architecture decisions made

- Extension lifecycle state is local execution evidence, not Registry metadata
  or authorization. Reading it does not start code or add a capability grant.
- Extension activation stays outside Personal Agent Web and still requires the
  exact device/policy approval already defined by the runner.
- Applications remain external Software. They are discovered through a direct
  member session and never become Agent Add-ons or Bridge Extension packages.
- Personal Agent Web continues to link to the separate member origin rather
  than receiving or forwarding a member session or Bridge credential.

## Verification

Supported target: Windows, Python 3.12 only. No Ubuntu or browser automation.

```text
Focused Extension/Web/member/Application suite:
51 passed

python -m pytest --ignore=tests/test_browser.py -q
1449 passed, 4 skipped in 61.36s

python -m ruff check .
All checks passed!

python -m ruff format --check .
322 files already formatted

python -m mypy
Success: no issues found in 254 source files

python -m pip check
No broken requirements found.

python -m build --no-isolation --outdir <repo>/.scratch/build-p3-ui-final
Successfully built sdist and wheel.

git diff --check
PASS
```

## Known issues

- This slice verifies the dependency-free HTML contract and real HTTP APIs but
  intentionally does not run the separately maintained browser-automation suite.
- A real Extension operator/composition must pass the host's
  `ExtensionLifecycleStore` to `ExtensionManager`; the core host does not
  auto-activate publisher code.
- API, MCP and Workflow Application integrations are display metadata until a
  separately governed configuration flow is approved.

## Next Recommended Action

Merge the exact green head of this PR. Then use the updated phase/roadmap state
to define the next small product milestone; do not extend Application install
or Extension activation behavior without an approved contract and user-level
acceptance scenario.
