# Governed browser preflight during authoring repair

Status: owner approved scope delivered as513784d0; actual preflight path exercised.
C4C novice business acceptance still failed; domain Skill revision awaits approval.
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

## Approved implementation contract and slices

The owner explicitly replied「好的同意修改」twice after reviewing this proposal.
Consent applies to this bounded repair preflight only. No broader harness work.

1. Add closed local contracts for a repair scope (actor/session/candidate, actual
   failed trial/digest/attempt, failed browser step and original origins) and a
   preflight action request (current digest,1..8 documented browser actions).
   Resolve only fixed/run inputs from the saved actual trial values; reject
   previous-step-dependent inputs and unsupported collection loops for preflight.
2. Offer authoring__preflight_browser through existing turn_host_tools ONLY in
   an eligible repair pass. The model tests small proposed corrections BEFORE
   its existing scoped patch. No general tool registry or Knowledge changes.
3. Reuse capability approvals with a reserved authoring-preflight source and a
   typed envelope in arguments. This preserves ApprovalRequest's schema; older
   code rejects the envelope as invalid BrowserRequest before any handler call.
   Approval commits the scope, candidate digest and exact browser arguments.
   Always wait for explicit approval before executing, at most2requests/pass.
4. On approval, revalidate scope/digest/origins/arguments and durably claim the
   request before dispatch. Use model provenance and a single-call confirmation
   adapter with the normal approved-trial authorization narrowed to that failed
   capability. Its temporary grant is never added to the resident policy.
   Scope origins through a host-only ContextVar in the existing browser handler;
   normal requests are unchanged. Return real observations/failure evidence.
5. Only these approvals can resume the SAME bounded repair pass; durably claim
   continuation once. Keep its original trial/attempt and do not renew budgets,
   mark verification or permit downstream replacement. Track execution as active
   work so restarts cannot interrupt it. Preflight records stay separate from
   AuthoringTask/Knowledge state. Rejected/stale requests stop without acting.
6. Tests first: contract negatives, fake-browser integration, authorization and
   at-most-once checks, eligible-only model tool discovery, approval continuation,
   unchanged nonbrowser repair and Knowledge isolation. Then focused/global/full
   verification, package/canary/guarded resident update and fresh novice C4C replay.

Implemented source scope: three host_runtime preflight modules, small integration
changes in chat_authoring.py/web.py/web_page.py and a request-local origin scope
in the browser-session handler. Independent review found that consuming returned
Gateway counts cannot preserve the approved same-pass budget: Host-check retry
returns only one pass's evidence. Therefore agent/gateway.py has an optional
request-local accounting callback, charged before each actual model/tool request.
Only eligible repair passes set it; ordinary conversations and Knowledge leave it
unset. Persistent counters and a fixed deadline include approval continuations,
without renewing the three-trial limit. This implements the approved no-renewal
constraint, not a general turn-budget redesign. Approval cards show exact actions,
values, sites and digest before execution. No new dependency, global tool exposure
or general permission-policy modification.
