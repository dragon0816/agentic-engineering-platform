# Handoff

Date: 2026-10-01 (Asia/Taipei)
Branch: `codex/personal-agent-web-usability`
Base: `origin/main` at `1e846160`
PR: pending

## Goal

Make the Personal Agent Web usable without editing JSON by hand: expose
actionable readiness and installed commands, configure the existing
OpenAI-compatible model Gateway safely, and keep the existing governed
Marketplace, Workflow, Knowledge and Bridge Extension boundaries visible.

## Completed

- Added the Productization 4 incremental specification and roadmap/tasks.
- Added a closed `ModelSettingsUpdateRequest`. It accepts endpoint metadata,
  model id, routing alias and optional `SecretRef`/environment-variable names;
  extra fields such as an API-key value are rejected.
- Added authenticated `/api/readiness` and `/api/settings` projections plus
  `/api/settings/model` for a validated, atomic `host.json` update.
- Passed the actual CLI config path to Personal Agent Web. Tests that construct
  the Web without one remain read-only.
- Added a Settings tab prefilled for the owner-provided Gateway
  `http://127.0.0.1:4000/v1`; the model id remains explicit.
- Added Ask-page readiness cards and clickable command hints derived from
  installed `SkillManifest` command bindings. Clicking fills the request and
  causes no execution.
- Kept Skills, Workflows, Knowledge, Agent profiles, Bridge Extensions and the
  Shared Capability Marketplace visible through their existing governed paths.
- Removed the startup deadlock where installed Knowledge plus no routing model
  invalidated the entire host. The Agent Web and deterministic Workflows now
  start; the Knowledge capability remains unregistered until its model
  prerequisite is configured.
- Updated the Windows preview instructions for safe model setup.

## In Progress

- Open the PR, pass exact-head GitHub Actions, merge, and use its successful
  Windows preview artifact for an owner-visible UI check.

## Remaining

1. Productization 4 slice 3: durable local conversation sessions,
   clarification and human-readable history.
2. Slice 4: a provider-neutral bounded tool loop with progress/evidence. The
   current model performs one routing decision; it is not yet a Hermes-style
   general conversation/tool loop.
3. Slice 5: standardized feedback and candidate Skill/Workflow creation from
   the conversation workspace, retaining validation/review/publishing gates.
4. Add a separately governed Bridge Extension staging/activation operator UI
   only after its device-admin identity and approval contract is defined.

## Architecture decisions made

- The Web remains a loopback ingress and projection; it does not own routing,
  execution, installation or authorization.
- Model settings reuse `ModelBinding`, `ModelCatalog`, `SecretRef` and
  `CredentialBinding`. The page never accepts a credential value.
- Saving configuration is the operator's explicit write action. The complete
  `CompanyHostConfiguration` validates before one atomic replacement, and a
  restart is required before the running Agent uses it.
- Missing model routing makes model-dependent Knowledge unavailable without
  disabling deterministic local capabilities or the setup interface.
- Command discovery is manifest-driven, so new Skills appear without core Web
  changes.

## Verification

Supported target: Windows, Python 3.12 only. Browser automation was not run.

```text
Focused Host/Model/Web integration:
80 passed

python -m pytest --ignore=tests/test_browser.py -q
1455 passed, 4 skipped in 64.14s

python -m ruff check .
All checks passed!

python -m ruff format --check .
323 files already formatted

python -m mypy
Success: no issues found in 254 source files

python -m pip check
No broken requirements found.

python -m build --no-isolation --outdir <scratch>/build-web-usability
Successfully built sdist and wheel.
```

## Known issues

- The Gateway model id is deployment configuration and cannot be inferred from
  the URL alone; the operator must enter the id served by the Gateway.
- The current natural-language path chooses one installed Skill command. It
  does not yet retain a conversation or iterate through multiple tool calls.
- An old invalid `knowledge[].manifest` field is still rejected as an unknown
  configuration field. The current installer/configuration contracts never
  write it.
- Bridge Extension lifecycle is visible, but activation remains outside the
  Personal Agent Web behind the existing device-owner/policy gate.

## Next Recommended Action

Finish the PR/CI/merge/artifact path for this slice. Then implement durable
conversation sessions before adding the bounded tool loop, so progress and
clarification have a stable local record rather than living only in the page.
