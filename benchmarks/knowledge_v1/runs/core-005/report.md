# knowledge_v1 — core-005

Run at 2026-10-10T03:56:03+00:00, AEP commit `9cbe3cab8743b92cca4507b00369ec98fe625949`, grader 1.3, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**29 of 36 acceptable** (PASS 25, INSUFFICIENT_KNOWLEDGE 4); FAIL 7, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 4 | 0 | 2 | 0 | 0 |
| Aerospace / Defense | 4 | 1 | 1 | 0 | 0 |
| Automotive | 4 | 0 | 2 | 0 | 0 |
| Semiconductor | 2 | 3 | 1 | 0 | 0 |
| Wireless Communication | 6 | 0 | 0 | 0 | 0 |
| foundation | 5 | 0 | 1 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 1 | 0 | 0 | 0 | 0 |
| High-Speed / Signal Integrity | 1 | 0 | 0 | 0 | 0 |
| Instrument & Measurement Principles | 1 | 0 | 0 | 0 | 0 |
| Oscilloscope | 4 | 2 | 1 | 0 | 0 |
| RF / Measurement Fundamentals | 0 | 0 | 1 | 0 | 0 |
| Signal Generator / Signal Analyzer | 5 | 0 | 1 | 0 | 0 |
| Signaling / Non-signaling Tester | 7 | 1 | 3 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 4 | 1 | 1 | 0 | 0 |
| Wireless Fundamentals | 1 | 0 | 0 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 5 | 0 | 0 | 0 | 0 |
| basic | 3 | 2 | 0 | 0 | 0 |
| competitive | 3 | 0 | 2 | 0 | 0 |
| cross_domain | 3 | 1 | 1 | 0 | 0 |
| foundation | 5 | 0 | 1 | 0 | 0 |
| solution_mapping | 3 | 1 | 1 | 0 | 0 |
| strategic | 3 | 0 | 2 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: REASONING_GAP 5, SOURCE_GAP or RETRIEVAL_GAP 4, VALIDATION_GAP 2

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0339 | FAIL | REASONING_GAP | reviewer: Most of the answer is a fair, evidence-backed statement that the current passages do not yet connect a competitor, Aerospace/Defense use case, and signal generator/analyzer comparison, and t |
| Q0351 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0489 | FAIL | REASONING_GAP | reviewer: Most evidentiary cautions about competitor sources, specifications, numerical claim types, binding conditions, and sales language are supported by passages [18], [6], and [44]. However, the  |
| Q0571 | FAIL | REASONING_GAP | reviewer: Several rows are supported by the passages, such as Low DK automotive-linked PCB material, Dk/Df/insertion-loss/impedance measurements, ZNA-K2 TDR, ZNA-K20 eye diagram, and the ZNA frequency |
| Q0631 | FAIL | REASONING_GAP | reviewer: The cited passages support the listed AI data-center ecosystem items and the CMX500/CMP180 capabilities, but they do not establish that AI data-center technology changes create Wi-Fi 7/cellu |
| Q0646 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0801 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0846 | FAIL | REASONING_GAP | reviewer: Most listed opportunities are supported by the provided passages, including Anritsu pre/post-silicon protocol testing, CMX500 RedCap/NTN, Wi‑Fi 7 R&D, CMP180 production non-signaling, and Wi |
| Q0871 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_grounded) |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1001 | FAIL | VALIDATION_GAP | 1 of 13 citations not found in the Vault |
