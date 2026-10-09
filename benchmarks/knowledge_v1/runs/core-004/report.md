# knowledge_v1 — core-004

Run at 2026-10-09T20:55:55+00:00, AEP commit `13354e4d3fecf05069a287b970629166572e677b`, grader 1.3, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**31 of 36 acceptable** (PASS 23, INSUFFICIENT_KNOWLEDGE 8); FAIL 5, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 3 | 1 | 2 | 0 | 0 |
| Aerospace / Defense | 4 | 2 | 0 | 0 | 0 |
| Automotive | 3 | 2 | 1 | 0 | 0 |
| Semiconductor | 4 | 2 | 0 | 0 | 0 |
| Wireless Communication | 5 | 0 | 1 | 0 | 0 |
| foundation | 4 | 1 | 1 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 1 | 0 | 0 | 0 |
| High-Speed / Signal Integrity | 1 | 0 | 0 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 3 | 3 | 1 | 0 | 0 |
| RF / Measurement Fundamentals | 1 | 0 | 0 | 0 | 0 |
| Signal Generator / Signal Analyzer | 5 | 0 | 1 | 0 | 0 |
| Signaling / Non-signaling Tester | 7 | 3 | 1 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 4 | 1 | 1 | 0 | 0 |
| Wireless Fundamentals | 1 | 0 | 0 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 4 | 1 | 0 | 0 | 0 |
| basic | 2 | 2 | 1 | 0 | 0 |
| competitive | 4 | 0 | 1 | 0 | 0 |
| cross_domain | 2 | 3 | 0 | 0 | 0 |
| foundation | 4 | 1 | 1 | 0 | 0 |
| solution_mapping | 4 | 1 | 0 | 0 | 0 |
| strategic | 3 | 0 | 2 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: SOURCE_GAP or RETRIEVAL_GAP 8, REASONING_GAP 3, VALIDATION_GAP 2

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0196 | FAIL | REASONING_GAP | reviewer: The first two opportunity areas are supported by the network-infrastructure mapping and VNA product labels, and the regulatory-lab caveat is fairly grounded. However, the cited passages for  |
| Q0231 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0351 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0401 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0461 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0489 | FAIL | REASONING_GAP | reviewer: Most source-quality requirements are backed by [20], [31], [9], [30], and [2], especially the limits on oscilloscope evidence and non-binding battle-card/specification material. However, cit |
| Q0631 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0646 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0701 | FAIL | REASONING_GAP | reviewer: The passages support individual instrument capabilities and mention AI-assisted test planning/log analysis plus generative-AI connected devices, but they do not establish which signal-genera |
| Q0871 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1061 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1091 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
