# AEP six-layer harness status (2026-10-04)

This is an implementation inventory, not a claim that all six layers form one
continuous autonomous loop. It distinguishes the general Agent chat path from
the narrower Coding Harness and explicit Task path.

| Layer | Current status | Implemented evidence | Remaining gap |
| --- | --- | --- | --- |
| 1. Intent / Routing | Partial | Rule-first `CommandRouter`, installed-target `RequestRouter`, one approved Gateway route decision, optional typed Decision Service with `NONE` baseline. Named Knowledge and matrix intent route deterministically. | No reusable task/domain classifier or policy that chooses a Skill and its allowed scope across domains. JEV/Laya is not a production routing provider. |
| 2. Skill / Planning | Partial | Versioned Skill manifests carry procedures and exact commands. `TaskContract` describes objective, scope and outputs. Coding Harness has a bounded plan/change/validate/repair loop. | Ordinary Ask and Knowledge Ask do not run a Skill-owned plan with explicit success criteria, fallback and checkpointed subtasks. |
| 3. Retrieval / Context | Partial | Raw/Wiki retrieval with provenance and Raw citations; bounded conversation history is configurable (default 12 recent messages, at most 48,000 UTF-8 bytes). Knowledge Ask has a narrow Raw coverage and citation check. | No general evidence-sufficiency decision, query reformulation/re-retrieval policy, or task-level context manager that tracks what has been learned and what remains missing. The history budget is not the model's context window. |
| 4. Reasoning / Loop | Partial | Gateway chat supports at most five model turns and four installed-command calls, with tool observations and a bounded repair for unknown calls. Coding Harness separately has a validation/repair loop. | No general explicit `retrieve → assess sufficiency → retrieve again → reason` loop for Knowledge questions. A model's own reasoning is not an independent orchestrator state. |
| 5. Execution | Strong foundation | Bridge checks exact grants and validates input/output contracts; Workflow engine runs installed exact versions with durable run evidence; Coding Harness executes only declared paths and commands; explicit Gateway Tasks can use installed read-only capabilities. Knowledge query and the matrix are read capabilities. | The same broad agent planning/execution loop does not yet cover every tool, Workflow and backend. Native Codex/Claude task backends remain outside the first governed Gateway Task slice. |
| 6. Validation / Feedback | Partial | Bridge validates typed results; Knowledge requires Raw citations and has a narrow product-to-market assertion guard; explicit Tasks validate artifact bytes; Coding Harness runs declared checks and bounded repairs; Workflows expose failure states. | No general independent semantic entailment/acceptance gate for every natural-language answer, no reusable `insufficient evidence → re-retrieval` failure route, and no validated product/option strategy recommendation yet. |

The product/market cell assessment is a Knowledge pilot, not the common
harness. The owner clarified that the common six-layer process must serve
Workflow/Task execution, Knowledge Asking and Coding. A shared Skill-guided
plan envelope and bounded, payload-free run state now have negative tests in
all three domains. Live domain adapters and Host validator wiring remain to be
connected. Knowledge
is the first user-level validation case, driven by a candidate Knowledge
Asking Skill. The adapter maps Raw citations into common observations without
owning the procedure. See `docs/phases/HARNESS_6_LAYER_INCREMENTAL.md`.
