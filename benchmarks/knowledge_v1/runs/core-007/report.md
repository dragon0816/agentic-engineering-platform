# knowledge_v1 — core-007

Run at 2026-10-11T06:10:17+00:00, AEP commit `e097aa04589d30fb943bfd39e9fac5d19b398f0f`, grader 1.3, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**25 of 36 acceptable** (PASS 18, INSUFFICIENT_KNOWLEDGE 7); FAIL 11, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 4 | 0 | 2 | 0 | 0 |
| Aerospace / Defense | 3 | 2 | 1 | 0 | 0 |
| Automotive | 2 | 3 | 1 | 0 | 0 |
| Semiconductor | 3 | 2 | 1 | 0 | 0 |
| Wireless Communication | 4 | 0 | 2 | 0 | 0 |
| foundation | 2 | 0 | 4 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 0 | 1 | 0 | 0 |
| High-Speed / Signal Integrity | 1 | 0 | 0 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 2 | 4 | 1 | 0 | 0 |
| RF / Measurement Fundamentals | 1 | 0 | 0 | 0 | 0 |
| Signal Generator / Signal Analyzer | 2 | 1 | 3 | 0 | 0 |
| Signaling / Non-signaling Tester | 8 | 0 | 3 | 0 | 0 |
| Technical Document / Paper Understanding | 0 | 0 | 1 | 0 | 0 |
| Vector Network Analyzer | 4 | 2 | 0 | 0 | 0 |
| Wireless Fundamentals | 0 | 0 | 1 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 4 | 1 | 0 | 0 | 0 |
| basic | 4 | 1 | 0 | 0 | 0 |
| competitive | 3 | 0 | 2 | 0 | 0 |
| cross_domain | 2 | 1 | 2 | 0 | 0 |
| foundation | 2 | 0 | 4 | 0 | 0 |
| solution_mapping | 2 | 2 | 1 | 0 | 0 |
| strategic | 1 | 2 | 2 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: SOURCE_GAP or RETRIEVAL_GAP 7, REASONING_GAP 6, VALIDATION_GAP 5

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0121 | FAIL | REASONING_GAP | reviewer: The core mapping from FWA test indicators to VSG/VSA/SMW/FSW/CMP instruments and from NTN channel parameters to SMW200A/FSW capabilities is mostly backed by the provided passages. However, s |
| Q0131 | FAIL | REASONING_GAP | reviewer: Most Wi‑Fi 7/8 capability points are backed by the passages: 320 MHz bandwidth, 4096QAM with cited EVM examples, MLO/multiple RF chains, Wi‑Fi 8 dRU/UEQM signaling analysis, and 480 MHz only |
| Q0296 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0339 | FAIL | REASONING_GAP | reviewer: Most of the answer is a conservative, evidence-backed description of what would be needed for a defensible Aerospace/Defense competitor comparison, and the cited passages support the gaps ar |
| Q0351 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0461 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0489 | FAIL | VALIDATION_GAP | 1 of 7 citations not found in the Vault |
| Q0546 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0571 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_grounded) |
| Q0631 | FAIL | REASONING_GAP | reviewer: The cited passages support the listed AI data-center components and the CMX500/CMP180/CMW tester capabilities, but they do not establish that AI data-center technology changes drive or affec |
| Q0646 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0846 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0871 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_grounded) |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1021 | FAIL | REASONING_GAP | reviewer: The NR-related explanation and product-option connections are mostly supported by the provided passages. However, several main WLAN and RAW-passage claims rely on cited passage numbers that  |
| Q1061 | FAIL | VALIDATION_GAP | 1 of 12 citations not found in the Vault |
| Q1071 | FAIL | REASONING_GAP | reviewer: The cited passages support only that the test method is 'Measurement.' The answer does not address the question's second part about which product-related measurement decisions depend on unde |
| Q1091 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
