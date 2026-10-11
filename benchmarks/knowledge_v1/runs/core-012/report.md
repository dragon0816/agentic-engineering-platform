# knowledge_v1 — core-012

Run at 2026-10-11T21:44:33+00:00, AEP commit `425c5f61e582b4fbf04e9022342a1e882549dc32`, grader 1.3, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**30 of 36 acceptable** (PASS 28, INSUFFICIENT_KNOWLEDGE 2); FAIL 6, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 5 | 0 | 1 | 0 | 0 |
| Aerospace / Defense | 5 | 1 | 0 | 0 | 0 |
| Automotive | 5 | 0 | 1 | 0 | 0 |
| Semiconductor | 4 | 1 | 1 | 0 | 0 |
| Wireless Communication | 5 | 0 | 1 | 0 | 0 |
| foundation | 4 | 0 | 2 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 1 | 0 | 0 | 0 | 0 |
| High-Speed / Signal Integrity | 1 | 0 | 0 | 0 | 0 |
| Instrument & Measurement Principles | 1 | 0 | 0 | 0 | 0 |
| Oscilloscope | 6 | 1 | 0 | 0 | 0 |
| RF / Measurement Fundamentals | 0 | 0 | 1 | 0 | 0 |
| Signal Generator / Signal Analyzer | 5 | 0 | 1 | 0 | 0 |
| Signaling / Non-signaling Tester | 8 | 1 | 2 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 5 | 0 | 1 | 0 | 0 |
| Wireless Fundamentals | 0 | 0 | 1 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 5 | 0 | 0 | 0 | 0 |
| basic | 5 | 0 | 0 | 0 | 0 |
| competitive | 4 | 0 | 1 | 0 | 0 |
| cross_domain | 4 | 1 | 0 | 0 | 0 |
| foundation | 4 | 0 | 2 | 0 | 0 |
| solution_mapping | 2 | 1 | 2 | 0 | 0 |
| strategic | 4 | 0 | 1 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: REASONING_GAP 6, SOURCE_GAP or RETRIEVAL_GAP 2

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0121 | FAIL | REASONING_GAP | reviewer: Much of the MIMO, OTA, spectrum/mmWave, and NTN mapping is supported by the provided passages. However, the SAN measurement/capability details, the detailed energy-efficiency measurement and |
| Q0221 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_grounded) |
| Q0571 | FAIL | REASONING_GAP | reviewer: The automotive high-speed requirement, PCB/SI measurable items, ZNA frequency/specification data, and the caveat about lack of a complete formal PCB solution are supported. However, the cite |
| Q0639 | FAIL | REASONING_GAP | reviewer: The main cautious conclusion—that formal R&S specs/configuration evidence, competitor official evidence, AI-use-case linkage, and matched test conditions are needed—is a fair reading of the  |
| Q0846 | FAIL | REASONING_GAP | reviewer: The core five opportunities in the opening recommendation are well supported by the supplied passages: Virtual Signalling Tester pre-silicon chipset testing, CMX500/TS8980 NR-NTN validation, |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1001 | FAIL | REASONING_GAP | reviewer: Most core EVM definitions and many UE/BS/OTA/CMX/CMP200 decision points are supported by the provided passages. However, several substantial product-related rows and the final limitations re |
| Q1021 | FAIL | REASONING_GAP | reviewer: Most of the OFDM/NR-grid explanation and several measurement-decision rows are supported by the provided passages. However, the CORESET/PDCCH and SMBV100B rows rely on cited sources whose pa |
