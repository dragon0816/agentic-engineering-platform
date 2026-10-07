# knowledge_v1 run comparison

Generated offline by `benchmarks/knowledge_v1/compare.py` from the stored `result.json` files.

| Run | Started | Commit | Grader | Questions | Compared | Left out |
|---|---|---|---|---|---|---|
| sample-002 | 2026-10-07T09:32:40+00:00 | `c64a724` | 1.1 | 110 | 110 | 0 |
| sample-003 | 2026-10-07T11:58:07+00:00 | `041c746` | 1.1 | 110 | 110 | 0 |

## Status

| Status | sample-002 | sample-003 |
|---|---|---|
| **acceptable** | **75 (68%)** | **68 (62%)** |
| PASS | 34 | 35 |
| INSUFFICIENT_KNOWLEDGE | 41 | 33 |
| FAIL | 35 | 40 |
| NEEDS_HUMAN_REVIEW | 0 | 0 |
| SYSTEM_ERROR | 0 | 2 |

## Route × status

| Run | Route | Questions | PASS | INSUFFICIENT | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR | PASS rate |
|---|---|---|---|---|---|---|---|---|
| sample-002 | direct | 34 | 19 | 13 | 2 | 0 | 0 | 56% |
| sample-002 | tool | 76 | 15 | 28 | 33 | 0 | 0 | 20% |
| sample-002 | none | 0 | 0 | 0 | 0 | 0 | 0 | – |
| sample-003 | direct | 34 | 25 | 3 | 6 | 0 | 0 | 74% |
| sample-003 | tool | 74 | 10 | 30 | 34 | 0 | 0 | 14% |
| sample-003 | none | 2 | 0 | 0 | 0 | 0 | 2 | 0% |

## By market

| market | n | sample-002 acc / PASS | sample-003 acc / PASS | Δ acc |
|---|---|---|---|---|
| AI | 20 | 11 / 5 | 8 / 7 | -3 |
| Aerospace / Defense | 20 | 12 / 5 | 12 / 7 | +0 |
| Automotive | 20 | 15 / 7 | 14 / 6 | -1 |
| Semiconductor | 20 | 15 / 8 | 12 / 6 | -3 |
| Wireless Communication | 20 | 16 / 9 | 13 / 9 | -3 |
| foundation | 10 | 6 / 0 | 9 / 0 | +3 |

## By product family

| product family | n | sample-002 acc / PASS | sample-003 acc / PASS | Δ acc |
|---|---|---|---|---|
| Cross-Knowledge Reasoning | 1 | 1 / 0 | 1 / 0 | +0 |
| High-Speed / Signal Integrity | 2 | 1 / 0 | 2 / 0 | +1 |
| Instrument & Measurement Principles | 1 | 1 / 0 | 0 / 0 | -1 |
| Oscilloscope | 25 | 18 / 5 | 21 / 7 | +3 |
| RF / Measurement Fundamentals | 2 | 2 / 0 | 2 / 0 | +0 |
| Signal Generator / Signal Analyzer | 25 | 14 / 8 | 10 / 8 | -4 |
| Signaling / Non-signaling Tester | 25 | 17 / 12 | 14 / 11 | -3 |
| Technical Document / Paper Understanding | 2 | 1 / 0 | 2 / 0 | +1 |
| Vector Network Analyzer | 25 | 20 / 9 | 14 / 9 | -6 |
| Wireless Fundamentals | 2 | 0 / 0 | 2 / 0 | +2 |

## By question type

| question type | n | sample-002 acc / PASS | sample-003 acc / PASS | Δ acc |
|---|---|---|---|---|
| application | 16 | 8 / 2 | 7 / 3 | -1 |
| basic | 16 | 9 / 5 | 8 / 2 | -1 |
| competitive | 17 | 16 / 15 | 14 / 14 | -2 |
| cross_domain | 17 | 11 / 2 | 8 / 0 | -3 |
| foundation | 10 | 6 / 0 | 9 / 0 | +3 |
| solution_mapping | 17 | 16 / 4 | 14 / 11 | -2 |
| strategic | 17 | 9 / 6 | 8 / 5 | -1 |

## By difficulty

| difficulty | n | sample-002 acc / PASS | sample-003 acc / PASS | Δ acc |
|---|---|---|---|---|
| L1 | 16 | 9 / 5 | 8 / 2 | -1 |
| L2 | 16 | 8 / 2 | 7 / 3 | -1 |
| L3 | 17 | 16 / 4 | 14 / 11 | -2 |
| L4 | 34 | 27 / 17 | 22 / 14 | -5 |
| L5 | 17 | 9 / 6 | 8 / 5 | -1 |
| foundation | 10 | 6 / 0 | 9 / 0 | +3 |

## Gap types

| Gap | sample-002 | sample-003 |
|---|---|---|
| REASONING_GAP | 35 | 40 |
| SOURCE_GAP or RETRIEVAL_GAP | 41 | 33 |
| SYSTEM_ERROR | 0 | 2 |

## Reviewer verdicts

Over answers the reviewer read (citations all verified); overreach = at least one claim listed as going beyond the passages.

| Run | Reviewed | Verdict given | Supported | Reasonable | Confidence high / medium / low | With overreach | Overreach items per answer |
|---|---|---|---|---|---|---|---|
| sample-002 | 69 | 69 | 35 (51%) | 38 (55%) | 62 / 7 / 0 | 66 (96%) | 5.5 |
| sample-003 | 75 | 75 | 35 (47%) | 42 (56%) | 66 / 9 / 0 | 71 (95%) | 6.3 |

## Latency (seconds)

| Run | Route | n | median | p90 |
|---|---|---|---|---|
| sample-002 | direct | 34 | 81.2 | 125.1 |
| sample-002 | tool | 76 | 61.6 | 103.8 |
| sample-002 | all | 110 | 66.3 | 113.5 |
| sample-003 | direct | 34 | 101.0 | 160.9 |
| sample-003 | tool | 74 | 140.5 | 308.4 |
| sample-003 | none | 2 | 600.0 | 600.0 |
| sample-003 | all | 110 | 121.0 | 282.6 |

## Citations

Checked answers are those whose citations were checked against the Vault.

| Run | Checked answers | Citations | Per checked answer | Verified in the Vault |
|---|---|---|---|---|
| sample-002 | 69 | 404 | 5.9 | 404 (100%) |
| sample-003 | 75 | 486 | 6.5 | 486 (100%) |

## Transitions sample-002 → sample-003

Improved 26, regressed 26, unchanged 58 (of 110).

| Question | Change | Old → new | Route | Tags | Reason (new run) |
|---|---|---|---|---|---|
| Q0021 | improved | INSUFFICIENT → PASS | direct | Wireless Communication; solution_mapping | was: the harness ran and reported a gap (needs_input) |
| Q0031 | regressed | PASS → FAIL | tool | Wireless Communication; cross_domain | reviewer: The only cited passage supports that R&S and Broadcom will demonstrate a CMX500 multi-technology, multi-channel signaling tester … |
| Q0046 | regressed | PASS → FAIL | tool | Wireless Communication; strategic | reviewer: Most Wi‑Fi 7 CMX500/CMP180, CMX500 callbox use-case, certification-lab, and WLAN interworking claims are supported by the provide… |
| Q0051 | regressed | PASS → INSUFFICIENT | tool | Wireless Communication; basic | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0071 | improved | INSUFFICIENT → PASS | direct | Wireless Communication; solution_mapping | was: the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0096 | improved | FAIL → INSUFFICIENT | tool | Wireless Communication; strategic | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0121 | improved | INSUFFICIENT → PASS | direct | Wireless Communication; solution_mapping | was: the harness ran and reported a gap (needs_input) |
| Q0151 | regressed | INSUFFICIENT → FAIL | tool | Wireless Communication; basic | reviewer: The cited passages only identify a ZNA67EXT VNA system and ZNL ordering/frequency options; they do not discuss wireless communica… |
| Q0171 | improved | INSUFFICIENT → PASS | direct | Wireless Communication; solution_mapping | was: the harness ran and reported a gap (needs_input) |
| Q0196 | regressed | PASS → SYSTEM_ERROR | tool → none | Wireless Communication; strategic | turn timed out or HTTP 0 |
| Q0246 | improved | FAIL → PASS | tool | Aerospace / Defense; strategic | was: reviewer: The cited passages support the technical capabilities of CMX500/CMP180 for NTN, FR3/6G, OTA, Wi‑Fi 7, and non-signaling WLAN… |
| Q0251 | regressed | PASS → INSUFFICIENT | tool | Aerospace / Defense; basic | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0271 | regressed | INSUFFICIENT → FAIL | direct | Aerospace / Defense; solution_mapping | reviewer: The cited passages support the Aerospace/Defense market drivers, the NTN test parameters, and the PCB measurement items. However,… |
| Q0296 | improved | FAIL → PASS | tool | Aerospace / Defense; strategic | was: reviewer: The cited passages support technical facts about NTN RF requirements, mobility/handover, beam reporting, satellite re-sync, … |
| Q0321 | improved | INSUFFICIENT → PASS | direct | Aerospace / Defense; solution_mapping | was: the harness ran and reported a gap (needs_input) |
| Q0339 | regressed | PASS → FAIL | direct | Aerospace / Defense; competitive | reviewer: The answer reasonably concludes that the cited evidence does not support a competitor comparison and identifies the existing supp… |
| Q0351 | regressed | INSUFFICIENT → FAIL | tool | Aerospace / Defense; basic | reviewer: The only cited passage merely describes the composition of an R&S ZNA67EXT system and provides no evidence about Aerospace/Defens… |
| Q0371 | improved | INSUFFICIENT → PASS | direct | Aerospace / Defense; solution_mapping | was: the harness ran and reported a gap (needs_input) |
| Q0381 | improved | FAIL → INSUFFICIENT | tool | Aerospace / Defense; cross_domain | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0401 | improved | FAIL → INSUFFICIENT | tool | Automotive; basic | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0411 | improved | INSUFFICIENT → PASS | tool | Automotive; application | was: the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0446 | regressed | PASS → FAIL | tool | Automotive; strategic | reviewer: The cited passages only support general CMX500 capabilities and warranty/service details for CMX500/CMP180; they do not support t… |
| Q0451 | improved | FAIL → INSUFFICIENT | tool | Automotive; basic | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0461 | improved | FAIL → INSUFFICIENT | tool | Automotive; application | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0521 | improved | INSUFFICIENT → PASS | direct | Automotive; solution_mapping | was: the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0546 | regressed | PASS → FAIL | tool | Automotive; strategic | reviewer: The strongest two opportunities—automotive radar echo generation and NG eCall validation—are well supported by the cited passages… |
| Q0561 | regressed | INSUFFICIENT → FAIL | tool | Automotive; application | reviewer: The cited passages show AREG800A is an automotive radar echo generator and mention VNA measurement conditions for IF transfer cha… |
| Q0571 | regressed | PASS → INSUFFICIENT | direct | Automotive; solution_mapping | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0581 | regressed | INSUFFICIENT → FAIL | tool | Automotive; cross_domain | reviewer: The answer correctly notes that the cited passages do not directly link automotive radar technology changes to VNA requirements, … |
| Q0601 | regressed | PASS → FAIL | tool | AI; basic | reviewer: The cited passages support some related wireless-test themes such as RF/protocol/conformance testing, Wi‑Fi signaling, throughput… |
| Q0611 | improved | FAIL → PASS | tool | AI; application | was: reviewer: The passages support that the CMX500 can act as an AI-enabled base station emulator and support application testing for an A… |
| Q0631 | regressed | INSUFFICIENT → FAIL | tool | AI; cross_domain | reviewer: Only passage [1] supports limited CMX500 capabilities: network emulation/measurement, LTE/NR FR1/FR2, NSA/SA, RF parametric testi… |
| Q0661 | regressed | INSUFFICIENT → FAIL | tool | AI; application | reviewer: The passages only support a limited R&S solution mapping around MXO for power rail / multiphase DC / PI and other instruments for… |
| Q0671 | improved | INSUFFICIENT → PASS | direct | AI; solution_mapping | was: the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0689 | improved | INSUFFICIENT → PASS | direct | AI; competitive | was: the harness ran and reported a gap (needs_input) |
| Q0696 | regressed | PASS → INSUFFICIENT | tool | AI; strategic | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0721 | regressed | INSUFFICIENT → FAIL | direct | AI; solution_mapping | reviewer: Most PCBA, switch, PCB, connector/cable, and SMA100B capability statements are backed or clearly caveated, but the power-supply r… |
| Q0739 | regressed | PASS → FAIL | direct | AI; competitive | reviewer: Passages [1], [3], and [10] support that the available materials cover R&S NTN component-test capabilities and that the AI ecosys… |
| Q0771 | improved | FAIL → PASS | direct | AI; solution_mapping | was: reviewer: The passages support only that Qualcomm focuses on AI integration/advanced broadband features and that the R&S ZNL20 has a 5… |
| Q0796 | improved | INSUFFICIENT → PASS | tool | AI; strategic | was: the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0831 | regressed | PASS → FAIL | tool | Semiconductor; cross_domain | reviewer: The cited passages support a narrower conclusion that testers need multi-technology coverage, signaling for realistic Wi-Fi/cellu… |
| Q0896 | improved | FAIL → PASS | tool | Semiconductor; strategic | was: reviewer: The cited passages support the raw technical facts about a MOSFET DC-DC converter, voltage blocking, complementary gate sign… |
| Q0921 | regressed | PASS → INSUFFICIENT | direct | Semiconductor; solution_mapping | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0946 | improved | INSUFFICIENT → PASS | tool | Semiconductor; strategic | was: the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0961 | regressed | PASS → FAIL | tool | Semiconductor; application | reviewer: The cited passages only establish that certain R&S products are Vector Network Analyzers and give some frequency/port details; th… |
| Q0971 | regressed | INSUFFICIENT → FAIL | direct | Semiconductor; solution_mapping | reviewer: The cited passages support the isolated facts about Qualcomm, O-RU test focus areas, and VNA frequency ranges, but they do not es… |
| Q0996 | regressed | PASS → SYSTEM_ERROR | tool → none | Semiconductor; strategic | turn timed out or HTTP 0 |
| Q1021 | improved | FAIL → INSUFFICIENT | tool | foundation; foundation | the harness ran and reported a gap (knowledge_not_grounded) |
| Q1031 | improved | FAIL → INSUFFICIENT | tool | foundation; foundation | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1051 | improved | FAIL → INSUFFICIENT | tool | foundation; foundation | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1061 | regressed | INSUFFICIENT → FAIL | tool | foundation; foundation | reviewer: The cited passages do not define non-signaling testers or discuss product-related measurement decisions; they only mention PRS/nu… |
| Q1071 | improved | FAIL → INSUFFICIENT | tool | foundation; foundation | the harness ran and reported a gap (knowledge_not_grounded) |

