# knowledge_v1 — core-001

Run at 2026-10-09T10:19:06+00:00, AEP commit `cd948b1075d1d1d0025d98a062d74be6f2f3151b`, grader 1.3, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**30 of 36 acceptable** (PASS 20, INSUFFICIENT_KNOWLEDGE 10); FAIL 6, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 5 | 0 | 1 | 0 | 0 |
| Aerospace / Defense | 3 | 2 | 1 | 0 | 0 |
| Automotive | 5 | 0 | 1 | 0 | 0 |
| Semiconductor | 2 | 2 | 2 | 0 | 0 |
| Wireless Communication | 5 | 0 | 1 | 0 | 0 |
| foundation | 0 | 6 | 0 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 1 | 0 | 0 | 0 |
| High-Speed / Signal Integrity | 0 | 1 | 0 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 1 | 0 | 0 | 0 |
| Oscilloscope | 4 | 1 | 2 | 0 | 0 |
| RF / Measurement Fundamentals | 0 | 1 | 0 | 0 | 0 |
| Signal Generator / Signal Analyzer | 3 | 0 | 3 | 0 | 0 |
| Signaling / Non-signaling Tester | 8 | 2 | 1 | 0 | 0 |
| Technical Document / Paper Understanding | 0 | 1 | 0 | 0 | 0 |
| Vector Network Analyzer | 5 | 1 | 0 | 0 | 0 |
| Wireless Fundamentals | 0 | 1 | 0 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 2 | 0 | 3 | 0 | 0 |
| basic | 3 | 1 | 1 | 0 | 0 |
| competitive | 5 | 0 | 0 | 0 | 0 |
| cross_domain | 2 | 1 | 2 | 0 | 0 |
| foundation | 0 | 6 | 0 | 0 | 0 |
| solution_mapping | 4 | 1 | 0 | 0 | 0 |
| strategic | 4 | 1 | 0 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: SOURCE_GAP or RETRIEVAL_GAP 10, REASONING_GAP 4, VALIDATION_GAP 2

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0131 | FAIL | REASONING_GAP | reviewer: The broad points about 320 MHz bandwidth, 4096QAM, MLO requiring multiple RF chains, signaling-mode R&D tests, 2x2 MIMO, coexistence, and 6 GHz/7.125 GHz coverage are supported by the passag |
| Q0211 | FAIL | REASONING_GAP | reviewer: The cited passages support that the CMX500 signaling tester can be central to certain wireless/NTN/FR3 R&D test setups and can support fading/channel emulation, but they do not address Aeros |
| Q0231 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_validated) |
| Q0351 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_validated) |
| Q0461 | FAIL | REASONING_GAP | reviewer: The factual statements about AREG800A echo generation, IF/control interfaces, and broader R&S automotive lifecycle support are backed by the cited passages. However, the answer does not addr |
| Q0701 | FAIL | REASONING_GAP | reviewer: The cited passages support GNSS/avionics options for R&S signal generators and agentic-AI features for the CONTEST sequencer, but they do not identify 'most important' signal-generation capa |
| Q0846 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_validated) |
| Q0871 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0881 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0911 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1001 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_validated) |
| Q1021 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_validated) |
| Q1041 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_validated) |
| Q1061 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_validated) |
| Q1071 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_validated) |
| Q1091 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_validated) |
