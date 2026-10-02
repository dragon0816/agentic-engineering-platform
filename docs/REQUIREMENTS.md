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

The host records an approval for the exact routed Gateway alias/URL and each
permitted data class in `host.json`. An endpoint URL or credential alone is not
approval; changing the URL, provider or credential clears the prior approval,
while changing only the model on the same route preserves it. Until
finer-grained provenance is available, every complete AEP
model request is classified `UNCLASSIFIED`. A PUBLIC external text-chat session
must be declared before its first message; it cannot inherit old history,
local persona text or command/tool results. A selected external CLI receives
only the complete explicitly PUBLIC history, and changing back to Gateway
removes the PUBLIC session declaration.

The owner explicitly approved this workstation's local LiteLLM route
`company` at `http://127.0.0.1:4000/v1` for `UNCLASSIFIED` data on 2026-10-02.
The editable, credential-free fragment is
`deploy/windows-preview/gateway-default.json`; its `models` and `credentials`
keys belong in the installed `host.json`. The approval field under `models` is:

```json
"data_approval": {
  "backend_id": "gateway",
  "endpoint_alias": "company",
  "endpoint_base_url": "http://127.0.0.1:4000/v1",
  "approved_classes": ["UNCLASSIFIED"],
  "approval_ref": "owner-approved/localhost-litellm-2026-10-02",
  "internal_gateway": true
}
```

The alias and URL must match the configured routed endpoint exactly. The
approval applies to this workstation's owner-identified LiteLLM route; another
host must make its own configuration decision. No secret value belongs in the
fragment or `host.json`.

The first implementation slice adds a provider-neutral backend profile,
health and exact-selection contract, then adapts the existing Gateway
conversation without changing its observable answer, failure or tool evidence.
No data classification, native CLI task execution or automatic fallback is
enabled by the first slice.

The portable-task slice defines a backend-neutral objective, task type,
initial classification, exact Skill/resource and allowed/prohibited capability
references, bounded execution constraints, expected artifact outputs and
host-repeatable checks. Allowed capability references are a requested scope,
not execution grants. The backend's normalized result remains a candidate.
Its durable run record carries a digest of that contract, trace, selected
backend and use history, effective data class, status, bounded observations
and artifact references, but not the
objective text, source contents or model reasoning. Resume requires the same
task contract. A backend's claim of success does not establish completion:
the host must inspect the actual artifact and record a passing independent
validation report. This contract slice does not enable native task execution
or change existing Workflow routing.

Bounded Agent decisions require a provider-neutral Decision Service. Without
an explicitly configured accelerator, the service must execute the existing
rule-first/Gateway path with the same result and number of provider calls;
it must never initialize, probe or wait for JEV. A configured accelerator is
eligible only for named decision types and after a trusted full-payload egress
authorization. Unknown, unsupported, failed and low-confidence accelerator
results fall back to the approved baseline, with payload-free provider,
latency, confidence and fallback evidence. Data classification, access-control
decisions, complex next-action planning and strict completion validation stay
outside accelerator authority. A JEV adapter is a later, benchmark-gated
slice; Phase 1A adds no JEV dependency or account requirement.
Ordinary Agent conversations must preserve the entire installed Skill command
catalog when acceleration is `NONE`. Any accelerated Skill candidate set must
be a nonempty subset of installed commands, and omitted commands must be
absent from both model-visible tools and executable dispatch bindings.

The initial data-class vocabulary includes `RESTRICTED`, but no existing
Gateway approval may list that class until a separately reviewed restricted
execution environment exists. PUBLIC native tasks remain subject to a fresh
whole-context policy decision; task metadata alone is never authorization.

After the harness, migrate the pinned `rs_workflow_system` behaviors through
typed adapters and parity tests. Distinguish per-install/user static settings
from per-run parameters and generate matching Web/chat/Telegram controls from
one schema. Resolve flexible `/run` aliases to exact installed Workflow
identities. Review Hermes Skills and validated Workflows for provenance,
license, dependencies and policy before publishing Marketplace defaults.
Finally, demonstrate SOP-to-Workflow, Knowledge and ordinary Skill use from
user-level entry points with independent validation.
