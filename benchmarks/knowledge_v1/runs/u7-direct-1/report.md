# knowledge_v1 — u7-direct-1

Run at 2026-10-18T09:30:07+00:00, AEP commit `3a97c8a0fe43de63cd06edfe660c2db79bd01301`, grader 1.4, question bank sha256 `f5275373dad7…`, set `core`.

**34 of 36 acceptable** (PASS 33, INSUFFICIENT_KNOWLEDGE 1); FAIL 2, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 4 | 1 | 1 | 0 | 0 |
| Aerospace / Defense | 6 | 0 | 0 | 0 | 0 |
| Automotive | 6 | 0 | 0 | 0 | 0 |
| Semiconductor | 6 | 0 | 0 | 0 | 0 |
| Wireless Communication | 6 | 0 | 0 | 0 | 0 |
| foundation | 5 | 0 | 1 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 1 | 0 | 0 | 0 | 0 |
| High-Speed / Signal Integrity | 1 | 0 | 0 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 6 | 0 | 1 | 0 | 0 |
| RF / Measurement Fundamentals | 1 | 0 | 0 | 0 | 0 |
| Signal Generator / Signal Analyzer | 5 | 1 | 0 | 0 | 0 |
| Signaling / Non-signaling Tester | 11 | 0 | 0 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 6 | 0 | 0 | 0 | 0 |
| Wireless Fundamentals | 1 | 0 | 0 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 5 | 0 | 0 | 0 | 0 |
| basic | 4 | 1 | 0 | 0 | 0 |
| competitive | 5 | 0 | 0 | 0 | 0 |
| cross_domain | 5 | 0 | 0 | 0 | 0 |
| foundation | 5 | 0 | 1 | 0 | 0 |
| solution_mapping | 4 | 0 | 1 | 0 | 0 |
| strategic | 5 | 0 | 0 | 0 | 0 |

## Harness

Routes: direct 36

Gaps: REASONING_GAP 1, SOURCE_GAP or RETRIEVAL_GAP 1, VALIDATION_GAP 1

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0671 | FAIL | REASONING_GAP | reviewer: Most of the PCB/SI and PDN/power-rail mappings are backed by the passages, including high-speed PCB drivers, IL/Xtalk/Eye/TDR items, Interface Test mapped to scopes, and MXO mapped to power  |
| Q0701 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1061 | FAIL | VALIDATION_GAP | 1 of 13 citations not found in the Vault |
