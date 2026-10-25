# AGENTS.md

Instructions for coding agents and human contributors working in this repository.

## Mission

Build a multi-user, contribution-driven agentic engineering platform without sacrificing deterministic reliability. Preserve proven behaviour from source repositories before refactoring it. Team members must be able to develop, validate, publish, discover, reuse and evolve Tasks, Workflows, Skills, Knowledge and Agent profiles without requiring changes to the core runtime.

## Architectural rules

1. **Agent decides WHAT / WHY / WHICH.** Do not embed deterministic execution details in prompts when code/workflows can own them.
2. **Workflow defines HOW EXACTLY.** Repeatable engineering operations belong in deterministic workflows/jobs.
3. **AEP does not integrate n8n** (owner, 2026-10-17). The Agent never calls or is called by n8n workflows; schedules, triggers and notifications are AEP's own (host schedule store, Telegram, Agent Web). Old n8n workflows are only a specification source for migration. Agent and CLI call the same underlying Workflow/Capability contracts.
4. **Skills are procedures and domain guidance.** They are not synonymous with Python functions.
5. **Tools are atomic executable capabilities.** Give them explicit input/output contracts and side-effect classification.
6. **MCP exposes capabilities.** It is an integration boundary, not a replacement for agent or workflow runtime.
7. **Knowledge owns grounded enterprise context.** Raw sources are immutable and provenance must survive transformation.
8. **Prefer deterministic routing.** Known commands and workflows must bypass LLM intent selection where possible.
9. **Bound agent loops.** On missing information, policy boundary or repeated failure, return a structured needs-input/failure state.
10. **Every new agent capability needs evaluation cases.** Every migrated deterministic behaviour needs regression tests.
11. **Contributions are first-class platform assets.** Tasks, Workflows, Skills, Knowledge and Agent profiles need stable manifests/contracts so they can evolve without core-runtime changes.
12. **Registry is control plane, Bridge is execution plane.** Publishing/discovery/versioning are centralized concerns; local Bridges/workers execute capabilities near required resources.
13. **Publishing does not grant execution permission.** Distribution, authorization and approval are separate concerns.
14. **Shared assets are governed.** Require scoped identity/namespace, owner, version, visibility, lifecycle, dependencies, compatibility and permission metadata appropriate to the asset type.
15. **Business approval and technical policy are distinct.** Department/domain owners validate business correctness; technical policy validates capability risk, data access, cross-scope use and side effects. Automate low-risk checks where practical.
16. **Local-first behavior is contractual.** Tasks/Workflows declare local capability and central-service dependencies; do not guess connectivity requirements at runtime.
17. **Secrets are references, never asset content.** Shared assets may declare `SecretRef` requirements, but resolution and authorization belong to the execution environment.
18. **Never ask for what the person already gave.** When a Workflow, form or flow collects inputs (Agent Web, Telegram or any channel), values stated in the request, in a replied-to message or in the model's run arguments are prefilled and validated, never asked again. Optional inputs take their defaults without a question. Only required, missing values are asked, one at a time and waiting for each answer. Before running, one confirmation lists every value with its origin (from the message, default, answered) and lets the person confirm or change any value in plain words. Nothing is consumed as an answer without the person's input. A yes/no input is presented by what each choice does (「只看計畫（不寫入、不寄信）」 / 「正式執行（寫入週報、起草郵件）」), on its buttons, options and confirmation lines alike; there are no bare Yes/No buttons. (Owner, 2026-10-25.)
19. **Never interrupt a person mid-interaction.** Restarts, updates and redeploys first check active work: running tasks, in-progress turns and open question flows or forms on every channel; they wait or ask while any exists. State a person is in the middle of is either persisted or the restart is refused. (Owner, 2026-10-25.)
20. **Remember what you produced in the session.** Within a session (an Agent Web conversation, a Telegram chat), the agent keeps what it produced — Workflow runs (name, run id, status, one-line summary), files and drafts — by short id, kind and file name, beyond any history window, and can show or attach them again on request. It never asks the person for a path or file it made. Pictures a run makes are shown at the end of the run. Attaching is limited to what was recorded for that session and that person; no arbitrary paths. (Owner, 2026-10-25.)

## Migration rules

- The source repositories are reference implementations. Do not modify them as part of this repository's migration.
- Before migrating a component, document its current contract/invariants and add tests for behaviour that must survive.
- Prefer adapters around proven components before rewriting them.
- Never copy two overlapping implementations merely because they exist in two source repositories; identify lineage and choose one source of truth.
- Each migration PR should be narrow, reversible and independently testable.
- Do not start a broad refactor in the same PR that first establishes behavioural coverage.

## Safety / side effects

Classify capabilities as `read`, `write`, `execute`, or `external_side_effect`. Destructive, release, deployment, message-sending, production, credential and external-system write operations require an explicit approval policy. Do not let an LLM silently bypass tests, approval gates, version rules or protected release semantics.

Secrets must come from environment variables, secret stores or runtime configuration. Never commit live tokens, passwords, bot tokens, JWTs or API keys. Logs/traces must redact them.

## Knowledge rules

Target pipeline:

```text
Drop -> Document Processor -> Raw Markdown -> Curation -> Wiki -> Retrieval
```

Drop contains originals. Raw preserves extracted text/tables/images plus source file and page/slide relationships. Wiki is curated knowledge. Do not allow the curation layer to become the only copy of source evidence. Conflicts and human decisions must be persisted so later ingestion does not reintroduce rejected claims.

## Definition of done for a migrated capability

A migration is not complete because code was copied. It is complete when the contract is explicit, tests/evaluation pass, observability exists, failure behaviour is defined, required approvals are enforced, and the source implementation can be deprecated without losing a verified capability.


## Coding-agent-neutral development workflow

Codex, Claude Code and human contributors are replaceable workers. GitHub and committed repository artifacts are the persistent project state; never rely on one coding agent's conversation history.

Required implementation sequence:

```text
Architecture -> Requirements -> Contracts -> Tests -> Implementation
             -> Verification -> Commit -> Handoff
```

Before modifying implementation code, read `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/TASKS.md`, the active phase specification and `HANDOFF.md`.

`docs/TASKS.md` is the progress record and accumulates; `HANDOFF.md` is rewritten each time and carries only where the current work stopped.

Finished work that passed verification is committed directly to `main`; a pull request is not required (owner decision 2026-10-19, `docs/DECISIONS.md`).

Open decisions and tasks are tracked in GitHub Issues (owner decision 2026-10-19). Who closes an issue:
- `decision-needed`, `meeting`: the owner or the decision maker the owner named. The decision is
  recorded in `docs/DECISIONS.md` first and the issue gets a comment linking it. An agent may close one
  only after the owner stated the decision, and says so in the closing comment ("closed on the owner's
  decision of <date>"); the owner may reopen it.
- `verification`: the person who verified it, with the result in a comment. A problem found becomes a
  new bug issue; the verification issue is not closed as passed.
- implementation work: closed by the commit that completes it (`Closes #N` in the commit message,
  pushed to `main` after verification). If CI then fails, reopen the issue and fix it.
- `coordination`, `on-hold`: the owner, with the reason in a comment.
Every closing leaves evidence: a commit, a `docs/DECISIONS.md` entry or a verification result.
Contributors may close the implementation and verification issues they own; decision issues are
closed only by the owner or the named decision maker. Owner-only security items are never filed as
issues.

Use repository procedures under `.agents/skills/`:
- `architecture-guard` before implementation or architectural changes;
- `implementation-planning` to convert requirements into small implementation slices;
- `contract-development` for shared platform contracts;
- `code-change-verification` before completion/commit/handoff;
- `migration` when adapting source-repository behavior;
- `handoff` whenever ownership may transfer between Codex, Claude Code or a human.

`CLAUDE.md` is the Claude Code entry point and must remain aligned with these shared rules. Do not create a separate architecture or workflow specifically for one coding agent.
