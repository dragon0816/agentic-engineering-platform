---
name: migration
description: Migrate proven behavior from source repositories without losing invariants or performing a big-bang merge.
---

# Migration

1. Treat source repositories as reference implementations; do not modify them from this migration.
2. Document current behavior, contract and invariants.
3. Add characterization/regression coverage for behavior that must survive.
4. Identify overlapping implementations and choose one lineage/source of truth.
5. Prefer an adapter around proven behavior before a rewrite.
6. Migrate one capability slice at a time.
7. Preserve deterministic execution paths and approval semantics.
8. Verify parity before deprecating a source implementation.
9. Keep rollback possible until acceptance criteria pass.
