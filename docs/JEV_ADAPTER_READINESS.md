# JEV adapter readiness audit

Status: audit updated on 2026-10-03 after the owner chose the TypeSafe official
JEV API and PUBLIC-only first use. No live JEV request or credential use was
performed. An offline, injected-transport Skill-selection adapter now exists.

## Evidence inspected

- Owner handoff `CODEX_AEP_MULTI_BACKEND_ORCHESTRATOR_HANDOFF_JEV_READY.md` (local attachment), especially §§2A, 3, 20 Phase 8, and 21.
- `docs/MULTI_BACKEND_ORCHESTRATOR_JEV_PLAN.md`, `docs/REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, and `docs/DECISIONS.md`.
- `src/agent/decisions.py`, `src/agent/gateway.py`, `src/agent/routing.py`, `src/agent/data_policy.py`, `src/host_runtime/contracts.py`, and `tests/test_decision_service.py`.
- TypeSafe's official [OpenAPI schema](https://api.typesafe.ai/openapi.json), inspected on 2026-10-03.

## Verified in AEP

| Boundary | Current contract |
|---|---|
| Decision provider | `DecisionProvider[RequestT, ValueT].decide(request) -> DecisionResult[ValueT]` is synchronous and in-process. The result carries decision type, value, accepted flag, confidence, reason code, provider ID, and optional metadata. It is **not** a JEV wire schema. |
| Configuration | `CompanyHostConfiguration.decision_accelerator` defaults to `provider: NONE`. `JEV` configuration requires an endpoint, a symbolic `SecretRef`, and at least one enabled decision type. Endpoint validation permits HTTPS or loopback HTTP, and rejects URL credentials/query/fragment. Timeout defaults to 300 ms (range 1–5000 ms); confidence threshold defaults to 0.9. |
| Actual wiring | `RequestRouter` and `Gateway.converse` use `DecisionService`. The ordinary conversation's `skill_selection` baseline returns every installed command in order. `RequestRouter` observes final `route_selection`, which is not an allowed accelerator type. No JEV factory or whole-request authorizer is wired into the Host; enabling the config alone cannot call JEV and falls back to baseline. |
| Admission | Before constructing an accelerator, `DecisionService` requires its caller's `authorize_accelerator(request)` to return true. Candidate type, provider ID, acceptance, request-specific validator, and confidence are checked; failures fall back to baseline. Traces contain no request text. `skill_selection` additionally accepts only a nonempty subset of installed tool names and applies it to both display and dispatch bindings. |
| Data policy | `DataPolicy` already distinguishes `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`, and `UNCLASSIFIED`; unknown outranks known classes. Its current approval model is for Gateway backends, not a JEV service. `SkillCandidateRequest` contains the full user context and tool descriptions but carries no per-material classification. Existing approval of the local LiteLLM Gateway does **not** approve JEV data egress. |

The design permits acceleration only for `intent_classification`, `skill_selection`, `retrieval_routing`, and `failure_classification`. It keeps security classification, authorization, execution routing, planning, and strict completion checks on the baseline. Only Skill candidates have an ordinary conversation integration today; the other candidate types do not yet have a proven JEV insertion point.

## Verified TypeSafe wire contract and remaining unknowns

The owner selected TypeSafe's official API for the first integration. Its
[published OpenAPI schema](https://api.typesafe.ai/openapi.json) defines
`POST https://api.typesafe.ai/v1/systemone` with Bearer API-key authentication,
`state`, `model`, and named `questions`; a `choice` answer carries `choice`,
`confidence`, and `probabilities`. The authenticated `GET /v1/models` lists
available model names. `src/agent/jev.py` uses the choice schema for one
`skill_selection` question and accepts an injected transport for offline tests.
It never discovers models or sends a request on construction. The configured
model profile must be explicit. The schema documents token usage, but the
owner's pricing, rate limit, calibrated confidence, and data retention terms
are still unverified. The endpoint has not been contacted with a real key.

The Host administrator still needs to approve the exact TypeSafe endpoint and
PUBLIC-only egress. No current Agent Gateway session provides a complete
PUBLIC classification for its system/persona text, prior turns, and installed
tool descriptions, so the adapter remains unwired to live Agent chat. The
existing LiteLLM approval does not cover TypeSafe. `UNCLASSIFIED` and
RS Knowledge content must stay out of TypeSafe. A separate golden benchmark
and acceptance thresholds remain outstanding.

## Smallest safe next slice

1. Use the published TypeSafe schema and an injected fake transport against representative success, timeout, malformed response, and auth-failure fixtures. Keep the adapter absent for `NONE`.
2. Add a JEV-specific, exact-endpoint egress approval and classify the **entire** candidate request, including user text, Skill descriptions, evidence, and metadata, before constructing transport or resolving credentials. Denial uses the existing baseline. Never use JEV's own classification to authorize sending that same payload.
3. Implement one `skill_selection` adapter behind `DecisionProvider` using the verified wire schema and configured short deadline. Resolve a symbolic secret only after admission. Validate returned names against installed commands. Normalize failures without logging payloads or secret-bearing exceptions; use bounded temporary disable after repeated failures. The offline adapter is present; Host wiring, egress approval, and circuit breaker remain open.
4. Compare the same golden cases against the unchanged baseline: exact candidate set, accuracy/confusion, confidence calibration, p50/p95 latency, fallback rate, and cost. Keep `NONE` as the default and prove it constructs no client, performs no probe, and adds no network call. Expand to another decision type only after its own benchmark passes.

This audit does not authorize production JEV calls or change the current routing path.
