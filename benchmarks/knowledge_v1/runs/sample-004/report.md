# knowledge_v1 — sample-004

Run at 2026-10-09T07:54:48+00:00, AEP commit `0896132762321fc42fba66bf9709ae2eb89b68bb`, grader 1.3, question bank sha256 `f5275373dad7…`, set `sample`.

**26 of 110 acceptable** (PASS 24, INSUFFICIENT_KNOWLEDGE 2); FAIL 27, NEEDS_HUMAN_REVIEW 41, SYSTEM_ERROR 16

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 5 | 0 | 7 | 8 | 0 |
| Aerospace / Defense | 5 | 0 | 5 | 7 | 3 |
| Automotive | 3 | 2 | 7 | 5 | 3 |
| Semiconductor | 4 | 0 | 5 | 10 | 1 |
| Wireless Communication | 7 | 0 | 2 | 11 | 0 |
| foundation | 0 | 0 | 1 | 0 | 9 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 0 | 0 | 0 | 1 |
| High-Speed / Signal Integrity | 0 | 0 | 0 | 0 | 2 |
| Instrument & Measurement Principles | 0 | 0 | 0 | 0 | 1 |
| Oscilloscope | 4 | 1 | 11 | 8 | 1 |
| RF / Measurement Fundamentals | 0 | 0 | 1 | 0 | 1 |
| Signal Generator / Signal Analyzer | 5 | 0 | 9 | 8 | 3 |
| Signaling / Non-signaling Tester | 7 | 0 | 2 | 14 | 2 |
| Technical Document / Paper Understanding | 0 | 0 | 0 | 0 | 2 |
| Vector Network Analyzer | 8 | 1 | 4 | 11 | 1 |
| Wireless Fundamentals | 0 | 0 | 0 | 0 | 2 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 0 | 0 | 2 | 13 | 1 |
| basic | 0 | 0 | 4 | 11 | 1 |
| competitive | 13 | 1 | 3 | 0 | 0 |
| cross_domain | 0 | 0 | 7 | 8 | 2 |
| foundation | 0 | 0 | 1 | 0 | 9 |
| solution_mapping | 11 | 1 | 3 | 0 | 2 |
| strategic | 0 | 0 | 7 | 9 | 1 |

## Harness

Routes: direct 33, none 15, tool 62

Gaps: VALIDATION_GAP 21, SYSTEM_ERROR 15, REASONING_GAP 6, SOURCE_GAP or RETRIEVAL_GAP 2, EXECUTION_GAP 1

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0011 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0031 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0046 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0051 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0061 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0081 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0096 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0101 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0111 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0131 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0151 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0181 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0196 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0211 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0231 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0246 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0251 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0261 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0271 | FAIL | REASONING_GAP | reviewer: The cited passages support the defense/private-5G drivers and list PCB test-flow parameters such as TDR impedance and eye diagram, but they do not link those A&D drivers to those measurable  |
| Q0281 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0296 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0301 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0311 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0321 | SYSTEM_ERROR | EXECUTION_GAP | Knowledge did not complete (knowledge_model_failed) |
| Q0331 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
| Q0351 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
| Q0381 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0396 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0401 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0411 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0431 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
| Q0446 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
| Q0451 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0461 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0481 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0489 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0496 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0501 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0511 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
| Q0539 | FAIL | REASONING_GAP | reviewer: The answer is a conservative and relevant checklist for avoiding unsupported competitive claims, and several cautions are backed by passages [1], [4], [12], [21], and [26]. However, passage  |
| Q0546 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0551 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0561 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0571 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0581 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0601 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0611 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0631 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0646 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0661 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0681 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0696 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0701 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0721 | FAIL | REASONING_GAP | reviewer: Most chains for PCBA, PCB, connectors/cables, network switches, silicon photonics, and the stated Signal Generator gap are supported by the cited passages. However, the detailed power-supply |
| Q0731 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0739 | FAIL | REASONING_GAP | reviewer: Most R&S configuration, AI-mapping, measurement-condition, and market/adoption cautions are supported by passages [1], [2], [3], [7], [9], and [10]. However, the central competitor-compariso |
| Q0746 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0751 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0761 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0796 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0801 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0811 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0831 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0846 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0861 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0871 | SYSTEM_ERROR | SYSTEM_ERROR | turn timed out or HTTP 0 |
| Q0881 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0896 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0901 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0931 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0939 | FAIL | REASONING_GAP | reviewer: Most cautionary requirements are backed by the cited passages: formal R&S specs must be checked, battle-card competitor claims are not official, PR/demo evidence lacks test conditions, and o |
| Q0946 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q0951 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0961 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q0971 | FAIL | REASONING_GAP | reviewer: The cited passages support Qualcomm's role/focus and the VNA frequency ranges/configuration, but they do not establish a chain from the semiconductor market requirement to a specific measura |
| Q0996 | NEEDS_HUMAN_REVIEW |  | the trace predates the host record carrying the cited passages |
| Q1001 | FAIL | VALIDATION_GAP | the Knowledge Harness did not validate an answer (knowledge_not_validated) |
| Q1011 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
| Q1021 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
| Q1031 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
| Q1041 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
| Q1051 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
| Q1061 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
| Q1071 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
| Q1081 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
| Q1091 | SYSTEM_ERROR | SYSTEM_ERROR | the conversation failed (model_http_error) |
