# knowledge_v1 — core-010

Run at 2026-10-11T19:52:01+00:00, AEP commit `9d0d74c21a43016662ed9707b5f00be794d9b1d0`, grader 1.3, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**28 of 36 acceptable** (PASS 26, INSUFFICIENT_KNOWLEDGE 2); FAIL 8, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 4 | 1 | 1 | 0 | 0 |
| Aerospace / Defense | 6 | 0 | 0 | 0 | 0 |
| Automotive | 5 | 0 | 1 | 0 | 0 |
| Semiconductor | 5 | 1 | 0 | 0 | 0 |
| Wireless Communication | 5 | 0 | 1 | 0 | 0 |
| foundation | 1 | 0 | 5 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 0 | 1 | 0 | 0 |
| High-Speed / Signal Integrity | 0 | 0 | 1 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 6 | 1 | 0 | 0 | 0 |
| RF / Measurement Fundamentals | 0 | 0 | 1 | 0 | 0 |
| Signal Generator / Signal Analyzer | 4 | 1 | 1 | 0 | 0 |
| Signaling / Non-signaling Tester | 9 | 0 | 2 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 6 | 0 | 0 | 0 | 0 |
| Wireless Fundamentals | 0 | 0 | 1 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 5 | 0 | 0 | 0 | 0 |
| basic | 4 | 1 | 0 | 0 | 0 |
| competitive | 3 | 0 | 2 | 0 | 0 |
| cross_domain | 4 | 1 | 0 | 0 | 0 |
| foundation | 1 | 0 | 5 | 0 | 0 |
| solution_mapping | 5 | 0 | 0 | 0 | 0 |
| strategic | 4 | 0 | 1 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: REASONING_GAP 5, VALIDATION_GAP 3, SOURCE_GAP or RETRIEVAL_GAP 2

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0039 | FAIL | REASONING_GAP | reviewer: Most of the answer is backed by the supplied passages: R&S claims should trace to formal specs/features, product-data limits matter, and competitor claims from battle cards need official or  |
| Q0546 | FAIL | REASONING_GAP | reviewer: The core opportunities—CMX500/CMX-KA098 for NG eCall, AREG800A as an automotive radar echo-generation anchor with caveat that it is not SG/SA, and SMW200A+FSW for NTN where automotive intere |
| Q0639 | FAIL | REASONING_GAP | reviewer: The R&S CMX500/CMP180 documentation and the warning against using sales battle-card language are mostly supported by the displayed passages. However, several central AI-specific and competit |
| Q0701 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1001 | FAIL | REASONING_GAP | reviewer: Most of the definition and product/test-decision rows are directly supported by the provided passages. However, the O-RAN beamforming row and the final warning rely on cited passages that we |
| Q1021 | FAIL | REASONING_GAP | reviewer: The basic OFDM/resource-grid, CP, sample-rate, CORESET/REG/CCE, and PSBCH counting facts are supported by the passages. However, the answer repeatedly turns product option/specification fact |
| Q1041 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1061 | FAIL | VALIDATION_GAP | 1 of 11 citations not found in the Vault |
| Q1091 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
