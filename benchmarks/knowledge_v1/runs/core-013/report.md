# knowledge_v1 — core-013

Run at 2026-10-12T02:27:30+00:00, AEP commit `677e18aff37115143bfebc3a0b61b8b2680c8ae3`, grader 1.3, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**27 of 36 acceptable** (PASS 25, INSUFFICIENT_KNOWLEDGE 2); FAIL 8, NEEDS_HUMAN_REVIEW 1, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 5 | 0 | 1 | 0 | 0 |
| Aerospace / Defense | 4 | 0 | 1 | 1 | 0 |
| Automotive | 5 | 1 | 0 | 0 | 0 |
| Semiconductor | 4 | 1 | 1 | 0 | 0 |
| Wireless Communication | 4 | 0 | 2 | 0 | 0 |
| foundation | 3 | 0 | 3 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 1 | 0 | 0 | 0 | 0 |
| High-Speed / Signal Integrity | 0 | 0 | 1 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 4 | 2 | 0 | 1 | 0 |
| RF / Measurement Fundamentals | 1 | 0 | 0 | 0 | 0 |
| Signal Generator / Signal Analyzer | 5 | 0 | 1 | 0 | 0 |
| Signaling / Non-signaling Tester | 8 | 0 | 3 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 5 | 0 | 1 | 0 | 0 |
| Wireless Fundamentals | 0 | 0 | 1 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 4 | 1 | 0 | 0 | 0 |
| basic | 4 | 0 | 1 | 0 | 0 |
| competitive | 4 | 0 | 1 | 0 | 0 |
| cross_domain | 3 | 1 | 1 | 0 | 0 |
| foundation | 3 | 0 | 3 | 0 | 0 |
| solution_mapping | 4 | 0 | 1 | 0 | 0 |
| strategic | 3 | 0 | 1 | 1 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: REASONING_GAP 6, SOURCE_GAP or RETRIEVAL_GAP 2, VALIDATION_GAP 2

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0039 | FAIL | REASONING_GAP | reviewer: The main recommendation to use formal R&S specifications/features documents and official competitor or third-party evidence is well supported by the cited passages. However, several detailed |
| Q0121 | FAIL | REASONING_GAP | reviewer: Most chains are backed by the provided passages, especially MIMO/beamforming, OTA receiver testing, conducted Tx conformance, spectrum/frequency drivers, and O-RAN U-Plane/beamforming. Howev |
| Q0296 | NEEDS_HUMAN_REVIEW |  | the reviewer gave no verdict (model_http_error) |
| Q0351 | FAIL | REASONING_GAP | reviewer: The answer reasonably caveats that the passages do not rank capabilities and bases much of the recommendation on satellite payload/component testing evidence. However, several listed 'import |
| Q0461 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0631 | FAIL | REASONING_GAP | reviewer: The cited passages support AI/data-center interconnect and PCB trends, PCB/SI measurement items, and separate CMX500/CMP180 Wi-Fi test capabilities. They do not establish that AI data center |
| Q0846 | FAIL | REASONING_GAP | reviewer: Several core opportunities are supported by the supplied passages, especially Anritsu pre-silicon Shift-Left, the CMX500/CMP180 Wi‑Fi 7 R&D-vs-production split, CMX500 general capabilities,  |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1021 | FAIL | REASONING_GAP | reviewer: The OFDM explanation and many product-option examples are supported by the provided passages, especially NR resource grid, numerology, sample rate, CP, PAPR, OFDM generation/analysis options |
| Q1041 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1061 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
