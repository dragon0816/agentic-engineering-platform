# knowledge_v1 — grader-1.4

Run at 2026-10-11T19:52:01+00:00, AEP commit `9d0d74c21a43016662ed9707b5f00be794d9b1d0`, grader 1.4, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**30 of 36 acceptable** (PASS 28, INSUFFICIENT_KNOWLEDGE 2); FAIL 6, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 5 | 1 | 0 | 0 | 0 |
| Aerospace / Defense | 6 | 0 | 0 | 0 | 0 |
| Automotive | 6 | 0 | 0 | 0 | 0 |
| Semiconductor | 5 | 1 | 0 | 0 | 0 |
| Wireless Communication | 5 | 0 | 1 | 0 | 0 |
| foundation | 1 | 0 | 5 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 0 | 1 | 0 | 0 |
| High-Speed / Signal Integrity | 0 | 0 | 1 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 5 | 1 | 1 | 0 | 0 |
| RF / Measurement Fundamentals | 1 | 0 | 0 | 0 | 0 |
| Signal Generator / Signal Analyzer | 5 | 1 | 0 | 0 | 0 |
| Signaling / Non-signaling Tester | 11 | 0 | 0 | 0 | 0 |
| Technical Document / Paper Understanding | 0 | 0 | 1 | 0 | 0 |
| Vector Network Analyzer | 6 | 0 | 0 | 0 | 0 |
| Wireless Fundamentals | 0 | 0 | 1 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 5 | 0 | 0 | 0 | 0 |
| basic | 3 | 1 | 1 | 0 | 0 |
| competitive | 5 | 0 | 0 | 0 | 0 |
| cross_domain | 4 | 1 | 0 | 0 | 0 |
| foundation | 1 | 0 | 5 | 0 | 0 |
| solution_mapping | 5 | 0 | 0 | 0 | 0 |
| strategic | 5 | 0 | 0 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: REASONING_GAP 3, VALIDATION_GAP 3, SOURCE_GAP or RETRIEVAL_GAP 2

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0051 | FAIL | REASONING_GAP | reviewer: Most individual statements are directly supported as general wireless-certification or general SI/PI/PCB capabilities, but the cited passages do not clearly establish that the SerDes/PCB/PDN |
| Q0701 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1021 | FAIL | REASONING_GAP | reviewer: The passages support the NR grid facts, CP, sample-rate formula, and several measurement/specification facts, but they do not establish that many listed product choices—especially CMX500 opt |
| Q1041 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1061 | FAIL | VALIDATION_GAP | 1 of 11 citations not found in the Vault |
| Q1071 | FAIL | REASONING_GAP | reviewer: The cited passages support the factual descriptions of substitution, EIRP/TRP workflow, TRP procedures/grids, ELEKTRA features, and ZNL constraints, but they do not generally establish that  |
| Q1091 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
