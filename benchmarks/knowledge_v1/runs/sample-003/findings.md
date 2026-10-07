# sample-003: findings

**Setup.** Agent Web was restarted at 18:52 on `db38f28`. `metadata.json` records repository commit `041c746`, a docs-only commit, so the code is the same. The build includes every 2026-10-07 Knowledge change:
- facet credit from cited passages;
- supported answers kept, with the gap named;
- the tool route binding the harness Skill procedure;
- Knowledge Skill 1.5.0 (market hints);
- rs-knowledge 1.0.2, the 4000-token synthesis limit and the "say when Knowledge gave no answer" rule.

Grader 1.1. The comparison is in `runs/compare-sample-002-003.md` (`compare.py`).

## Result

**68 of 110 acceptable:** PASS 35, INSUFFICIENT 33, FAIL 40, SYSTEM_ERROR 2. sample-002 had 75 acceptable and 34 PASS.

| Route | sample-002 PASS | sample-003 PASS |
|---|---|---|
| direct (Skill harness) | 19 of 34 (56%) | **25 of 34 (74%)** |
| tool (conversation model calls Knowledge) | 15 of 76 (20%) | **10 of 74 (14%)** |

1. **The direct route improved clearly.** Many former `needs_input` gap replies are now PASS answers that name what is missing (for example Q0071, Q0121, Q0171, Q0321, Q0371). INSUFFICIENT on this route fell from 13 to 3. This is what `72af226`'s facet credit and kept answers were for.
2. **The tool route did not improve.** Binding the Skill procedure gave it wiki-first retrieval and an 8192-token limit, but the conversation model still writes its own answer around the evidence:
   - over-reaching claims per answer rose (compare report);
   - tool-route latency roughly doubled (median about 127 s);
   - two questions hit the 600 s timeout (SYSTEM_ERROR).

   The tool route is still about two thirds of the traffic.
3. **Run-to-run variance on the tool route is about as large as the effects.** From 002 to 003, as many tool-route questions improved as regressed.
4. AI is the weakest market in all three runs. Every checked citation was found in the Vault in all three runs, so failures are reasoning and over-reach, not invented sources.

## Proposal for the owner

The direct route's answers are validated by the harness. On the tool route, the model's own rewrite is what fails review. Options:
- **(a)** When the model calls the Knowledge tool, return the harness's validated answer to the person as it is, and let the model only add a short framing marked as its own.
- **(b)** Route more Knowledge questions to the direct harness. The Skill's intent patterns now match only some of them.
- **(c)** Leave the tool route unchanged and accept its PASS rate.

These are harness changes and need the owner's decision.
