---
name: architecture-guard
description: Check a proposed code or design change against repository architecture before implementation.
---

# Architecture Guard

Read `ARCHITECTURE.md`, the active phase specification and relevant contracts before changing code.

Verify:
- Team Platform Plane remains control plane; Personal Engineering / Execution Plane remains the normal local execution plane.
- Personal Agent owns reasoning/planning/capability selection; Bridge owns deterministic execution/resource access.
- deterministic routes are not replaced by LLM-first routing;
- Registry/distribution is separate from execution authorization;
- publish does not imply execution permission;
- normal contributions do not require core-runtime modification;
- model/provider details do not leak into platform contracts;
- n8n is not introduced as a mandatory runtime dependency;
- new side effects have policy/approval classification;
- new capabilities have tests/evaluation coverage.

If a requested implementation conflicts with an invariant, stop implementation and document the conflict rather than silently redesigning the architecture.
