# fix-run-014: 19 of 20

Build: Agent Web on `db38f28`, the same build as lab fix-010 and fix-run-013.

**T16 FAIL (Agent diligence).**
- What happened: the input logs are in `input/logs/`. The Agent's first probe listed only files directly in `input/`, printed `input files: []`, and went on. Its program wrote `unified.json` with 0 records and `warnings.json` with 0 warnings. Its own check then "verified" those empty outputs.
- History: T16 passed in fix-run-012 and fix-run-013.
- Pattern: the same kind of gap as fix-run-013 T13 and lab C02 (see the 2026-10-07 rule-following analysis). The Agent did not compare its outputs with what the inputs hold.

On this build, coding_v1 scored 19 of 20 twice, with a different failing task each time (T13, then T16). The run-to-run variance is in the Agent's diligence, not in a platform defect.
