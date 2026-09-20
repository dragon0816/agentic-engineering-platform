# Handoff — Phase 3 Gateway run control

Updated: 2026-09-21 (Asia/Taipei).
Branch: `phase-3/gateway-resume`, based on `main` at `c726a05` (PR #12 merged).

## Goal

Complete Phase 3 slice 6: host-facing run control through the Gateway so that
CLI, Agent runtime and a future n8n adapter inspect and resume runs through the
same Gateway and engine contracts as routed workflows, without giving routing or
models any way to trigger a resumption. Requirements: `docs/phases/PHASE_3_WORKFLOW.md`
(slice 6). No new source excerpt: this composes already-characterized behavior.

## Completed

- `src/agent/gateway.py`: `RunControlResult` (`action`, lenient `run_id`, `plan`
  for inspect, `workflow` snapshot for resume; validator forbids a payload that
  does not match the action) and `Gateway.inspect` / `Gateway.resume`, which
  validate the request context and delegate to `WorkflowEngine.inspect` /
  `WorkflowEngine.resume`. `ResumePolicy` and the caller-wait timeout are host
  options; the engine keeps its default timeout when none is given.
- 6 regression tests (`tests/test_gateway_resume.py`): result contract,
  inspect-then-resume with policy and `resumed_from`/trace checks, policy never
  read from the message, no authority (denied, then granted), other actors and
  unknown runs indistinguishable, and no routed request — including a model
  proposing a `resume` route or smuggling a run id into workflow arguments — can
  continue a run.
- Docs: phase spec slice 6 requirements and sequence, `docs/CONTRACTS.md`
  "Phase 3 Gateway run control", README.

## In Progress

- Opening the review PR for this branch; review and CI results are recorded on
  the PR once available.

## Remaining

- Review and merge the Gateway run-control PR after the posted review.
- Later Phase 3 slices: the durable step-state/persistence contract (must be
  scoped explicitly with the owner before any persistence code), progress
  streaming, and the optional n8n adapter invoking the same Gateway/engine
  contracts.
- Earlier deferred reviews remain: bounded Bridge event history, SkillRegistry
  parse cost, MCP installation round trips, Review `not_required` semantics,
  generic top-level package names, repeated RequestContext validation.

## Architecture decisions made

- Run control is a host-facing Gateway API, not a Skill route or a
  `RouteDecision` kind: no deterministic or model-selected route can inspect or
  resume a run, so a model can never choose to replay an uncertain effect. The
  Gateway parses nothing and adds no authority; ownership, pre-flight and
  re-authorization stay in the engine.
- `RunControlResult` reports "unknown to this caller" (both payloads None) for
  missing, evicted and other actors' runs alike, preserving the engine's
  indistinguishability rule at the entry point.

## Exact verification commands and results

Windows, Python 3.12.14, repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
# PASS: 277 tests (271 prior + 6 Gateway run control)
.venv/Scripts/python.exe -m ruff check .
# PASS
.venv/Scripts/python.exe -m ruff format --check .
# PASS: 65 files
.venv/Scripts/python.exe -m mypy
# PASS: 44 source/test files
.venv/Scripts/python.exe -m build
# PASS: sdist and wheel
git diff --check
# PASS
```

No production service, transport, model, job or n8n instance was invoked; inert
doubles only. Local pytest uses `-p no:cacheprovider` because of temporary
directory ACLs on this machine; CI runs ordinary pytest.

## Known issues / limitations

- Run control is in-memory like the engine: evicted runs are unknown.
- There is no HTTP/CLI surface yet; hosts call the Gateway API directly.

## Next Recommended Action

Open the PR for `phase-3/gateway-resume` against `main`, run the review, apply
confirmed findings and let the owner merge. Then scope the durable step-state
contract with the owner before writing any persistence code, or pick progress
streaming / the n8n adapter if durability is deferred.
