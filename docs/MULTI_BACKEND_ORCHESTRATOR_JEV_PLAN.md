# JEV-ready Decision Service integration

Status: Phase 1A implemented in source on 2026-10-02; the later JEV adapter
remains gated. Based on the owner-supplied
`CODEX_AEP_MULTI_BACKEND_ORCHESTRATOR_HANDOFF_JEV_READY.md` and the current
repository, not on a requirement to run JEV today.

## Repository mapping

The ordinary model route is `LocalAgent` -> `Gateway` -> `RequestRouter` or
`Gateway.converse` -> the host-approved `ModelClient`; exact Skill commands
and Bridge/Workflow execution remain deterministic. `src/harness` is the
existing coding/validation vertical, not the generic conversation loop.
`BackendRouter`, `GatewayModelBackend`, data policy and portable task contracts
already exist. The current JEV gap is a bounded decision boundary and its
provider/policy/trace contract, not a second execution harness.

## Phase 1A — reversible first slice

1. Define serializable `DecisionResult`, `DecisionTrace` and non-secret generic
   `DecisionAcceleratorConfig`. `DecisionProvider` is a typed in-process
   protocol; the default provider is `NONE`.
2. Put `DecisionService` around the existing `RequestRouter` decision. Its
   baseline provider preserves exact rule-first, one-model-call behavior and
   existing `RoutingOutcome` results. The approved model wrapper still owns
   Gateway egress control. No JEV SDK, account, endpoint or discovery call is
   required or constructed for `NONE`.
3. Make acceleration opt-in per decision type. Even when configured, the
   service must receive an explicit egress authorizer before constructing an
   accelerator. Missing authorization, provider failure, unsupported output,
   unknown result or low confidence falls back to the baseline. A trace records
   decision type, provider, elapsed time, confidence and fallback code without
   request text or evidence. The first integration observes final route
   selection, but only intent, Skill candidate, retrieval routing and failure
   classification may later be accelerated; execution route selection,
   security classification, completion and planning stay on the baseline.
4. Expose the configuration in the local host contract without a secret value.
   Existing `host.json` files deserialize to `NONE`. The service contract is
   ready for a JEV adapter, but Phase 1A does not ship one.

Acceptance: deterministic commands never call a model; ambiguous routing
makes the same one approved-model call and yields the same result; with `NONE`,
no accelerator factory, authorization callback, probe, retry or network call
occurs. Negative tests prove the optional path cannot construct an accelerator
before authorization and never blocks an otherwise available baseline.

## Later slices from the updated plan

After normal Agent ingress uses whole-context classification and host-owned
validation, add a golden decision dataset for intent/Skill candidates,
retrieval routing, failure and simple result classification. Measure accuracy,
confidence calibration, p50/p95 latency, fallback and cost against the
unchanged baseline. Only then implement an optional `JEVDecisionProvider` for
benchmark-proven decisions. It must use `DataPolicy` before any text, features
or metadata leave AEP, short timeouts and a circuit breaker. Authorization,
security classification, Bridge grants and strict completion validation stay
deterministic and outside JEV. Native Codex/Claude execution remains behind
the separately planned full-context policy and containment gates.

No installed preview configuration, Skill, Workflow or Marketplace asset is
changed by Phase 1A. The rollback is removal of the Decision Service wrapper;
stored task and Workflow state formats remain unchanged.
