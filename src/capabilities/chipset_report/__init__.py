"""Workflow 10: the sales opportunity list projected into the chipset sheet.

The transformation is the source's, ported pure (`docs/PHASE_7_MIGRATION.md`,
"Workflow 10"). Its acceptance specification is the source's own
`docs/W1_MAPPING.md`, which declares itself authoritative over the code; the
rules module here implements that document and the source's own tests are the
oracle.

No chipset, vendor or brand knowledge is written in code. All of it is data,
typed as `ChipsetRuleset`, so a misspelt key is a refusal at load rather than
a rule that quietly stopped applying.
"""
