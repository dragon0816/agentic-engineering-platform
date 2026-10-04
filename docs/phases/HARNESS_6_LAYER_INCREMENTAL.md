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

The first G3 path was opt-in and reported facet coverage as `not_assessed`.
The current candidate Skill adds a typed Knowledge procedure, per-facet Raw
retrieval, bounded fallback searches for missing facets and independent Host
checks of cited facets and direct relationships. These checks establish
observable source support, not semantic entailment or product/market fit.
The Host still refuses an unsupported recommendation and preserves exact
Bridge authorization. The shared runner contains no Knowledge-specific rules.

## Knowledge-first evaluation cases

`evaluation/knowledge/scenarios-v1.json` is the test input for G3. The
`evaluation.knowledge_scenarios` module validates the shape of these cases; it
does not implement another harness. The shared execution contracts remain in
`agent.harness_plan` and `agent.harness_run`. The standalone tier asks
separately about market trends, product/option/spec data
and technical knowledge. The combined tier first compares market and product
evidence, then asks for a market/product/technical/competitor strategy with
SWOT and project execution actions. Every factual output needs Raw citations;
missing competitor, customer or fit evidence is an explicit gap, not an
invented recommendation. The case data defines questions and acceptance
facets, not pre-approved answers or a claim that the current Vault covers them.

## G3 combination acceptance (owner clarification, 2026-10-04)

Treat market trends, product/option/specifications, technical knowledge and
competitor evidence as four independently retrievable information facets. The
evaluation matrix must exercise all 15 nonempty subsets, including the four
standalone, six pairs, four triples and one full combination. For each subset,
exercise supported evidence, missing evidence and a misleading cross-source
co-mention in a small controlled Vault. Live RS_Knowledge runs then record the
actual route, retrieved Raw references, requested/missing facets and answer
status; source presence in the Vault is not assumed.

The Knowledge Asking Skill owns the query procedure and facet search guidance.
The Knowledge adapter can assemble per-facet candidate evidence, but only Host
checks can accept cited output. A strategy, SWOT or product-market fit claim
requires direct connecting evidence, not merely one market passage and one
product passage. If a required facet or link is absent, the answer must name
that gap and refrain from an unsupported conclusion. The shared harness remains
domain-neutral and Bridge authorization remains exact. Normal natural-language
chat must find the sole installed Knowledge asset for Skill-declared Knowledge
intents without requiring the user to memorize the asset name.

## G3 causal analysis before implementation (2026-10-04)

Two live combined cases did not fail for the same reason. The market/product
CMP180 question without an explicit Vault name stopped before Knowledge
dispatch; the named form and the four-facet strategy case entered the shared
harness but stopped with `knowledge_insufficient_evidence` and zero accepted Raw
citations. Simpler CMX500 questions previously passed with Raw citations, so
the current evidence does not indicate a general Gateway outage.

| Boundary | Observed cause | Ownership |
| --- | --- | --- |
| Intent and asset selection | Agent Web recognizes an explicit installed Knowledge name or one fixed matrix intent. An ordinary combined question may fall through to conversational routing. | Host routing, guided by the installed Skill's declared intent; not Vault coverage. |
| Skill to plan | Candidate Skill 1.1.0 says to assess each claim and retrieve again, but its machine-readable guidance only requires `raw_citations` and allows zero retries. The Host task also caps retries at zero. Its `instructions` are displayed but do not become retrieval steps. | Skill contract plus Host plan wiring. Rewording the Markdown alone cannot fix it. |
| Retrieval and reasoning | The Knowledge capability asks the whole question once with `k=8`. Its second model attempt reuses the same passages; it is not re-retrieval for a missing facet. | Knowledge capability adapter and Skill-directed procedure, outside the shared harness state machine. |
| Validation | Host currently checks nonempty text and at least one Raw citation, while `facet_status` is always `not_assessed`. It cannot prove that every requested facet or a product-to-market/competitor link is supported. | Host acceptance checks plus Knowledge evidence observation. |
| Data coverage | The platform Vault has CMP180 specs/features and some market text; competitor battle cards exist for CMX500 and mention CMP180 production use. This establishes partial material, not a verified CMP180-specific comparative strategy or coverage of all 15 combinations. | Source coverage must be measured after retrieval is repaired; absent evidence remains an explicit gap. |

The shared harness runner is functioning as designed for the checks it receives.
The primary defect is incomplete process wiring around it: routing, Skill-driven
query planning, facet retrieval and independent acceptance. The Skill's current
structured guidance is also insufficient. Keep domain-specific retrieval and
evidence interpretation behind the Knowledge capability/Skill boundary; do
not add Knowledge rules to the common Workflow/Knowledge/Coding runner.

Implementation order: (1) cover ordinary Knowledge intents without requiring
the asset name, preserving deterministic commands and exact asset selection;
(2) version a machine-actionable Knowledge Asking Skill procedure and bounded
budget; (3) retrieve and report evidence by requested facet, retrying only
missing facets; (4) require Host checks for each requested facet and any
cross-source relationship claim; (5) run controlled 15-subset cases, then live
Vault cases and distinguish retrieval failure from genuine source gaps.

## G3 guided-evidence result (2026-10-04)

Steps 1–4 above are implemented in the private
`company-agent/knowledge-query@1.2.0` candidate. Command routing has
precedence over natural Skill intent. The Skill's `procedure` is opaque to the
shared plan and runner; the Knowledge adapter interprets it, and the Host
checks the cited result separately. Every requested facet must have cited Raw
support. A combination also needs a connected graph of direct Raw
relationships; separate co-mentions do not establish that connection. When
evidence is incomplete, Ask returns a structured gap instead of a strategy.

The controlled evaluation exercises all 15 nonempty facet combinations in
supported, missing and misleading co-mention cases. A read-only live
RS_Knowledge retrieval probe observed candidate Raw for every queried facet,
but a connected direct-link graph for only 5 of 15 questions. The other 10
are **retrieval observations**, not proof that the Vault lacks the facts. A
product-plus-technical model probe produced a cited candidate that passed the
lexical claim check; live answer quality remains for the owner to assess in
Agent Web. The claim check rejects obvious unsupported numbers and unrelated
cited prose but is not semantic entailment. Strong market-fit, competitor,
SWOT and execution advice therefore remains subject to source review.
