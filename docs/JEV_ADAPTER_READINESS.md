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
existing LiteLLM approval does not cover TypeSafe. On 2026-10-03 the owner
declared the complete `RS_Knowledge` Vault public. The Host records this with
`privacy: "public"` on that Vault's binding; each Vault has an independent
`private` or `public` setting chosen by the owner. This removes the earlier
source-specific prohibition for RS_Knowledge. A separate golden benchmark and
acceptance thresholds remain outstanding.

The owner changes one Vault at a time in
`%LOCALAPPDATA%\AgenticEngineeringPlatform\preview-0.1.0\host.json` under its
`knowledge` entry:

```json
"privacy": "public"
```

The other accepted value is `"private"`; omitted means private. Restart the
Agent Host after changing the file. This setting contains no credential.

## Smallest safe next slice

1. Use the published TypeSafe schema and an injected fake transport against representative success, timeout, malformed response, and auth-failure fixtures. Keep the adapter absent for `NONE`.
2. Add a JEV-specific, exact-endpoint egress approval and classify the **entire** candidate request, including user text, Skill descriptions, evidence, and metadata, before constructing transport or resolving credentials. Denial uses the existing baseline. Never use JEV's own classification to authorize sending that same payload.
3. Implement one `skill_selection` adapter behind `DecisionProvider` using the verified wire schema and configured short deadline. Resolve a symbolic secret only after admission. Validate returned names against installed commands. Normalize failures without logging payloads or secret-bearing exceptions; use bounded temporary disable after repeated failures. The offline adapter is present; Host wiring, egress approval, and circuit breaker remain open.
4. Compare the same golden cases against the unchanged baseline: exact candidate set, accuracy/confusion, confidence calibration, p50/p95 latency, fallback rate, and cost. Keep `NONE` as the default and prove it constructs no client, performs no probe, and adds no network call. Expand to another decision type only after its own benchmark passes.

This audit does not authorize production JEV calls or change the current routing path.

## Self-hosted Laya SystemOne run (2026-10-05)

The owner runs `laya-serve 0.1.0` (`POST /v1/systemone`, Bearer token, the
`model` field is ignored and the reply names `laya-rl-agent`; it routes by
language, English to `convaiinnovations/laya`). It was reached through an SSH
tunnel (`ssh -N -p 2222 -L 18000:127.0.0.1:8000 openlab@172.25.228.141`) at
`http://127.0.0.1:18000/v1/systemone`, token in `AEP_JEV_API_KEY`. The reply
shape passes the adapter's validation unchanged.

`python -m evaluation.jev_live --model laya-rl-agent --endpoint
http://127.0.0.1:18000/v1/systemone --trials 3` (reviewed PUBLIC corpus,
4 skill cases): 12/12 answered, exact accuracy 0.25 (baseline 0.25),
latency p50 376 ms / p95 638 ms, Brier 0.238.

Findings:

1. The adapter sends the whole `ModelRequest` JSON as `state` (~280 state
   tokens for a one-line request). Laya then picks option 1 for every case
   with near-uniform probabilities and confidence about 0.02. With
   `state = {"message": <user text>}` the same cases give: file -> 1 (correct,
   0.84), report -> 3 (correct, 0.51), wiki -> 0 (preserve, 0.05), broad -> 1
   (0.06). The state shape, not the service, caused the 25 %.
2. The benchmark counts a provider answer as "answered" without the
   DecisionService confidence threshold (default 0.9), so it overstates what
   live routing would accept; at 0.9 every Laya answer above is rejected.
3. Latency is above the Host default accelerator timeout of 300 ms.
4. The corpus has four skill cases with placeholder tool descriptions
   ("Synthetic installed command X"); it cannot show useful accuracy.

### Follow-up the same day: state shape, threshold, live-catalogue corpus

- Adapter: `state` is now `{"message": <latest user message>}`; system and
  persona text, earlier turns and tool schemas are no longer sent.
- Benchmark: `--threshold` (default the Host's 0.9) decides whether a choice
  is admitted; a new `jev-systemone.with-fallback` column scores what a person
  gets (admitted choice, else the whole catalogue) against the baseline.
- Corpus `--corpus skills` (`evaluation/jev/golden-v2-skills.json`): 26 PUBLIC
  cases, English and Chinese, over the eight installed Skill commands with
  their real descriptions; six broad, chit-chat or multi-command cases expect
  the whole catalogue.

Laya, 26 cases x 3 trials (exact accuracy; baseline 0.231):

| Threshold | Admitted | Admitted correct | With fallback | p50 / p95 |
|---|---|---|---|---|
| 0.9 | 9 / 78 | 9 (100 %) | 0.346 | 216 / 439 ms |
| 0.3 | 42 / 78 | 30 (71 %) | 0.577 | 230 / 416 ms |

Before the state change the same corpus scored 0.115 raw with every answer
below 0.15 confidence. A wrongly admitted choice hides the right tool from the
model, so precision matters more than coverage; the threshold is an owner
decision. Weak spots: Chinese short commands (proof, checklist), knowledge
questions confused with the market matrix, and broad/chit-chat requests that
should keep the catalogue. Latency p95 still exceeds the 300 ms default.

### Selector hints (2026-10-05)

Skills now carry `selector_hint` and the adapter uses it (DECISIONS
2026-10-05). Corpus `--corpus skills-v3` (`golden-v3-skills.json`, 46 cases:
the 26 above plus 20 held-out paraphrases, with hints), Laya, 3 trials,
baseline 0.217:

| Threshold | Admitted | Admitted correct | With fallback | p50 / p95 |
|---|---|---|---|---|
| 0.9 | 15 / 138 | 100 % | 0.326 | 262 / 611 ms |
| 0.5 | 69 / 138 | 91 % | 0.630 | 271 / 526 ms |

Still weak: multi-task requests answered with one tool at high confidence,
and SOP-to-workflow vs NCC document requests. The threshold remains an owner
decision; latency p95 remains above the 300 ms default.

### Intent first, then Skill (owner question, 2026-10-05)

Hypothesis: classify the request (task execution, knowledge asking, coding,
or general chat / several tasks) and then choose among that class's Skills.
Measured on Laya over the 46 skills-v3 cases (scratch experiment, not
shipped):

| Strategy | Intent correct | Exact set | Right tool still offered | Avg tools |
|---|---|---|---|---|
| Flat Skill choice with hints, threshold 0.5 (current) | - | 67 % | 89 % | - |
| 4 intents, then Skill within the class | 67 % (50 cases incl. 4 coding) | 46 % | 70 % | 2.8 |
| 3 intents (coding folded into task), then Skill | 80 % | 52 % | 87 % | 3.6 |
| 3 intents, intent ignored below 0.3 | 80 % | 50 % | 91 % | 5.3 |
| Intent and Skill asked in one call | - | 24 % | 89 % | 6.7 |

Intent-first lowered the hit rate: the two decisions' errors multiply, the
classes overlap (an SOP-to-workflow request is both task and coding; "fix the
failing test" was read as a task), and good hints already carry the class.
With eight installed commands a flat choice is easier than two chained ones.
An intent layer is worth revisiting when the catalogue grows to dozens of
Skills, and intent remains useful as a routing signal for which harness runs
(Knowledge, coding, task) rather than as a tool filter.

### Most-likely lists and shadow mode (2026-10-05)

Adapter options on skills-v3 at threshold 0.9 (46 cases x 2):

| Mode | Narrowed | Right tool still offered | Right tool hidden | p50 |
|---|---|---|---|---|
| Single best | 11 % | 100 % | 0 / 92 | 237 ms |
| Up to 3 tools by probability | 46 % (1.6 kept) | 96 % | 4 / 92 | 278 ms |
| Either + "several tasks?" question | unchanged | unchanged | unchanged | ~450 ms |

Shadow mode is built (DECISIONS 2026-10-05) and off until the owner adds an
`egress_approval`. To enable it, in `host.json`:

```json
"decision_accelerator": {
  "provider": "JEV",
  "endpoint": "http://127.0.0.1:18000/v1/systemone",
  "credential": {"name": "jev_api_key"},
  "model_profile": "laya-rl-agent",
  "timeout_ms": 1500,
  "enabled_decision_types": ["skill_selection"],
  "mode": "shadow",
  "skill_max_tools": 3,
  "egress_approval": {"approval_ref": "<owner approval reference>"}
}
```

plus `{"secret": "jev_api_key", "environment_variable": "AEP_JEV_API_KEY"}` in
`credentials`, the SSH tunnel running, and an Agent Web restart.
