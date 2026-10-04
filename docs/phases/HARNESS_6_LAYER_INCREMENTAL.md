# Shared six-layer Agent harness plan

Status: active (2026-10-04). The owner will use Knowledge Asking first to inspect the behavior in Agent Web, while the harness itself must support Workflow/Task execution and Coding without Knowledge-specific assumptions.

The previous product/market `MarketCellSufficiency` is a Knowledge pilot. It is not the shared harness contract. Skill procedures, evidence needs and fallback guidance shape a plan; TaskContract and Host checks bound it; Bridge policy alone grants execution. A Knowledge adapter translates retrieval and Raw citations into common observations. It does not own the search strategy or final approval.

| Slice | Six-layer contribution | Acceptance |
| --- | --- | --- |
| G1 Shared plan contract | Intent, Skill/Planning, validation contract | One Skill-guided, provider-neutral plan envelope works for Knowledge, Workflow/Task and Coding fixtures. Skill guidance cannot add capabilities, remove Host checks or exceed the Task budget. A candidate Knowledge Asking Skill is versioned separately from the published 1.0.0 Skill. |
| G2 Bounded state machine | Context, reasoning loop, feedback | One shared transition model records route, plan, context observations, execution and independent validation. Missing evidence, failed checks and exhausted retries return structured stop states. Each of the three domains has a simulated negative case. |
| G3 Knowledge vertical slice | Knowledge adapter and first user-level effect | The candidate Knowledge Asking Skill drives evidence needs and bounded re-retrieval on one exact installed Vault. Agent Web shows the selected Skill, Raw coverage, missing facets, attempts and validation result; an unsupported recommendation is refused. Diagnose failures by routing, Skill plan, data coverage, retrieval, execution or validation evidence. |
| G4 Workflow/Task and Coding vertical slices | Existing Bridge/Workflow and Coding Harness adapters | The same plan/transition/validation envelope wraps one exact Workflow or Task and one bounded Coding run. Existing deterministic steps, grants, test cases and durable run artifacts remain authoritative. No LLM-selected target gains permission. |
| G5 Cross-domain acceptance | Independent validation and failure routing | A deliberate wrong output fails in each domain. A pass requires observed evidence and Host checks, never just a model or Skill claim. |
| G6 Agent Web proof | User-level validation | Knowledge, Workflow/Task and Coding traces are inspectable from Agent Web; the owner tests Knowledge first, then the other two applications. |

Each slice receives focused tests. Full repository verification is reserved for the owner's merge checkpoint. Do not add n8n as a core dependency, mutate the source Vault, or edit a published Skill version in place.

## Knowledge-first evaluation cases

`evaluation/knowledge/harness-cases-v1.json` is the test input for G3. The
standalone tier asks separately about market trends, product/option/spec data
and technical knowledge. The combined tier first compares market and product
evidence, then asks for a market/product/technical/competitor strategy with
SWOT and project execution actions. Every factual output needs Raw citations;
missing competitor, customer or fit evidence is an explicit gap, not an
invented recommendation. The case data defines questions and acceptance
facets, not pre-approved answers or a claim that the current Vault covers them.
