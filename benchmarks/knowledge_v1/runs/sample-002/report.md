# knowledge_v1 — sample-002

Run at 2026-10-07T09:32:40+00:00, AEP commit `c64a724c4040cf55163e91e0c57711120561e172`, grader 1.1, question bank sha256 `f5275373dad7…`, set `sample`.

**75 of 110 acceptable** (PASS 34, INSUFFICIENT_KNOWLEDGE 41); FAIL 35, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 0

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 5 | 6 | 9 | 0 | 0 |
| Aerospace / Defense | 5 | 7 | 8 | 0 | 0 |
| Automotive | 7 | 8 | 5 | 0 | 0 |
| Semiconductor | 8 | 7 | 5 | 0 | 0 |
| Wireless Communication | 9 | 7 | 4 | 0 | 0 |
| foundation | 0 | 6 | 4 | 0 | 0 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 1 | 0 | 0 | 0 |
| High-Speed / Signal Integrity | 0 | 1 | 1 | 0 | 0 |
| Instrument & Measurement Principles | 0 | 1 | 0 | 0 | 0 |
| Oscilloscope | 5 | 13 | 7 | 0 | 0 |
| RF / Measurement Fundamentals | 0 | 2 | 0 | 0 | 0 |
| Signal Generator / Signal Analyzer | 8 | 6 | 11 | 0 | 0 |
| Signaling / Non-signaling Tester | 12 | 5 | 8 | 0 | 0 |
| Technical Document / Paper Understanding | 0 | 1 | 1 | 0 | 0 |
| Vector Network Analyzer | 9 | 11 | 5 | 0 | 0 |
| Wireless Fundamentals | 0 | 0 | 2 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 2 | 6 | 8 | 0 | 0 |
| basic | 5 | 4 | 7 | 0 | 0 |
| competitive | 15 | 1 | 1 | 0 | 0 |
| cross_domain | 2 | 9 | 6 | 0 | 0 |
| foundation | 0 | 6 | 4 | 0 | 0 |
| solution_mapping | 4 | 12 | 1 | 0 | 0 |
| strategic | 6 | 3 | 8 | 0 | 0 |

## Harness

Routes: direct 34, tool 76

Gaps: SOURCE_GAP or RETRIEVAL_GAP 41, REASONING_GAP 35

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0011 | FAIL | REASONING_GAP | reviewer: The cited passage supports only that CMX500 is a Wi‑Fi 7 multi-channel signaling tester used during WLAN development for RF TX/RX, antenna, MLO, and IP-related tests under real-world signali |
| Q0021 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0061 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0071 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0081 | FAIL | REASONING_GAP | reviewer: The passages support some Wi-Fi 7 characteristics such as 320 MHz bandwidth, 16 spatial streams, 4096QAM, low latency, and a possible 480 MHz Wi-Fi 8 waveform, but they provide no oscillosco |
| Q0096 | FAIL | REASONING_GAP | reviewer: The cited passages support some underlying wireless-market facts, such as O-RU funding, NTN regulatory adaptation, NTN UE capabilities, beam reporting, satellite orbital/communication notes, |
| Q0121 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0131 | FAIL | REASONING_GAP | reviewer: The passages support wider bandwidth requirements, 480/500 MHz future-proofing, 4096QAM/MLO as Wi-Fi 7/8 features, multiple RF chains for MLO, and signaling vs non-signaling test contexts. H |
| Q0151 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0171 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0181 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0211 | FAIL | REASONING_GAP | reviewer: The cited passages support that CMX500/CMP180 are wireless communication testers for Wi-Fi, cellular, NTN, OTA, IP/E2E, fading/channel, and waveform loopback testing. They do not discuss rad |
| Q0231 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0246 | FAIL | REASONING_GAP | reviewer: The cited passages support the technical capabilities of CMX500/CMP180 for NTN, FR3/6G, OTA, Wi‑Fi 7, and non-signaling WLAN production test, and the answer correctly notes that no passage d |
| Q0261 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0271 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0281 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0296 | FAIL | REASONING_GAP | reviewer: The cited passages support technical facts about NTN RF requirements, mobility/handover, beam reporting, satellite re-sync, and a DC-DC converter, but they do not mention oscilloscopes, aero |
| Q0301 | FAIL | REASONING_GAP | reviewer: The passages support that wide bandwidth enables complex pulsed signals in A&D and list several general signal-generator characteristics or waveform playback limits. They do not establish th |
| Q0311 | FAIL | REASONING_GAP | reviewer: The passages support only general RF roles: signal generation/analysis, Doppler/fading in a 5G NTN setup, and CW interference in 5G receiver tests. The answer honestly notes the lack of rada |
| Q0321 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0331 | FAIL | REASONING_GAP | reviewer: The cited passages support only a few limited points: wide modulation bandwidth enabling complex pulsed A&D signals, low-SNR wideband measurement techniques, and 1 ns group-delay characteriz |
| Q0351 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0371 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0381 | FAIL | REASONING_GAP | reviewer: The cited passages support that certain VNA features exist, such as pulsed measurements, time-domain analysis, mixer measurements, sensitivity, dynamic range, receiver bandwidth, and de-embe |
| Q0396 | FAIL | REASONING_GAP | reviewer: The cited passages support that ZNA is used in a satellite payload group-delay comparison and that ZNA67EXT has 110 GHz and multiport/external-test-set capabilities. They do not support the  |
| Q0401 | FAIL | REASONING_GAP | reviewer: The cited passages support several general R&S capabilities—LTE/5G NR, NTN, channel emulation, OTA chambers, WLAN/cellular coverage—but only directly connect automotive to interest in 5G NTN |
| Q0411 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0431 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0451 | FAIL | REASONING_GAP | reviewer: The passages support a generic high-speed PCB/PCBA SI flow with IL, crosstalk, eye diagram, TDR impedance, stackup planning, and TL calculation, plus separate facts about NTN interest from a |
| Q0461 | FAIL | REASONING_GAP | reviewer: The cited passage only identifies the R&S AREG800A page and related automotive-radar concepts; it does not mention oscilloscopes, workflow stages, lifecycle coverage, EMC/connectivity, or de |
| Q0481 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0496 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0501 | FAIL | REASONING_GAP | reviewer: The cited passages support several generic signal-generator capabilities and one NTN passage mentioning automotive interest, but they do not establish a ranked or automotive-specific set of  |
| Q0511 | FAIL | REASONING_GAP | reviewer: The cited passages support that AREG800A is an automotive radar echo generator, that signal generators can generate CW/interfering signals in another RF test context, and that a signal analy |
| Q0521 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0551 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0561 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0581 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0611 | FAIL | REASONING_GAP | reviewer: The passages support that the CMX500 can act as an AI-enabled base station emulator and support application testing for an AI-enabled wireless prototype, and that a virtual tester workflow s |
| Q0631 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0646 | FAIL | REASONING_GAP | reviewer: The CMX500 GenAI UX, AI-enabled base-station/CSI, application testing, and AI scripting assistant opportunities are well supported by the cited passages. However, several listed 'AI' opportu |
| Q0661 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0671 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0681 | FAIL | REASONING_GAP | reviewer: The cited passages support that AI/data-center technologies involve 224 Gb/s PAM4 connectivity, optical engines, high-speed/high-frequency PCBs, crosstalk concerns, and PCB fiber-weave effec |
| Q0689 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0701 | FAIL | REASONING_GAP | reviewer: Passage 1 supports waveform-file generation and four hardware-limiting properties: frequency range, bandwidth, ARB memory, and sample clock rate; passage 2 supports integration of specific i |
| Q0721 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0731 | FAIL | REASONING_GAP | reviewer: The passages support the core link between AI data-center 800G/1.6T optics/interconnects and RF-style high-speed signal-integrity concerns such as mismatch, return loss, common-mode noise, c |
| Q0746 | FAIL | REASONING_GAP | reviewer: The answer is directionally reasonable: the passages support AI data-center chips involving GPU/ASIC/switch/PCIe/SerDes, high-speed PCB/RF-like signal-path concerns, and relevant generator/a |
| Q0751 | FAIL | REASONING_GAP | reviewer: The passages support only broad AI/data-center needs such as high-speed/high-density interconnects, signal integrity, reliable transmission, low latency, and 224 Gb/s PAM4; they do not menti |
| Q0761 | FAIL | REASONING_GAP | reviewer: The cited passages only show a data-center BBU/power context and that an R&S ZNA VNA can be part of a network-analyzer group-delay measurement setup; they do not connect VNAs to AI data-cent |
| Q0771 | FAIL | REASONING_GAP | reviewer: The passages support only that Qualcomm focuses on AI integration/advanced broadband features and that the R&S ZNL20 has a 5 kHz to 20 GHz VNA frequency range with specified ports. They do n |
| Q0796 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0811 | FAIL | REASONING_GAP | reviewer: The cited passages support CMX500 use for real-world signaling-mode Wi-Fi/cellular-style testing, CMP180 waveform verification in loopback for R&D/production, and VNA use for RFIC/SoC bare-b |
| Q0846 | FAIL | REASONING_GAP | reviewer: The cited passages support several R&S tester capabilities and use cases, including non-signaling production test, CMX500 RF/protocol validation, OTA, SAR, and Wi-Fi/RedCap support. However, |
| Q0861 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0871 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0881 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0896 | FAIL | REASONING_GAP | reviewer: The cited passages support the raw technical facts about a MOSFET DC-DC converter, voltage blocking, complementary gate signals, phase shift, and duty-cycle range. They do not directly suppo |
| Q0901 | FAIL | REASONING_GAP | reviewer: The cited passages support several general signal-generation capabilities as relevant or as product performance characteristics, but they do not mention Semiconductor applications or establi |
| Q0931 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0939 | FAIL | REASONING_GAP | reviewer: Most requirements are fairly grounded in passages about using formal specs, checking competitor official/third-party evidence, treating battle cards/PR as non-binding, and requiring full tes |
| Q0946 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0951 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0971 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1001 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1011 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1021 | FAIL | REASONING_GAP | reviewer: The cited passages support that Spectrum vs 5G NR modes expose different measurements, that OBW and transmitter spurious emissions are Spectrum-mode measurements, that PRS must not overlap S |
| Q1031 | FAIL | REASONING_GAP | reviewer: The answer makes no factual claims about packet error rate, so it does not go beyond or contradict the passages. However, it does not answer the question or clearly explain that the cited ev |
| Q1041 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1051 | FAIL | REASONING_GAP | reviewer: The cited passages do not define PCIe or discuss PCIe-specific measurement decisions; they only support general points about R&S options, signal integrity in a different context, ordering gu |
| Q1061 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1071 | FAIL | REASONING_GAP | reviewer: The cited passages support the isolated facts about XLAPI/SCPI, DMRS-based phase measurement, and PRS being bound to numerology, but they do not define “measurement method” or establish that |
| Q1081 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1091 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
