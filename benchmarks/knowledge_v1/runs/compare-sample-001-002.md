# knowledge_v1 run comparison

Generated offline by `benchmarks/knowledge_v1/compare.py` from the stored `result.json` files.

| Run | Started | Commit | Grader | Questions | Compared | Left out |
|---|---|---|---|---|---|---|
| sample-001 | 2026-10-07T07:51:15+00:00 | `ab9cb3e` | 1.1 | 110 | 110 | 0 |
| sample-002 | 2026-10-07T09:32:40+00:00 | `c64a724` | 1.1 | 110 | 110 | 0 |

## Status

| Status | sample-001 | sample-002 |
|---|---|---|
| **acceptable** | **64 (58%)** | **75 (68%)** |
| PASS | 31 | 34 |
| INSUFFICIENT_KNOWLEDGE | 33 | 41 |
| FAIL | 38 | 35 |
| NEEDS_HUMAN_REVIEW | 0 | 0 |
| SYSTEM_ERROR | 8 | 0 |

## Route × status

| Run | Route | Questions | PASS | INSUFFICIENT | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR | PASS rate |
|---|---|---|---|---|---|---|---|---|
| sample-001 | direct | 34 | 22 | 10 | 2 | 0 | 0 | 65% |
| sample-001 | tool | 58 | 9 | 23 | 18 | 0 | 8 | 16% |
| sample-001 | none | 18 | 0 | 0 | 18 | 0 | 0 | 0% |
| sample-002 | direct | 34 | 19 | 13 | 2 | 0 | 0 | 56% |
| sample-002 | tool | 76 | 15 | 28 | 33 | 0 | 0 | 20% |
| sample-002 | none | 0 | 0 | 0 | 0 | 0 | 0 | – |

## By market

| market | n | sample-001 acc / PASS | sample-002 acc / PASS | Δ acc |
|---|---|---|---|---|
| AI | 20 | 14 / 4 | 11 / 5 | -3 |
| Aerospace / Defense | 20 | 10 / 5 | 12 / 5 | +2 |
| Automotive | 20 | 11 / 6 | 15 / 7 | +4 |
| Semiconductor | 20 | 11 / 7 | 15 / 8 | +4 |
| Wireless Communication | 20 | 12 / 7 | 16 / 9 | +4 |
| foundation | 10 | 6 / 2 | 6 / 0 | +0 |

## By product family

| product family | n | sample-001 acc / PASS | sample-002 acc / PASS | Δ acc |
|---|---|---|---|---|
| Cross-Knowledge Reasoning | 1 | 1 / 0 | 1 / 0 | +0 |
| High-Speed / Signal Integrity | 2 | 0 / 0 | 1 / 0 | +1 |
| Instrument & Measurement Principles | 1 | 0 / 0 | 1 / 0 | +1 |
| Oscilloscope | 25 | 13 / 4 | 18 / 5 | +5 |
| RF / Measurement Fundamentals | 2 | 2 / 0 | 2 / 0 | +0 |
| Signal Generator / Signal Analyzer | 25 | 16 / 6 | 14 / 8 | -2 |
| Signaling / Non-signaling Tester | 25 | 13 / 10 | 17 / 12 | +4 |
| Technical Document / Paper Understanding | 2 | 2 / 1 | 1 / 0 | -1 |
| Vector Network Analyzer | 25 | 16 / 9 | 20 / 9 | +4 |
| Wireless Fundamentals | 2 | 1 / 1 | 0 / 0 | -1 |

## By question type

| question type | n | sample-001 acc / PASS | sample-002 acc / PASS | Δ acc |
|---|---|---|---|---|
| application | 16 | 4 / 0 | 8 / 2 | +4 |
| basic | 16 | 6 / 3 | 9 / 5 | +3 |
| competitive | 17 | 17 / 17 | 16 / 15 | -1 |
| cross_domain | 17 | 6 / 0 | 11 / 2 | +5 |
| foundation | 10 | 6 / 2 | 6 / 0 | +0 |
| solution_mapping | 17 | 15 / 5 | 16 / 4 | +1 |
| strategic | 17 | 10 / 4 | 9 / 6 | -1 |

## By difficulty

| difficulty | n | sample-001 acc / PASS | sample-002 acc / PASS | Δ acc |
|---|---|---|---|---|
| L1 | 16 | 6 / 3 | 9 / 5 | +3 |
| L2 | 16 | 4 / 0 | 8 / 2 | +4 |
| L3 | 17 | 15 / 5 | 16 / 4 | +1 |
| L4 | 34 | 23 / 17 | 27 / 17 | +4 |
| L5 | 17 | 10 / 4 | 9 / 6 | -1 |
| foundation | 10 | 6 / 2 | 6 / 0 | +0 |

## Gap types

| Gap | sample-001 | sample-002 |
|---|---|---|
| EXECUTION_GAP | 26 | 0 |
| REASONING_GAP | 20 | 35 |
| SOURCE_GAP or RETRIEVAL_GAP | 33 | 41 |

## Reviewer verdicts

Over answers the reviewer read (citations all verified); overreach = at least one claim listed as going beyond the passages.

| Run | Reviewed | Verdict given | Supported | Reasonable | Confidence high / medium / low | With overreach | Overreach items per answer |
|---|---|---|---|---|---|---|---|
| sample-001 | 51 | 51 | 32 (63%) | 34 (67%) | 44 / 7 / 0 | 49 (96%) | 4.7 |
| sample-002 | 69 | 69 | 35 (51%) | 38 (55%) | 62 / 7 / 0 | 66 (96%) | 5.5 |

## Latency (seconds)

| Run | Route | n | median | p90 |
|---|---|---|---|---|
| sample-001 | direct | 34 | 99.8 | 137.1 |
| sample-001 | tool | 58 | 82.5 | 226.2 |
| sample-001 | none | 18 | 15.6 | 26.2 |
| sample-001 | all | 110 | 86.8 | 147.8 |
| sample-002 | direct | 34 | 81.2 | 125.1 |
| sample-002 | tool | 76 | 61.6 | 103.8 |
| sample-002 | all | 110 | 66.3 | 113.5 |

## Citations

Checked answers are those whose citations were checked against the Vault.

| Run | Checked answers | Citations | Per checked answer | Verified in the Vault |
|---|---|---|---|---|
| sample-001 | 51 | 295 | 5.8 | 295 (100%) |
| sample-002 | 69 | 404 | 5.9 | 404 (100%) |

## Transitions sample-001 → sample-002

Improved 26, regressed 16, unchanged 62, changed at the same rank 6 (of 110).

| Question | Change | Old → new | Route | Tags | Reason (new run) |
|---|---|---|---|---|---|
| Q0011 | changed, same rank | SYSTEM_ERROR → FAIL | tool | Wireless Communication; application | reviewer: The cited passage supports only that CMX500 is a Wi‑Fi 7 multi-channel signaling tester used during WLAN development for RF TX/RX… |
| Q0021 | regressed | PASS → INSUFFICIENT | direct | Wireless Communication; solution_mapping | the harness ran and reported a gap (needs_input) |
| Q0031 | improved | FAIL → PASS | tool | Wireless Communication; cross_domain | was: reviewer: The only provided passage supports that R&S positions CMP180/200/CMW100 for non-signaling factory-line capability and mentio… |
| Q0046 | improved | SYSTEM_ERROR → PASS | tool | Wireless Communication; strategic | was: Knowledge did not complete (knowledge_model_failed) |
| Q0096 | regressed | INSUFFICIENT → FAIL | tool | Wireless Communication; strategic | reviewer: The cited passages support some underlying wireless-market facts, such as O-RU funding, NTN regulatory adaptation, NTN UE capabil… |
| Q0111 | improved | FAIL → PASS | none → tool | Wireless Communication; application | was: answered without using Knowledge |
| Q0131 | changed, same rank | SYSTEM_ERROR → FAIL | tool | Wireless Communication; cross_domain | reviewer: The passages support wider bandwidth requirements, 480/500 MHz future-proofing, 4096QAM/MLO as Wi-Fi 7/8 features, multiple RF ch… |
| Q0151 | improved | FAIL → INSUFFICIENT | none → tool | Wireless Communication; basic | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0181 | improved | FAIL → INSUFFICIENT | none → tool | Wireless Communication; cross_domain | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0246 | changed, same rank | SYSTEM_ERROR → FAIL | tool | Aerospace / Defense; strategic | reviewer: The cited passages support the technical capabilities of CMX500/CMP180 for NTN, FR3/6G, OTA, Wi‑Fi 7, and non-signaling WLAN prod… |
| Q0251 | improved | FAIL → PASS | tool | Aerospace / Defense; basic | was: reviewer: Most RF-related points are supported by the cited passages, especially satellite RF lifecycle testing, wideband/pulsed signa… |
| Q0261 | improved | FAIL → INSUFFICIENT | none → tool | Aerospace / Defense; application | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0281 | improved | FAIL → INSUFFICIENT | none → tool | Aerospace / Defense; cross_domain | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0331 | regressed | INSUFFICIENT → FAIL | tool | Aerospace / Defense; cross_domain | reviewer: The cited passages support only a few limited points: wide modulation bandwidth enabling complex pulsed A&D signals, low-SNR wide… |
| Q0351 | improved | FAIL → INSUFFICIENT | none → tool | Aerospace / Defense; basic | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0396 | regressed | PASS → FAIL | tool | Aerospace / Defense; strategic | reviewer: The cited passages support that ZNA is used in a satellite payload group-delay comparison and that ZNA67EXT has 110 GHz and multi… |
| Q0401 | changed, same rank | SYSTEM_ERROR → FAIL | tool | Automotive; basic | reviewer: The cited passages support several general R&S capabilities—LTE/5G NR, NTN, channel emulation, OTA chambers, WLAN/cellular covera… |
| Q0411 | improved | FAIL → INSUFFICIENT | tool | Automotive; application | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0481 | improved | FAIL → INSUFFICIENT | tool | Automotive; cross_domain | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0511 | regressed | INSUFFICIENT → FAIL | tool | Automotive; application | reviewer: The cited passages support that AREG800A is an automotive radar echo generator, that signal generators can generate CW/interferin… |
| Q0521 | improved | FAIL → INSUFFICIENT | direct | Automotive; solution_mapping | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0546 | improved | INSUFFICIENT → PASS | tool | Automotive; strategic | was: the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0561 | improved | FAIL → INSUFFICIENT | none → tool | Automotive; application | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0581 | improved | FAIL → INSUFFICIENT | none → tool | Automotive; cross_domain | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0601 | improved | FAIL → PASS | none → tool | AI; basic | was: answered without using Knowledge |
| Q0611 | changed, same rank | SYSTEM_ERROR → FAIL | tool | AI; application | reviewer: The passages support that the CMX500 can act as an AI-enabled base station emulator and support application testing for an AI-ena… |
| Q0681 | regressed | INSUFFICIENT → FAIL | tool | AI; cross_domain | reviewer: The cited passages support that AI/data-center technologies involve 224 Gb/s PAM4 connectivity, optical engines, high-speed/high-… |
| Q0689 | regressed | PASS → INSUFFICIENT | direct | AI; competitive | the harness ran and reported a gap (needs_input) |
| Q0696 | improved | FAIL → PASS | tool | AI; strategic | was: reviewer: The cited passages strongly support high-speed AI/data-center interconnect, connector, memory, and signal-integrity applicat… |
| Q0731 | regressed | INSUFFICIENT → FAIL | tool | AI; cross_domain | reviewer: The passages support the core link between AI data-center 800G/1.6T optics/interconnects and RF-style high-speed signal-integrity… |
| Q0746 | regressed | INSUFFICIENT → FAIL | tool | AI; strategic | reviewer: The answer is directionally reasonable: the passages support AI data-center chips involving GPU/ASIC/switch/PCIe/SerDes, high-spe… |
| Q0751 | regressed | INSUFFICIENT → FAIL | tool | AI; basic | reviewer: The passages support only broad AI/data-center needs such as high-speed/high-density interconnects, signal integrity, reliable tr… |
| Q0761 | regressed | INSUFFICIENT → FAIL | tool | AI; application | reviewer: The cited passages only show a data-center BBU/power context and that an R&S ZNA VNA can be part of a network-analyzer group-dela… |
| Q0831 | improved | FAIL → PASS | tool | Semiconductor; cross_domain | was: reviewer: The cited passages support a high-level inference that testers are adding multi-technology/multi-channel signaling, Wi‑Fi 7/… |
| Q0846 | regressed | PASS → FAIL | tool | Semiconductor; strategic | reviewer: The cited passages support several R&S tester capabilities and use cases, including non-signaling production test, CMX500 RF/prot… |
| Q0861 | improved | FAIL → INSUFFICIENT | none → tool | Semiconductor; application | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0881 | improved | FAIL → INSUFFICIENT | none → tool | Semiconductor; cross_domain | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0921 | improved | INSUFFICIENT → PASS | direct | Semiconductor; solution_mapping | was: the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0931 | improved | FAIL → INSUFFICIENT | tool | Semiconductor; cross_domain | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0939 | regressed | PASS → FAIL | direct | Semiconductor; competitive | reviewer: Most requirements are fairly grounded in passages about using formal specs, checking competitor official/third-party evidence, tr… |
| Q0961 | improved | FAIL → PASS | none → tool | Semiconductor; application | was: answered without using Knowledge |
| Q0971 | regressed | PASS → INSUFFICIENT | direct | Semiconductor; solution_mapping | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0996 | improved | SYSTEM_ERROR → PASS | tool | Semiconductor; strategic | was: Knowledge did not complete (knowledge_model_failed) |
| Q1021 | regressed | PASS → FAIL | tool | foundation; foundation | reviewer: The cited passages support that Spectrum vs 5G NR modes expose different measurements, that OBW and transmitter spurious emission… |
| Q1041 | improved | FAIL → INSUFFICIENT | tool | foundation; foundation | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1051 | changed, same rank | SYSTEM_ERROR → FAIL | tool | foundation; foundation | reviewer: The cited passages do not define PCIe or discuss PCIe-specific measurement decisions; they only support general points about R&S … |
| Q1061 | improved | FAIL → INSUFFICIENT | tool | foundation; foundation | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1071 | regressed | PASS → FAIL | tool | foundation; foundation | reviewer: The cited passages support the isolated facts about XLAPI/SCPI, DMRS-based phase measurement, and PRS being bound to numerology, … |

