# BI schema v8 (fixture)

`bi_schema.py` from the owner's manager's AIDC and wireless-module knowledge bases (schema v8, 21 card
types; identical in both, 2026-10-29). `scripts/build_bi_schema_v2.py` reads it with `ast`, never imports
or runs it, and writes the shipped `bi.schema/v1.1@2.0.0` (`docs/phases/BI_VAULT.md` §12, V9). Only the
schema file is kept here; the knowledge bases' cards and sources are not in the repository.
