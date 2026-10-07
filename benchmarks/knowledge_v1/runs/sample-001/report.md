# knowledge_v1 — sample-001

Run at 2026-10-07T07:51:15+00:00, AEP commit `ab9cb3ea62e9325daa6b729af8dfb2ebba80c341`, grader 1.1, question bank sha256 `f5275373dad7…`, set `sample`.

**64 of 110 acceptable** (PASS 31, INSUFFICIENT_KNOWLEDGE 33); FAIL 38, NEEDS_HUMAN_REVIEW 0, SYSTEM_ERROR 8

## By market

| market | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| AI | 4 | 10 | 5 | 0 | 1 |
| Aerospace / Defense | 5 | 5 | 9 | 0 | 1 |
| Automotive | 6 | 5 | 8 | 0 | 1 |
| Semiconductor | 7 | 4 | 8 | 0 | 1 |
| Wireless Communication | 7 | 5 | 5 | 0 | 3 |
| foundation | 2 | 4 | 3 | 0 | 1 |

## By product

| product | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| Cross-Knowledge Reasoning | 0 | 1 | 0 | 0 | 0 |
| High-Speed / Signal Integrity | 0 | 0 | 1 | 0 | 1 |
| Instrument & Measurement Principles | 0 | 0 | 1 | 0 | 0 |
| Oscilloscope | 4 | 9 | 12 | 0 | 0 |
| RF / Measurement Fundamentals | 0 | 2 | 0 | 0 | 0 |
| Signal Generator / Signal Analyzer | 6 | 10 | 8 | 0 | 1 |
| Signaling / Non-signaling Tester | 10 | 3 | 7 | 0 | 5 |
| Technical Document / Paper Understanding | 1 | 1 | 0 | 0 | 0 |
| Vector Network Analyzer | 9 | 7 | 8 | 0 | 1 |
| Wireless Fundamentals | 1 | 0 | 1 | 0 | 0 |

## By type

| type | PASS | INSUFFICIENT_KNOWLEDGE | FAIL | NEEDS_HUMAN_REVIEW | SYSTEM_ERROR |
|---|---|---|---|---|---|
| application | 0 | 4 | 10 | 0 | 2 |
| basic | 3 | 3 | 9 | 0 | 1 |
| competitive | 17 | 0 | 0 | 0 | 0 |
| cross_domain | 0 | 6 | 10 | 0 | 1 |
| foundation | 2 | 4 | 3 | 0 | 1 |
| solution_mapping | 5 | 10 | 2 | 0 | 0 |
| strategic | 4 | 6 | 4 | 0 | 3 |

## Harness

Routes: direct 34, none 18, tool 58

Gaps: SOURCE_GAP or RETRIEVAL_GAP 33, EXECUTION_GAP 26, REASONING_GAP 20

## Not passed

| Question | Status | Gap | Why |
|---|---|---|---|
| Q0011 | SYSTEM_ERROR | EXECUTION_GAP | Knowledge did not complete (knowledge_model_failed) |
| Q0031 | FAIL | REASONING_GAP | reviewer: The only provided passage supports that R&S positions CMP180/200/CMW100 for non-signaling factory-line capability and mentions asking about integrated Wi-Fi signaling for 6/6E/7. It does not |
| Q0046 | SYSTEM_ERROR | EXECUTION_GAP | Knowledge did not complete (knowledge_model_failed) |
| Q0061 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0071 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0081 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0096 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0111 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0121 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0131 | SYSTEM_ERROR | EXECUTION_GAP | Knowledge did not complete (knowledge_model_failed) |
| Q0151 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0171 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0181 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0211 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0231 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0246 | SYSTEM_ERROR | EXECUTION_GAP | Knowledge did not complete (knowledge_model_failed) |
| Q0251 | FAIL | REASONING_GAP | reviewer: Most RF-related points are supported by the cited passages, especially satellite RF lifecycle testing, wideband/pulsed signal generation, and high-power RF component verification. However, t |
| Q0261 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0271 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0281 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0296 | FAIL | REASONING_GAP | reviewer: The cited passages support that NTN involves UE measurements, propagation-delay compensation, beam reporting, and that DC-DC converters involve gate signals, phase shift, and duty cycle. How |
| Q0301 | FAIL | REASONING_GAP | reviewer: The passages directly support wide bandwidth for complex pulsed A&D signals, and mention GNSS/avionics options and NTN channel-emulation features. However, several listed 'most important' A& |
| Q0311 | FAIL | REASONING_GAP | reviewer: The cited passages support only the general idea that signal generators can create an interfering signal and signal/spectrum analyzers are used for signal analysis/test cases. They do not su |
| Q0321 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0331 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0351 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0371 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0381 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0401 | SYSTEM_ERROR | EXECUTION_GAP | Knowledge did not complete (knowledge_model_failed) |
| Q0411 | FAIL | REASONING_GAP | reviewer: The only cited passage supports that R&S AREG800A is associated with automotive radar echo generation and related radar/HIL concepts. It does not provide evidence about signaling or non-sign |
| Q0431 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0451 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0461 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0481 | FAIL | REASONING_GAP | reviewer: The cited passage only supports that the FSW-B2071 option records I/Q data using supported R&S RTO oscilloscopes with the RTO-B4 option to obtain specified performance. The answer makes broa |
| Q0496 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0501 | FAIL | REASONING_GAP | reviewer: The cited passages support general signal-generator capabilities such as 5G/LTE standards, NTN channel emulation, bandwidth, frequency range, signal quality, complex signals, and GNSS option |
| Q0511 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0521 | FAIL | REASONING_GAP | reviewer: Most listed factual snippets are supported by the cited passages, but the answer does not actually map an Automotive market requirement to measurable parameters and then to required Signal G |
| Q0546 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0551 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0561 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0581 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0601 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0611 | SYSTEM_ERROR | EXECUTION_GAP | Knowledge did not complete (knowledge_model_failed) |
| Q0631 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0646 | FAIL | REASONING_GAP | reviewer: Several core tester capabilities are supported, especially CMX500 AI-enabled radio validation, AI scripting, Wi‑Fi 7/8 signaling, and CMP/WMT non-signaling production features. However, the  |
| Q0661 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0671 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0681 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0696 | FAIL | REASONING_GAP | reviewer: The cited passages strongly support high-speed AI/data-center interconnect, connector, memory, and signal-integrity application demand, and the answer honestly caveats the lack of oscillosco |
| Q0701 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0721 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0731 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0746 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0751 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0761 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_not_grounded) |
| Q0771 | FAIL | REASONING_GAP | reviewer: The cited passages support Qualcomm's AI/advanced broadband focus and the two VNA frequency ranges, but they do not establish a chain from that AI market requirement to RF validation, freque |
| Q0796 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0811 | FAIL | REASONING_GAP | reviewer: The cited passages support that the CMX500 is a signaling tester for end-to-end signaling, RF conformance, protocol validation, and real-world signaling-mode RF TX/RX measurements, and that  |
| Q0831 | FAIL | REASONING_GAP | reviewer: The cited passages support a high-level inference that testers are adding multi-technology/multi-channel signaling, Wi‑Fi 7/8 capabilities, 480 MHz waveform support, OTA chamber integration, |
| Q0861 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0871 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (needs_input) |
| Q0881 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0896 | FAIL | REASONING_GAP | reviewer: The O-RU/RTO6 opportunity is directly supported by passage 3. However, the other two main opportunities infer oscilloscope use from semiconductor or IP subject matter without passage evidenc |
| Q0901 | FAIL | REASONING_GAP | reviewer: The cited passages support only a few generic generator capabilities: high output power, wide modulation bandwidth, excellent signal quality, frequency range, per-carrier settings, and wavef |
| Q0921 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0931 | FAIL | REASONING_GAP | reviewer: The cited passages support only limited points: some instruments are used in wireless or payload testing, one integration with chamber/software exists, a questionnaire mentions workflow pain |
| Q0946 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0951 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q0961 | FAIL | EXECUTION_GAP | answered without using Knowledge |
| Q0996 | SYSTEM_ERROR | EXECUTION_GAP | Knowledge did not complete (knowledge_model_failed) |
| Q1001 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1011 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1031 | FAIL | REASONING_GAP | reviewer: The passages support only that PER is a named measurement/feature in CMP180 and PVT360A and that CMX500 has WLAN signaling PER settings/results. They do not define packet error rate or suppo |
| Q1041 | FAIL | REASONING_GAP | reviewer: The cited passages only state that different operation modes, such as Spectrum or 5G NR, provide different measurements for 5G NR base-station transmitter tests, with Spectrum mode used for  |
| Q1051 | SYSTEM_ERROR | EXECUTION_GAP | Knowledge did not complete (knowledge_model_failed) |
| Q1061 | FAIL | REASONING_GAP | reviewer: The passages support that CMX500 is a signaling tester used for protocol/performance/RF, conformance, fading/channel emulation, and that CMP180 verifies a 480 MHz waveform in loopback mode f |
| Q1081 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
| Q1091 | INSUFFICIENT_KNOWLEDGE | SOURCE_GAP or RETRIEVAL_GAP | the harness ran and reported a gap (knowledge_insufficient_evidence) |
