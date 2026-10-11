# Multi-backend Agent Orchestrator — approved incremental design

Status: approved by the owner on 2026-10-02 for slice 1 implementation.
Source inventory, architecture gaps and all nine slices are recorded in
`../../archive/MULTI_BACKEND_ORCHESTRATOR_PHASE0.md`.

## Boundary

The Personal Agent owns admission, task/backend choice and observable result.
The AEP Gateway owns its bounded model/tool loop; Bridge and Workflow engine
retain deterministic execution and policy. A native Agent adapter may later own
its internal loop, but may not inherit Bridge grants or an unclassified
conversation merely because it is installed. Registry remains discovery and
distribution only.

The first slice changes only ordinary Gateway conversation dispatch. A closed,
serializable backend profile identifies backend kind (`model` or `agent`),
harness (`aep` or `native`) and declared features. It cannot express execution
permission. A separate health projection distinguishes unknown liveness from
unavailability. An exact-selection router refuses unknown, ineligible or
unavailable backend IDs; it never tries another backend implicitly. The
Gateway adapter accepts the existing request context, bounded history and
persona guidance, then returns the existing `GatewayConversationResult`
unchanged. The only registered and eligible backend in slice 1 is Gateway.

Tests first: reject inconsistent profile kind/harness pairs, reject duplicate
IDs and ineligible/unavailable selections, verify Gateway request/result
equivalence including failures and tool evidence, and regress LocalAgent
admission and run recording. Then run focused and full repository checks.

## Subsequent slices and security gate

Next, classify each material item with provenance; compute the effective
classification of the complete outbound context and record an eligibility
decision before any backend receives bytes. Unknown content is denied to
native external backends. No fallback can change that decision. Then add
portable task/run state and independent completion validation. Only after
negative policy and workspace/credential containment tests pass may PUBLIC
tasks use native Codex/Claude adapters. Workflow parameter, source migration,
Marketplace and product evidence follow the sequence in the Phase 0 audit.

No network, credential, repository publication or external side effect is
required by slice 1. Its rollback is removal of the adapter and restoring the
direct `LocalAgent.converse` call; stored state and wire result formats do not
change.
