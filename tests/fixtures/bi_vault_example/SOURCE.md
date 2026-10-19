# BI Vault example (test fixture)

Owner-provided on 2026-10-19 (the "BI_Vault_Starter" example, v6) and approved by the owner
to be committed as test data: "files/BI_Vault_Example 可以commit 進repo當測試資料".

- **What it is:** an Obsidian BI example: 11 card types, 103 entity cards under `BI/<Type>/`,
  11 templates, `BI/Dashboard.md`, and the reference tools under `tools/` (`bi_schema.py`,
  `bi_ingest.py`, `bi_slides_extract.py`, `bi_concept_candidates.py`, prompts and samples).
- **Trust:** the README says the content is fictional or unverified. Treat every card as test
  data, never as trusted business knowledge, including the two CustomerProduct cards marked
  `confidence: verified` (see `docs/proposals/` v1.3, data-quality issues). Do not index it
  into a real Knowledge vault.
- **Not copied:** `.obsidian/plugins/` (third-party Dataview and Templater code, not ours to
  redistribute and not needed by tests), `.obsidian/workspace.json` and `graph.json` /
  `appearance.json` (personal editor state), `tools/__pycache__/`.
- **Do not run** the tools here against real data from tests; tests read the files or run the
  tools only on temporary copies.
- The owner's working copy stays in the untracked `files/BI_Vault_Example/`; this folder is
  the committed snapshot.
