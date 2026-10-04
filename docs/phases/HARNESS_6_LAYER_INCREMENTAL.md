# Six-layer Agent harness improvement plan

Status: active (2026-10-04). The owner will validate the completed path in Agent Web before broader Workflow and product acceptance tests. This plan follows the current inventory in `docs/HARNESS_6_LAYER_STATUS.md` and keeps deterministic commands, Bridge authorization and existing Workflow contracts intact.

## Order and acceptance

| Slice | Layers | Deliverable | Acceptance |
| --- | --- | --- | --- |
| H1 | 3, 6 | Typed evidence-sufficiency assessment for one selected product/market cell | A matrix co-mention or two unrelated passages never becomes a verified fit; the exact missing evidence is returned without a model call. |
| H2 | 3, 4 | Bounded re-retrieval over the selected cell's missing facets | At most a declared number of retrieval attempts; every attempt records its query, Raw source IDs and unmet facets; exhaustion returns `needs_evidence`. |
| H3 | 4, 6 | Independent claim and artifact validation | A synthesized recommendation is accepted only when each material claim passes a separate Raw citation and acceptance check; failure routes to bounded retrieval or a concrete gap report. |
| H4 | 2, 4 | Skill-owned plan for ordinary Ask | An installed Skill can declare plan steps, success criteria and fallback; unknown or unavailable tools stop with `needs_input`, and a checkpointed plan can be inspected. |
| H5 | 1, 5 | Reusable task/domain routing policy | Known commands still bypass the model; ambiguous Skill selection asks rather than executes; selected capability scope is enforced by Bridge policy. |
| H6 | 1–6 | Agent Web vertical proof | One selected cell and one ordinary Skill request show route, plan, evidence, bounded observations and validation outcome; failures remain visible and do not silently become answers. |

H1–H3 use exact installed Knowledge and immutable Raw; they do not establish market fit from lexical matches. H4–H5 reuse the existing Agent, Skill, Task and Bridge boundaries. No new model provider, n8n dependency, external write or permission bypass is part of this plan. Each slice gets focused regression tests; the repository-wide verification runs at the owner's merge checkpoint.
