# knowledge_v1 — core-014

Run at 2026-10-12T03:29:46+00:00, AEP commit `be6ee03fdc5c2bee387b364d4bed2ca677f01d08`, grader 1.4, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**32 of 36 acceptable** (PASS 30, INSUFFICIENT_KNOWLEDGE 2); FAIL 4, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 5 | 0 | 1 | 0 | 0 |
| Aerospace / Defense | 5 | 1 | 0 | 0 | 0 |
| Automotive | 5 | 0 | 1 | 0 | 0 |
| Semiconductor | 5 | 1 | 0 | 0 | 0 |
| Wireless Communication | 6 | 0 | 0 | 0 | 0 |
| foundation | 4 | 0 | 2 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 1 | 0 | 0 | 0 | 0 |
| High-Speed / Signal Integrity | 0 | 0 | 1 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 5 | 1 | 1 | 0 | 0 |
| RF / Measurement Fundamentals | 1 | 0 | 0 | 0 | 0 |
| Signal Generator / Signal Analyzer | 5 | 0 | 1 | 0 | 0 |
| Signaling / Non-signaling Tester | 10 | 1 | 0 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 6 | 0 | 0 | 0 | 0 |
| Wireless Fundamentals | 1 | 0 | 0 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 5 | 0 | 0 | 0 | 0 |
| basic | 4 | 0 | 1 | 0 | 0 |
| competitive | 4 | 0 | 1 | 0 | 0 |
| cross_domain | 4 | 1 | 0 | 0 | 0 |
| foundation | 4 | 0 | 2 | 0 | 0 |
| solution_mapping | 4 | 1 | 0 | 0 | 0 |
| strategic | 5 | 0 | 0 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: SOURCE_GAP or RETRIEVAL_GAP 2, REASONING_GAP 2, VALIDATION_GAP 2

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0221 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_grounded) |
| Q0489 | FAIL | REASONING_GAP | reviewer: The answer’s overall caution that the supplied passages are insufficient for an Automotive oscilloscope competitor comparison is reasonable and mostly backed by the cited gaps. However, some |
| Q0701 | FAIL | REASONING_GAP | reviewer: The cited passages support the listed instruments' signal-generation capabilities and separately mention AI/data-center high-speed connectivity and jitter/phase-noise testing, but they do no |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1041 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1061 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
