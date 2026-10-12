# knowledge_v1 — grader-1.4

Run at 2026-10-11T20:42:29+00:00, AEP commit `43dcd768407a2d886f206247265fe4047797a8eb`, grader 1.4, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**31 of 36 acceptable** (PASS 29, INSUFFICIENT_KNOWLEDGE 2); FAIL 5, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 6 | 0 | 0 | 0 | 0 |
| Aerospace / Defense | 4 | 1 | 1 | 0 | 0 |
| Automotive | 5 | 0 | 1 | 0 | 0 |
| Semiconductor | 5 | 1 | 0 | 0 | 0 |
| Wireless Communication | 6 | 0 | 0 | 0 | 0 |
| foundation | 3 | 0 | 3 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 0 | 1 | 0 | 0 |
| High-Speed / Signal Integrity | 0 | 0 | 1 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 5 | 1 | 1 | 0 | 0 |
| RF / Measurement Fundamentals | 1 | 0 | 0 | 0 | 0 |
| Signal Generator / Signal Analyzer | 6 | 0 | 0 | 0 | 0 |
| Signaling / Non-signaling Tester | 10 | 1 | 0 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 5 | 0 | 1 | 0 | 0 |
| Wireless Fundamentals | 1 | 0 | 0 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 5 | 0 | 0 | 0 | 0 |
| basic | 4 | 0 | 1 | 0 | 0 |
| competitive | 4 | 0 | 1 | 0 | 0 |
| cross_domain | 4 | 1 | 0 | 0 | 0 |
| foundation | 3 | 0 | 3 | 0 | 0 |
| solution_mapping | 4 | 1 | 0 | 0 | 0 |
| strategic | 5 | 0 | 0 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: REASONING_GAP 3, SOURCE_GAP or RETRIEVAL_GAP 2, VALIDATION_GAP 2

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0221 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_grounded) |
| Q0351 | FAIL | REASONING_GAP | reviewer: The answer is honest that the passages do not provide a ranked Aerospace/Defense S-parameter list, and many satellite payload/component test items are supported. However, several listed item |
| Q0489 | FAIL | REASONING_GAP | reviewer: Most recommendations are fair process guidance supported by passages about formal specs, competitor evidence, battle-card limits, automotive validation gaps, and TCO evidence. However, the c |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1041 | FAIL | REASONING_GAP | reviewer: The cited passages support the listed occurrences of eye diagram in PCIe eye-opening requirements, SI/PCB workflows, stackup selection, and ZNA/ZNA67EXT option configuration. However, the an |
| Q1061 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1091 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
