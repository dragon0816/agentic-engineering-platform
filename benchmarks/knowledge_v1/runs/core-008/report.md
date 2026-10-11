# knowledge_v1 — core-008

Run at 2026-10-11T07:36:00+00:00, AEP commit `ce756713dcbaececff16deb99a8952ce23b8f972`, grader 1.3, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**26 of 36 acceptable** (PASS 19, INSUFFICIENT_KNOWLEDGE 7); FAIL 10, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 3 | 0 | 3 | 0 | 0 |
| Aerospace / Defense | 4 | 2 | 0 | 0 | 0 |
| Automotive | 2 | 2 | 2 | 0 | 0 |
| Semiconductor | 3 | 2 | 1 | 0 | 0 |
| Wireless Communication | 4 | 0 | 2 | 0 | 0 |
| foundation | 3 | 1 | 2 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 0 | 1 | 0 | 0 |
| High-Speed / Signal Integrity | 1 | 0 | 0 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 1 | 0 | 0 | 0 |
| Oscilloscope | 0 | 4 | 3 | 0 | 0 |
| RF / Measurement Fundamentals | 0 | 0 | 1 | 0 | 0 |
| Signal Generator / Signal Analyzer | 6 | 0 | 0 | 0 | 0 |
| Signaling / Non-signaling Tester | 7 | 0 | 4 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 3 | 2 | 1 | 0 | 0 |
| Wireless Fundamentals | 1 | 0 | 0 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 4 | 1 | 0 | 0 | 0 |
| basic | 3 | 1 | 1 | 0 | 0 |
| competitive | 3 | 0 | 2 | 0 | 0 |
| cross_domain | 2 | 1 | 2 | 0 | 0 |
| foundation | 3 | 1 | 2 | 0 | 0 |
| solution_mapping | 2 | 2 | 1 | 0 | 0 |
| strategic | 2 | 1 | 2 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: REASONING_GAP 7, SOURCE_GAP or RETRIEVAL_GAP 7, VALIDATION_GAP 3

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0039 | FAIL | REASONING_GAP | reviewer: The R&S product-document portions are mostly supported by the provided CMX500, CMP200, and CMP180 passages. However, much of the answer’s core guidance about competitor evidence, battle-card |
| Q0051 | FAIL | REASONING_GAP | reviewer: The passages support that R&S worked on 3GPP mmWave testing, EVM tuning, and signal integrity after up-conversion, and they list some instruments and generic SI activities. They do not estab |
| Q0296 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0351 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0461 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0489 | FAIL | REASONING_GAP | reviewer: The answer is a reasonable conservative checklist for avoiding unsupported competitive claims, and several cautions about sales language, battle-card validation, and the weak Automotive/UAV  |
| Q0571 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0581 | FAIL | REASONING_GAP | reviewer: The frequency/bandwidth shift from 24 GHz/250 MHz to 76–81 GHz/GHz-class bandwidth, and several VNA specs such as 110 GHz coverage, dynamic range, IF spans, and coherent multiport capability |
| Q0631 | FAIL | REASONING_GAP | reviewer: Most listed data-center trends and signaling/non-signaling tester capabilities are supported by the passages, and the answer reasonably notes that the passages do not show wireless testers d |
| Q0646 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0671 | FAIL | REASONING_GAP | reviewer: The cited passages support that MXO is listed for `power rail / multiphase DC / PI` under server motherboard/PCBA, and that PDN testing is associated with scopes and network analyzers. They  |
| Q0846 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0871 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_grounded) |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1001 | FAIL | REASONING_GAP | reviewer: The answer’s core explanation of EVM and most CMX500, UE pre-conformance, SRS, FR2 frontend, and base-station conformance points are supported by the supplied passages. However, several FSV3 |
| Q1061 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1091 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
