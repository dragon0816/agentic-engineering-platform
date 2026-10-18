# knowledge_v1 — u7-direct-2

Run at 2026-10-18T10:22:08+00:00, AEP commit `3a97c8a0fe43de63cd06edfe660c2db79bd01301`, grader 1.4, question bank sha256 `f5275373dad7…`, set `core`.

**33 of 36 acceptable** (PASS 30, INSUFFICIENT_KNOWLEDGE 3); FAIL 3, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 5 | 1 | 0 | 0 | 0 |
| Aerospace / Defense | 5 | 0 | 1 | 0 | 0 |
| Automotive | 4 | 1 | 1 | 0 | 0 |
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
| Signal Generator / Signal Analyzer | 5 | 1 | 0 | 0 | 0 |
| Signaling / Non-signaling Tester | 11 | 0 | 0 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 4 | 0 | 2 | 0 | 0 |
| Wireless Fundamentals | 0 | 0 | 1 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 4 | 1 | 0 | 0 | 0 |
| basic | 3 | 1 | 1 | 0 | 0 |
| competitive | 5 | 0 | 0 | 0 | 0 |
| cross_domain | 4 | 1 | 0 | 0 | 0 |
| foundation | 5 | 0 | 1 | 0 | 0 |
| solution_mapping | 4 | 0 | 1 | 0 | 0 |
| strategic | 5 | 0 | 0 | 0 | 0 |

## Harness

Routes: direct 36

Gaps: REASONING_GAP 3, SOURCE_GAP or RETRIEVAL_GAP 3

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0351 | FAIL | REASONING_GAP | reviewer: The cited passages strongly support several satellite-payload/component capabilities such as group delay, converter measurements without LO access, noise figure, component RF measurements, a |
| Q0461 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0571 | FAIL | REASONING_GAP | reviewer: The answer is generally cautious and fairly states that the cited passages do not directly prove a full Automotive requirement-to-VNA-capability chain, while mapping supported intermediate f |
| Q0701 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1021 | FAIL | REASONING_GAP | reviewer: Most OFDM definitions and the WLAN OFDM, cyclic-prefix, sample-rate, RE-counting, and total-power-dynamic-range points are backed by the passages. However, the cited evidence for the 5G NR t |
