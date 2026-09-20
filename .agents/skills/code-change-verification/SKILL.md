---
name: code-change-verification
description: Verify implementation changes before completion, commit or handoff.
---

# Code Change Verification

1. Inspect changed files and scope.
2. Run focused tests for changed behavior.
3. Run the full pytest suite when shared contracts/runtime behavior changed.
4. Run configured lint.
5. Run configured type checking.
6. Re-run architecture-guard against the final diff.
7. Confirm no secrets, credentials or accidental production side effects were introduced.
8. Record exact verification commands and outcomes in HANDOFF when transferring ownership.
9. Never report a check as passing if it was not run.
