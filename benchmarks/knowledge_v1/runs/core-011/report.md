# knowledge_v1 — core-011

Run at 2026-10-11T20:42:29+00:00, AEP commit `43dcd768407a2d886f206247265fe4047797a8eb`, grader 1.3, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**25 of 36 acceptable** (PASS 23, INSUFFICIENT_KNOWLEDGE 2); FAIL 11, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 4 | 0 | 2 | 0 | 0 |
| Aerospace / Defense | 5 | 1 | 0 | 0 | 0 |
| Automotive | 5 | 0 | 1 | 0 | 0 |
| Semiconductor | 4 | 1 | 1 | 0 | 0 |
| Wireless Communication | 3 | 0 | 3 | 0 | 0 |
| foundation | 2 | 0 | 4 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 0 | 1 | 0 | 0 |
| High-Speed / Signal Integrity | 0 | 0 | 1 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 5 | 1 | 1 | 0 | 0 |
| RF / Measurement Fundamentals | 0 | 0 | 1 | 0 | 0 |
| Signal Generator / Signal Analyzer | 3 | 0 | 3 | 0 | 0 |
| Signaling / Non-signaling Tester | 8 | 1 | 2 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 5 | 0 | 1 | 0 | 0 |
| Wireless Fundamentals | 1 | 0 | 0 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 5 | 0 | 0 | 0 | 0 |
| basic | 4 | 0 | 1 | 0 | 0 |
| competitive | 3 | 0 | 2 | 0 | 0 |
| cross_domain | 3 | 1 | 1 | 0 | 0 |
| foundation | 2 | 0 | 4 | 0 | 0 |
| solution_mapping | 3 | 1 | 1 | 0 | 0 |
| strategic | 3 | 0 | 2 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: REASONING_GAP 9, SOURCE_GAP or RETRIEVAL_GAP 2, VALIDATION_GAP 2

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0121 | FAIL | REASONING_GAP | reviewer: Most of the 3GPP, MIMO/beamforming, OTA, spectrum-bandwidth, and O-RAN mappings are supported by the provided passages. However, the energy-efficiency row and the NTN row rely on cited items |
| Q0131 | FAIL | REASONING_GAP | reviewer: The core Wi‑Fi 7/8 conclusions about 320 MHz-class bandwidth, MLO/MIMO multi-chain needs, CMP180 500 MHz/candidate 480 MHz waveform work, and Wi‑Fi 8 dRU/UEQM signaling tests are supported b |
| Q0196 | FAIL | REASONING_GAP | reviewer: The core opportunity framing for LEO/satcom RF front ends, 5G FR2/FR2-2 mmWave work, and high-frequency PCB/SI is a fair inference from the provided market, frequency-range, OTA-metric, PCB- |
| Q0221 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_grounded) |
| Q0489 | FAIL | REASONING_GAP | reviewer: Most guidance about using formal specifications, competitor official evidence, avoiding sales language, and substantiating TCO is backed by the cited passages. However, the cited evidence do |
| Q0639 | FAIL | REASONING_GAP | reviewer: Much of the non-AI comparison guidance is supported by the provided passages, especially the need for formal CMX500 specs/options and caution around sales battle cards. However, several cent |
| Q0701 | FAIL | REASONING_GAP | reviewer: Most listed instrument capabilities are supported by the cited passages, and the answer reasonably caveats that the passages do not provide an AI-specific ranking. However, the framing as th |
| Q0846 | FAIL | REASONING_GAP | reviewer: The core recommendations for CMX500 in 5G device/chipset validation, CMP180 for WLAN production non-signaling RF, and Virtual Signalling Tester for pre-silicon chipset protocol testing are s |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1001 | FAIL | REASONING_GAP | reviewer: Most definitions of EVM and many measurement/product option decisions are supported by the provided passages. However, several cited claims rely on passages [38], [47], and [51], which are n |
| Q1041 | FAIL | REASONING_GAP | reviewer: The cited passages support the specific facts about PCIe eye-opening limits, eye diagram appearing in SI/material-stackup workflows, and ZNA/ZNA67EXT option dependencies. However, the answer |
| Q1061 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1091 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
