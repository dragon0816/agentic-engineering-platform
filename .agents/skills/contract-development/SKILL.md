---
name: contract-development
description: Design and implement stable typed contracts for platform assets and boundaries.
---

# Contract Development

For Task, Workflow, Skill, Agent, Registry, Bridge, Knowledge and Model boundaries:

1. Start from architecture semantics, not a provider/library object.
2. Define explicit typed inputs, outputs, identity and failure states.
3. Keep contracts serializable where cross-process or registry use is expected.
4. Separate metadata/discovery from runtime execution.
5. Include version/lifecycle/provenance/permission fields where the asset requires them.
6. Avoid embedding concrete LLM SDK, database or transport types.
7. Add contract validation and unit tests before depending on the contract broadly.
8. Prefer backward-compatible evolution; document intentional breaking changes.
