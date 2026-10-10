# knowledge_v1 — core-006

Run at 2026-10-10T10:38:53+00:00, AEP commit `839711bb525d1c5449ae3e5211bfb96c8b11e869`, grader 1.3, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**24 of 36 acceptable** (PASS 18, INSUFFICIENT_KNOWLEDGE 6); FAIL 11, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 1

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 3 | 0 | 3 | 0 | 0 |
| Aerospace / Defense | 4 | 1 | 0 | 0 | 1 |
| Automotive | 2 | 2 | 2 | 0 | 0 |
| Semiconductor | 3 | 2 | 1 | 0 | 0 |
| Wireless Communication | 4 | 0 | 2 | 0 | 0 |
| foundation | 2 | 1 | 3 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 1 | 0 | 0 | 0 |
| High-Speed / Signal Integrity | 1 | 0 | 0 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 3 | 1 | 2 | 0 | 1 |
| RF / Measurement Fundamentals | 0 | 0 | 1 | 0 | 0 |
| Signal Generator / Signal Analyzer | 4 | 0 | 2 | 0 | 0 |
| Signaling / Non-signaling Tester | 6 | 2 | 3 | 0 | 0 |
| Technical Document / Paper Understanding | 0 | 0 | 1 | 0 | 0 |
| Vector Network Analyzer | 3 | 2 | 1 | 0 | 0 |
| Wireless Fundamentals | 1 | 0 | 0 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 4 | 1 | 0 | 0 | 0 |
| basic | 2 | 2 | 1 | 0 | 0 |
| competitive | 2 | 0 | 3 | 0 | 0 |
| cross_domain | 3 | 1 | 1 | 0 | 0 |
| foundation | 2 | 1 | 3 | 0 | 0 |
| solution_mapping | 5 | 0 | 0 | 0 | 0 |
| strategic | 0 | 1 | 3 | 0 | 1 |

## Harness

Routes: direct 10, none 1, tool 25

Gaps: REASONING_GAP 7, SOURCE_GAP or RETRIEVAL_GAP 6, VALIDATION_GAP 4, SYSTEM_ERROR 1

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0039 | FAIL | REASONING_GAP | reviewer: The answer’s core guidance—use formal R&S specs/features, competitor official or third-party evidence, and treat battle cards as sales positioning—is well supported by passages [30], [34], [ |
| Q0196 | FAIL | REASONING_GAP | reviewer: The cited passages show only that some wireless lab instrument categories exist, that two products are vector network analyzers, and that VNA base units/options include multiple frequency ra |
| Q0296 | SYSTEM_ERROR | SYSTEM_ERROR | turn timed out or HTTP 0 |
| Q0351 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0461 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0489 | FAIL | REASONING_GAP | reviewer: Passages [8] and [7] support the need for formal specifications and caution against treating sales/battle-card language as binding specs. However, no cited passage supports the oscilloscope/ |
| Q0546 | FAIL | REASONING_GAP | reviewer: The main recommendation—CMX500-based hybrid/NG eCall as the strongest supported automotive signal-generator/analyzer-type opportunity—is well supported by passages on eCall testing, CMX500 c |
| Q0581 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0639 | FAIL | REASONING_GAP | reviewer: The core conclusion—that a defensible AI comparison needs formal R&S specifications/features, official competitor or third-party evidence, and AI-specific validation/version/deployment evide |
| Q0646 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0701 | FAIL | REASONING_GAP | reviewer: The cited passages support EVM tuning/signal integrity in 3GPP mmWave testing and AI-assisted test planning/log analysis, but they do not establish these as the 'most important' signal gener |
| Q0801 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0846 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0881 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1001 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1061 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1071 | FAIL | REASONING_GAP | reviewer: The cited passages support only that the test/measurement method is "Measurement." The answer does not address the question's second part about which product-related measurement decisions de |
| Q1091 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
