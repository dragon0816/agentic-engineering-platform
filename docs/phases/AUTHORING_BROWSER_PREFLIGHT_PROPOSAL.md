# Governed browser preflight during authoring repair

Status: proposal awaiting explicit owner consent; no implementation authorized.
Date: 2026-11-11. Owner rule: AGENTS.md22.

## Problem and observed boundary

After recovering the dedicated browser's authentication, the resident AEP Agent
read the original SOP, navigated to Sales Orders, applied All and the prescribed
date range, and observed765 records/26pages. It independently drafted
wf-20261110-201153-ff4b99 and revised it twice. All3 approved full trials failed
in navigation, before the Excel step: ensure_visible target timeout, click target
missing, then a navigation wait timeout. No accepted report or installed Workflow.
The owner authorized testing; this does not authorize harness modification.

Both sop_workflow and c4c_navigation were actually selected. Domain Skill1.0.2
explicitly requires testing proposed targets with the same operation semantics
before submitting another full trial. The automatic continuation in
host_runtime/web.py:1269 permits inspection, planning, patching and requesting
a full trial, but excludes browser__operate and coding__run. agent/gateway.py:990
filters tools, hints and bindings before the model request. A Skill cannot grant
an excluded tool, including by introducing another alias. Full Workflow trial
validation is available; live incremental browser preflight is unavailable.

Existing regression test_failed_authoring_resumes_once_with_only_safe_tools_and_retests
captures real model requests and explicitly asserts that absence. It passed
unchanged:1test/11.27s. Read-only AST extraction independently confirms the
allowlist. Evidence: .scratch/c4c-preflight-sop-20261111/
repair-preflight-causal-proof.json and evaluation.json, raw result-5..8.json.

This is not a claim that every navigation failure is caused by that restriction.
The initial authoring turn had browser access and still compiled an unverified
navigation sequence; Skill guidance for preserving tested actions remains useful.
Preflight access alone does not establish final business correctness.

## Alternatives

1. Recommended: candidate-scoped, governed browser preflight in the existing
   automatic repair phase. A repair can validate its changed navigation before
   consuming another complete trial, subject to normal technical authorization.
2. Retain Skill-only repair and full trials. No runtime change, but a Skill still
   cannot make the missing preflight operation available. Further instructions
   may improve the first draft; they do not remove this deterministic boundary.
3. Add unrestricted browser__operate to the repair allowlist. Rejected: the
   current host-tool adapter invokes Bridge with its default person origin;
   directly widening the allowlist is not sufficient approval/provenance control.

## Smallest scope proposed for owner approval

Permit browser preflight only for the active unfinished candidate whose failed
step is already a browser/operate step of an owner-approved trial. Bind the
preflight to actor/session, current candidate digest, failed-step scope and its
original authorized origin. Use existing Bridge authorization and explicit model
provenance; require the normal approval whenever execution is not already
authorized. No execution on pending/refused/stale approval. Do not turn an
automatic continuation into a new owner-origin grant.

Keep the default repair tools restricted for every other task. Do not enable
coding, desktop, messaging, installation or arbitrary capability tools. Do not
expand allowed origins, grants, secrets or browser safety behavior. Keep the
three-full-trial limit and the existing bounded turn/tool budget; scope preflight
to at most two approved requests per repair pass. A successful preflight never
marks the Workflow verified or installable: an exact full trial and business
output acceptance are still required.

The approved outcome would be this behavior only; detailed contracts and the
implementation plan follow consent. If implementing normal approvals requires
another continuation/state change outside this scope, return with that concrete
expansion for consent first. Do not silently change general conversations,
Knowledge routing/retrieval/asking, attachment handling or persistent memory.
Keep C4C selectors, date/FX/mapping logic and output methods in Skills/Workflows.

## Verification required before delivery

- Selected Skill requests preflight: current behavior omits it; approved browser
  repair can request it and receives real execution/refusal evidence.
- Only an active matching browser failed step is eligible; unrelated tasks,
  stale/cross-session/different-digest candidates and unsupported origins refuse.
- Model provenance is enforced; approval-pending/refused requests have zero
  handler calls. Exact approved arguments execute at most once; no extra grant.
- Coding/desktop/mail/install stay unavailable. Preflight cannot replace saved
  requirements/downstream code or manufacture full-trial verification.
- Existing repair/full-trial limits and successful-call deduplication remain;
  Knowledge isolation regressions remain unchanged and pass.
- Re-run actual C4C development with the original prompt/files, disclose the
  earlier browser-authentication intervention, and independently reconcile final
  Excel against source totals/IDs, filters/dates, mapping, currencies and totals.
- Run applicable focused tests, normal full suite, lint/format/typecheck/build
  and official canary/resident checks before claiming implementation delivered.

No harness code, tests or permission policy has been changed for this proposal.
