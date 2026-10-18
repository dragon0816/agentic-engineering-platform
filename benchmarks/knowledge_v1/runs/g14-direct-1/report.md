# knowledge_v1 — g14-direct-1

Run at 2026-10-18T13:59:24+00:00, AEP commit `b1264d8324fe6792a0e2b2cca3c9bc53e1f85828`, grader 1.4, question bank sha256 `f5275373dad7…`, set `core`.

**34 of 36 acceptable** (PASS 31, INSUFFICIENT_KNOWLEDGE 3); FAIL 1, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 1

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 5 | 0 | 0 | 0 | 1 |
| Aerospace / Defense | 5 | 1 | 0 | 0 | 0 |
| Automotive | 5 | 1 | 0 | 0 | 0 |
| Semiconductor | 5 | 1 | 0 | 0 | 0 |
| Wireless Communication | 6 | 0 | 0 | 0 | 0 |
| foundation | 5 | 0 | 1 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 1 | 0 | 0 | 0 | 0 |
| High-Speed / Signal Integrity | 1 | 0 | 0 | 0 | 0 |
| Instrument & Measurement Principles | 1 | 0 | 0 | 0 | 0 |
| Oscilloscope | 5 | 2 | 0 | 0 | 0 |
| RF / Measurement Fundamentals | 1 | 0 | 0 | 0 | 0 |
| Signal Generator / Signal Analyzer | 6 | 0 | 0 | 0 | 0 |
| Signaling / Non-signaling Tester | 9 | 1 | 0 | 0 | 1 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 6 | 0 | 0 | 0 | 0 |
| Wireless Fundamentals | 0 | 0 | 1 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 4 | 1 | 0 | 0 | 0 |
| basic | 5 | 0 | 0 | 0 | 0 |
| competitive | 5 | 0 | 0 | 0 | 0 |
| cross_domain | 4 | 1 | 0 | 0 | 0 |
| foundation | 5 | 0 | 1 | 0 | 0 |
| solution_mapping | 4 | 1 | 0 | 0 | 0 |
| strategic | 4 | 0 | 0 | 0 | 1 |

## Harness

Routes: direct 36

Gaps: SOURCE_GAP or RETRIEVAL_GAP 3, EXECUTION_GAP 1, REASONING_GAP 1

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0221 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_grounded) |
| Q0461 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0646 | SYSTEM_ERROR | EXECUTION_GAP | Knowledge did not complete (knowledge_model_failed) |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1021 | FAIL | REASONING_GAP | reviewer: The OFDM explanation is mostly supported, and the WLAN OFDM analyzer decision is directly supported. But the answer overstates that several NR product option, bandwidth, mode, and receiver s |
