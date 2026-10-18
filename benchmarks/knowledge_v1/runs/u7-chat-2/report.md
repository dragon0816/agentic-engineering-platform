# knowledge_v1 — u7-chat-2

Run at 2026-10-18T09:55:15+00:00, AEP commit `3a97c8a0fe43de63cd06edfe660c2db79bd01301`, grader 1.4, question bank sha256 `f5275373dad7…`, set `core`.

**30 of 36 acceptable** (PASS 29, INSUFFICIENT_KNOWLEDGE 1); FAIL 6, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 6 | 0 | 0 | 0 | 0 |
| Aerospace / Defense | 5 | 0 | 1 | 0 | 0 |
| Automotive | 4 | 0 | 2 | 0 | 0 |
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
| Signaling / Non-signaling Tester | 11 | 0 | 0 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 4 | 0 | 2 | 0 | 0 |
| Wireless Fundamentals | 1 | 0 | 0 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 5 | 0 | 0 | 0 | 0 |
| basic | 4 | 0 | 1 | 0 | 0 |
| competitive | 4 | 0 | 1 | 0 | 0 |
| cross_domain | 4 | 1 | 0 | 0 | 0 |
| foundation | 3 | 0 | 3 | 0 | 0 |
| solution_mapping | 4 | 0 | 1 | 0 | 0 |
| strategic | 5 | 0 | 0 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: REASONING_GAP 3, VALIDATION_GAP 3, SOURCE_GAP or RETRIEVAL_GAP 1

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0351 | FAIL | REASONING_GAP | reviewer: The passages support many individual product features and some satellite-specific needs such as group delay and TVAC calibration, but they do not establish a 'most important' or 'priority' s |
| Q0489 | FAIL | REASONING_GAP | reviewer: The answer's caution that current passages do not support an Automotive oscilloscope competitor comparison is fair, and the requirements for formal specs, competitor verification, and avoidi |
| Q0571 | FAIL | REASONING_GAP | reviewer: The overall market-to-measurement mapping is mostly supported by passages [25], [28], and [31], and several ZNA capability facts are supported by [42] and [44]. However, the answer makes key |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1041 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1061 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1091 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
