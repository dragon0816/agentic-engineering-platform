# knowledge_v1 — grader-1.4

Run at 2026-10-11T18:36:29+00:00, AEP commit `0be2b141a55f528528d4d7515831bdff71a4e564`, grader 1.4, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**29 of 36 acceptable** (PASS 23, INSUFFICIENT_KNOWLEDGE 6); FAIL 6, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 1

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 4 | 0 | 2 | 0 | 0 |
| Aerospace / Defense | 4 | 2 | 0 | 0 | 0 |
| Automotive | 4 | 1 | 1 | 0 | 0 |
| Semiconductor | 3 | 2 | 0 | 0 | 1 |
| Wireless Communication | 6 | 0 | 0 | 0 | 0 |
| foundation | 2 | 1 | 3 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 1 | 0 | 0 | 0 |
| High-Speed / Signal Integrity | 0 | 0 | 1 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 4 | 2 | 0 | 0 | 1 |
| RF / Measurement Fundamentals | 0 | 0 | 1 | 0 | 0 |
| Signal Generator / Signal Analyzer | 6 | 0 | 0 | 0 | 0 |
| Signaling / Non-signaling Tester | 8 | 1 | 2 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 3 | 2 | 1 | 0 | 0 |
| Wireless Fundamentals | 1 | 0 | 0 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 5 | 0 | 0 | 0 | 0 |
| basic | 4 | 1 | 0 | 0 | 0 |
| competitive | 5 | 0 | 0 | 0 | 0 |
| cross_domain | 2 | 2 | 1 | 0 | 0 |
| foundation | 2 | 1 | 3 | 0 | 0 |
| solution_mapping | 3 | 0 | 1 | 0 | 1 |
| strategic | 2 | 2 | 1 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: SOURCE_GAP or RETRIEVAL_GAP 6, VALIDATION_GAP 5, REASONING_GAP 1, EXECUTION_GAP 1

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0296 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0351 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0571 | FAIL | REASONING_GAP | reviewer: Most of the automotive-to-parameter mapping is supported by [38], and ZNA frequency range/TDR options are supported by [8] and [10]. However, the cited passages do not show that R&S ZNA has  |
| Q0581 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0631 | FAIL | VALIDATION_GAP | 1 of 18 citations not found in the Vault |
| Q0646 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0846 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0871 | SYSTEM_ERROR | EXECUTION_GAP | Knowledge did not complete (knowledge_model_failed) |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1001 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1041 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1061 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1091 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
