# Active requirements

## Multi-backend Personal Agent (approved 2026-10-02)

The owner approved the incremental design in
`MULTI_BACKEND_ORCHESTRATOR_PHASE0.md`. Strengthen the Agent harness before
continuing Workflow migration and product acceptance. Preserve deterministic
commands, installed-only Workflow execution, device admission, Bridge policy,
durable run evidence and existing user-visible result contracts.

The initial data rule is fail closed: unclassified material may go only to an
internal Gateway explicitly approved for that data; native Codex and Claude
Code backends require the complete transferred context to be explicitly
`PUBLIC`. Gateway outage must never cause a fallback to an ineligible backend.
This rule needs an enforced classifier and negative tests before native task
execution is enabled. The existing restricted CLI text-chat path does not
qualify as a governed native task backend.

The first implementation slice adds a provider-neutral backend profile,
health and exact-selection contract, then adapts the existing Gateway
conversation without changing its observable answer, failure or tool evidence.
No data classification, native CLI task execution or automatic fallback is
enabled by the first slice.

After the harness, migrate the pinned `rs_workflow_system` behaviors through
typed adapters and parity tests. Distinguish per-install/user static settings
from per-run parameters and generate matching Web/chat/Telegram controls from
one schema. Resolve flexible `/run` aliases to exact installed Workflow
identities. Review Hermes Skills and validated Workflows for provenance,
license, dependencies and policy before publishing Marketplace defaults.
Finally, demonstrate SOP-to-Workflow, Knowledge and ordinary Skill use from
user-level entry points with independent validation.
