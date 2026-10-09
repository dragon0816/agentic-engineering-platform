# knowledge_v1 — core-002

Run at 2026-10-09T12:57:21+00:00, AEP commit `def5ea6e154a26875cf1755614a5303b697c8abd`, grader 1.3, question bank sha256 `f5275373dad7…`, set `Q0011,Q0039,Q0051,Q0121,Q0131,Q0196,Q0211,Q0221,Q0231,Q0296,Q0339,Q0351,Q0401,Q0461,Q0489,Q0546,Q0571,Q0581,Q0631,Q0639,Q0646,Q0671,Q0701,Q0761,Q0801,Q0846,Q0871,Q0881,Q0911,Q0989,Q1001,Q1021,Q1041,Q1061,Q1071,Q1091`.

**27 of 36 acceptable** (PASS 25, INSUFFICIENT_KNOWLEDGE 2); FAIL 9, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 6 | 0 | 0 | 0 | 0 |
| Aerospace / Defense | 3 | 1 | 2 | 0 | 0 |
| Automotive | 5 | 1 | 0 | 0 | 0 |
| Semiconductor | 4 | 0 | 2 | 0 | 0 |
| Wireless Communication | 4 | 0 | 2 | 0 | 0 |
| foundation | 3 | 0 | 3 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 0 | 1 | 0 | 0 |
| High-Speed / Signal Integrity | 0 | 0 | 1 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 6 | 0 | 1 | 0 | 0 |
| RF / Measurement Fundamentals | 1 | 0 | 0 | 0 | 0 |
| Signal Generator / Signal Analyzer | 5 | 0 | 1 | 0 | 0 |
| Signaling / Non-signaling Tester | 8 | 1 | 2 | 0 | 0 |
| Technical Document / Paper Understanding | 1 | 0 | 0 | 0 | 0 |
| Vector Network Analyzer | 3 | 1 | 2 | 0 | 0 |
| Wireless Fundamentals | 1 | 0 | 0 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 4 | 1 | 0 | 0 | 0 |
| basic | 4 | 0 | 1 | 0 | 0 |
| competitive | 3 | 0 | 2 | 0 | 0 |
| cross_domain | 4 | 1 | 0 | 0 | 0 |
| foundation | 3 | 0 | 3 | 0 | 0 |
| solution_mapping | 4 | 0 | 1 | 0 | 0 |
| strategic | 3 | 0 | 2 | 0 | 0 |

## Harness

Routes: direct 10, tool 26

Gaps: REASONING_GAP 5, VALIDATION_GAP 4, SOURCE_GAP or RETRIEVAL_GAP 2

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0039 | FAIL | REASONING_GAP | reviewer: The passages support using formal R&S product/specification evidence, limiting claims to stated CMX500/CMP180 capabilities, and treating battle cards cautiously. However, the key requirement |
| Q0196 | FAIL | REASONING_GAP | reviewer: The cited passages support that LEO/Direct-to-Cell and Wi‑Fi 7 are wireless-communication supply-chain or standards topics, and that VNA base units are available up to 43.5 GHz. They do not  |
| Q0211 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0339 | FAIL | REASONING_GAP | reviewer: Most operational guidance is backed: formal R&S specs are supported, internal battle cards are limited, competitor claims need official/third-party evidence, and the PARPRO link is unresolve |
| Q0351 | FAIL | REASONING_GAP | reviewer: The cited passages support the listed product facts about ZNB3020 frequency/ports, uncertainty options, PCB test items, group delay setup, and NR-NTN option. However, they do not establish w |
| Q0581 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0846 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0871 | FAIL | REASONING_GAP | reviewer: The cited passages support the separate facts: AI-server/800V power-semiconductor demand, SI parameters such as IL/Xtalk/Eye/TDR, PDN impedance as a PI topic, and scopes being mapped to Inte |
| Q1041 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1061 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1091 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_model_failed) |
