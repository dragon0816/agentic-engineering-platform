---
name: handoff
description: Leave a reproducible repository state so another coding agent or human can continue without conversation history.
---

# Handoff

Before transferring ownership:

1. Inspect `git status`, diff and recent commits.
2. Separate completed work from incomplete work.
3. Run the applicable code-change-verification procedure.
4. Commit coherent completed work; do not hide unfinished behavior behind a success claim.
5. Update `HANDOFF.md` with:
   - current phase and branch;
   - goal;
   - completed work;
   - in-progress work;
   - remaining work;
   - architecture decisions/invariants relevant to the task;
   - exact verification results;
   - known issues;
   - one concrete next recommended action.
6. Do not rely on chat history or uncommitted reasoning as project state.

When taking over, reconcile HANDOFF with actual git state and tests before continuing.
