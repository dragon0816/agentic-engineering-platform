# knowledge_v1 — u7-chat-1

Run at 2026-10-18T08:58:53+00:00, AEP commit `3a97c8a0fe43de63cd06edfe660c2db79bd01301`, grader 1.4, question bank sha256 `f5275373dad7…`, set `core`.

**30 of 36 acceptable** (PASS 27, INSUFFICIENT_KNOWLEDGE 3); FAIL 6, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 4 | 1 | 1 | 0 | 0 |
| Aerospace / Defense | 5 | 0 | 1 | 0 | 0 |
| Automotive | 6 | 0 | 0 | 0 | 0 |
| Semiconductor | 4 | 2 | 0 | 0 | 0 |
| Wireless Communication | 6 | 0 | 0 | 0 | 0 |
| foundation | 2 | 0 | 4 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 0 | 1 | 0 | 0 |
| High-Speed / Signal Integrity | 0 | 0 | 1 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 4 | 2 | 1 | 0 | 0 |
| RF / Measurement Fundamentals | 1 | 0 | 0 | 0 | 0 |
| Signal Generator / Signal Analyzer | 6 | 0 | 0 | 0 | 0 |
| Signaling / Non-signaling Tester | 10 | 1 | 0 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 5 | 0 | 1 | 0 | 0 |
| Wireless Fundamentals | 0 | 0 | 1 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 5 | 0 | 0 | 0 | 0 |
| basic | 4 | 0 | 1 | 0 | 0 |
| competitive | 5 | 0 | 0 | 0 | 0 |
| cross_domain | 3 | 2 | 0 | 0 | 0 |
| foundation | 2 | 0 | 4 | 0 | 0 |
| solution_mapping | 3 | 1 | 1 | 0 | 0 |
| strategic | 5 | 0 | 0 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: REASONING_GAP 3, SOURCE_GAP or RETRIEVAL_GAP 3, VALIDATION_GAP 3

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0351 | FAIL | REASONING_GAP | reviewer: The passages support satellite-payload group delay/frequency-converter testing and document many ZNA/ZNB product features, but they do not establish a ranked or priority set of S-parameter c |
| Q0631 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0671 | FAIL | REASONING_GAP | reviewer: Most of the qualitative connectivity/PCB-to-SI-test-to-scope mapping is supported, and the answer appropriately notes missing numeric oscilloscope specifications. However, the power-demand r |
| Q0871 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_grounded) |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1021 | FAIL | REASONING_GAP | reviewer: Most OFDM-grid and product measurement points are supported by the cited passages, especially NR numerology/SCS, sample-rate formulas, CMP200/CMX500 settings, PRACH, SRS, and WLAN OFDM TX te |
| Q1041 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1061 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1091 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
