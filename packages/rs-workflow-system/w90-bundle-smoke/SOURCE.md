# Workflow 90 — bundle_smoke (rs_workflow_system)

Strategy: **WRAP**. The job runs unchanged as an AEP governed script tool.

| | |
|---|---|
| Source | `dragon0816/rs_workflow_system@896046e8fe2170d21f9213e56e5ce2f93c05ba43` |
| Job | `host-bridge/jobs/bundle_smoke.py`, `host-bridge/jobs/_bundle_smoke_rules.py` (and the empty `jobs/__init__.py`) |
| n8n workflow | `workflows/90_bundle_smoke.json` (manual trigger → bridge job call → report); not migrated: the AEP Workflow, Agent Web, Telegram `/run 90` and schedules replace it |
| Vendored copies | `vendor/jobs/*`, byte-identical; `run.py` verifies their SHA-256 before importing |

## Contract

- Run parameters (from `PARAMS_SCHEMA`): `greeting` (text, optional; the job
  defaults to `hello`), `fail` (boolean, default false; makes the run fail).
- Result: the job's own report (`summary`, `greeting`, `host`, `checks` (5),
  `installedAssets`, ...). A raised job exits non-zero and the run fails with
  `script_failed`.
- Side effect: the job writes nothing, but AEP classifies every script tool
  as `execute`, so a run needs a Bridge grant with an approval reference and
  Telegram asks for a Run tap.
- Not carried over: the job's optional `configPath` / `BUNDLE_SMOKE_CONFIG`
  greeting file (per-install settings replace it if ever needed).

## Install

`script-tool.json` is a candidate (lifecycle `validated`, approvals pending).
The owner publishes and approves it before a Host can install it under
`assets/script-tools/engineering/rs-bundle-smoke-tool/1.0.0/`, with
`workflow.json` under `assets/workflows/` and `skill.json` under
`assets/skills/`, plus a grant for `rs-workflow.bundle-smoke.execute`.
Regenerate the manifests with `build_manifests.py`.

## Parity evidence

`tests/test_rs_w90_bundle_smoke.py`: the pinned job runs through Bridge
policy (default and named greeting, 5/5 checks, summary format, failure
reported, denied without a grant), the candidate is not installable before
approval, vendored files equal the pinned source, and manifests match the
generator.
