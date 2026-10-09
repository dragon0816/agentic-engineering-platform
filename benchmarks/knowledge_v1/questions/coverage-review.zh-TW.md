# knowledge_v1 涵蓋率選題（審閱用）

由 `benchmarks/knowledge_v1/coverage.py` 產生（2026-10-09）。目標是用最少題目涵蓋題庫的各個面向，而不是追求題數。選法：每次挑「能補上最多尚未涵蓋面向」的題目；同分時優先選以前跑過的題目（方便前後比較），再依題號。

## 兩個層級

- **核心層（core）：36 題**。涵蓋：20 個市場×產品格、每個題型在每個市場與每個產品都出現、每個題型×難度組合、6 個基礎知識類別，以及過去三次樣本出現過的每一種結果（PASS / INSUFFICIENT / FAIL 與缺口類型、直接或工具路徑）。
- **意圖層（intents）：228 題**。在核心層之上再涵蓋全部 127 種題目模板（同一題只換市場/產品名稱算一種）與 100 個基礎主題。

建議先用**核心層**請 Claude Code 產生參考答案並比較；若核心層結果穩定，再決定是否擴到意圖層。

過去跑過的題目共 110 題；核心層中有 35 題跑過，可直接前後比較。

## 核心層題目

| 題號 | 市場 / 產品（或基礎類別） | 題型 / 難度 | 過去結果 | 題目 | 涵蓋原因 |
|---|---|---|---|---|---|
| Q0011 | Wireless Communication / Signaling / Non-signaling Tester | application / L2 | FAIL／REASONING_GAP／tool | For a Wireless Communication use case involving Wi-Fi 7/8, where would Signaling / Non-signaling Tester fit in the test workflow? | 5 項（cell；outcome；type-difficulty；type-market；type-product） |
| Q0039 | Wireless Communication / Signaling / Non-signaling Tester | competitive / L4 | PASS／-／direct | What evidence is required to compare our Signaling / Non-signaling Tester solution with a competitor for Wireless Communication without making unsupported claims? | 1 項（type-market） |
| Q0051 | Wireless Communication / Oscilloscope | basic / L1 | INSUFFICIENT_KNOWLEDGE／SOURCE_GAP or RETRIEVAL_GAP／tool | What are the most important signal integrity capabilities for applications in Wireless Communication? | 5 項（cell；outcome；type-difficulty；type-market；type-product） |
| Q0121 | Wireless Communication / Signal Generator / Signal Analyzer | solution_mapping / L3 | PASS／-／direct | Map the chain from a Wireless Communication market requirement to a measurable parameter and then to a required capability of Signal Generator / Signal Analyzer. | 5 項（cell；outcome；type-difficulty；type-market；type-product） |
| Q0131 | Wireless Communication / Signal Generator / Signal Analyzer | cross_domain / L4 | FAIL／REASONING_GAP／tool | How do changes in Wi-Fi 7/8 technology affect the measurement capability required from Signal Generator / Signal Analyzer? | 2 項（type-market；type-product） |
| Q0196 | Wireless Communication / Vector Network Analyzer | strategic / L5 | SYSTEM_ERROR／SYSTEM_ERROR／none | Based on current vault evidence, what are the strongest opportunities for Vector Network Analyzer in Wireless Communication, and what evidence supports each opportunity? | 5 項（cell；outcome；type-difficulty；type-market；type-product） |
| Q0211 | Aerospace / Defense / Signaling / Non-signaling Tester | application / L2 | FAIL／REASONING_GAP／tool | For a Aerospace / Defense use case involving radar, where would Signaling / Non-signaling Tester fit in the test workflow? | 1 項（type-market） |
| Q0221 | Aerospace / Defense / Signaling / Non-signaling Tester | solution_mapping / L3 | PASS／-／direct | Map the chain from a Aerospace / Defense market requirement to a measurable parameter and then to a required capability of Signaling / Non-signaling Tester. | 2 項（type-market；type-product） |
| Q0231 | Aerospace / Defense / Signaling / Non-signaling Tester | cross_domain / L4 | INSUFFICIENT_KNOWLEDGE／SOURCE_GAP or RETRIEVAL_GAP／tool | How do changes in radar technology affect the measurement capability required from Signaling / Non-signaling Tester? | 4 項（cell；type-difficulty；type-market；type-product） |
| Q0296 | Aerospace / Defense / Oscilloscope | strategic / L5 | PASS／-／tool | Based on current vault evidence, what are the strongest opportunities for Oscilloscope in Aerospace / Defense, and what evidence supports each opportunity? | 4 項（cell；outcome；type-market；type-product） |
| Q0339 | Aerospace / Defense / Signal Generator / Signal Analyzer | competitive / L4 | FAIL／REASONING_GAP／direct | What evidence is required to compare our Signal Generator / Signal Analyzer solution with a competitor for Aerospace / Defense without making unsupported claims? | 5 項（cell；outcome；type-difficulty；type-market；type-product） |
| Q0351 | Aerospace / Defense / Vector Network Analyzer | basic / L1 | FAIL／REASONING_GAP／tool | What are the most important S-parameters capabilities for applications in Aerospace / Defense? | 3 項（cell；type-market；type-product） |
| Q0401 | Automotive / Signaling / Non-signaling Tester | basic / L1 | INSUFFICIENT_KNOWLEDGE／SOURCE_GAP or RETRIEVAL_GAP／tool | What are the most important signaling test capabilities for applications in Automotive? | 3 項（cell；type-market；type-product） |
| Q0461 | Automotive / Oscilloscope | application / L2 | INSUFFICIENT_KNOWLEDGE／SOURCE_GAP or RETRIEVAL_GAP／tool | For a Automotive use case involving automotive radar, where would Oscilloscope fit in the test workflow? | 3 項（cell；type-market；type-product） |
| Q0489 | Automotive / Oscilloscope | competitive / L4 | PASS／-／direct | What evidence is required to compare our Oscilloscope solution with a competitor for Automotive without making unsupported claims? | 2 項（type-market；type-product） |
| Q0546 | Automotive / Signal Generator / Signal Analyzer | strategic / L5 | FAIL／REASONING_GAP／tool | Based on current vault evidence, what are the strongest opportunities for Signal Generator / Signal Analyzer in Automotive, and what evidence supports each opportunity? | 3 項（cell；type-market；type-product） |
| Q0571 | Automotive / Vector Network Analyzer | solution_mapping / L3 | INSUFFICIENT_KNOWLEDGE／SOURCE_GAP or RETRIEVAL_GAP／direct | Map the chain from a Automotive market requirement to a measurable parameter and then to a required capability of Vector Network Analyzer. | 4 項（cell；outcome；type-market；type-product） |
| Q0581 | Automotive / Vector Network Analyzer | cross_domain / L4 | FAIL／REASONING_GAP／tool | How do changes in automotive radar technology affect the measurement capability required from Vector Network Analyzer? | 2 項（type-market；type-product） |
| Q0631 | AI / Signaling / Non-signaling Tester | cross_domain / L4 | FAIL／REASONING_GAP／tool | How do changes in AI data centers technology affect the measurement capability required from Signaling / Non-signaling Tester? | 1 項（type-market） |
| Q0639 | AI / Signaling / Non-signaling Tester | competitive / L4 | PASS／-／direct | What evidence is required to compare our Signaling / Non-signaling Tester solution with a competitor for AI without making unsupported claims? | 3 項（cell；type-market；type-product） |
| Q0646 | AI / Signaling / Non-signaling Tester | strategic / L5 | FAIL／REASONING_GAP／tool | Based on current vault evidence, what are the strongest opportunities for Signaling / Non-signaling Tester in AI, and what evidence supports each opportunity? | 1 項（type-market） |
| Q0671 | AI / Oscilloscope | solution_mapping / L3 | PASS／-／direct | Map the chain from a AI market requirement to a measurable parameter and then to a required capability of Oscilloscope. | 3 項（cell；type-market；type-product） |
| Q0701 | AI / Signal Generator / Signal Analyzer | basic / L1 | FAIL／REASONING_GAP／tool | What are the most important signal generation capabilities for applications in AI? | 3 項（cell；type-market；type-product） |
| Q0761 | AI / Vector Network Analyzer | application / L2 | FAIL／REASONING_GAP／tool | For a AI use case involving AI data centers, where would Vector Network Analyzer fit in the test workflow? | 3 項（cell；type-market；type-product） |
| Q0801 | Semiconductor / Signaling / Non-signaling Tester | basic / L1 | PASS／-／tool | What are the most important signaling test capabilities for applications in Semiconductor? | 1 項（type-market） |
| Q0846 | Semiconductor / Signaling / Non-signaling Tester | strategic / L5 | FAIL／REASONING_GAP／tool | Based on current vault evidence, what are the strongest opportunities for Signaling / Non-signaling Tester in Semiconductor, and what evidence supports each opportunity? | 3 項（cell；type-market；type-product） |
| Q0871 | Semiconductor / Oscilloscope | solution_mapping / L3 | INSUFFICIENT_KNOWLEDGE／SOURCE_GAP or RETRIEVAL_GAP／direct | Map the chain from a Semiconductor market requirement to a measurable parameter and then to a required capability of Oscilloscope. | 1 項（type-market） |
| Q0881 | Semiconductor / Oscilloscope | cross_domain / L4 | INSUFFICIENT_KNOWLEDGE／SOURCE_GAP or RETRIEVAL_GAP／tool | How do changes in RFIC validation technology affect the measurement capability required from Oscilloscope? | 3 項（cell；type-market；type-product） |
| Q0911 | Semiconductor / Signal Generator / Signal Analyzer | application / L2 | 未跑過 | For a Semiconductor use case involving RFIC validation, where would Signal Generator / Signal Analyzer fit in the test workflow? | 3 項（cell；type-market；type-product） |
| Q0989 | Semiconductor / Vector Network Analyzer | competitive / L4 | PASS／-／direct | What evidence is required to compare our Vector Network Analyzer solution with a competitor for Semiconductor without making unsupported claims? | 3 項（cell；type-market；type-product） |
| Q1001 | 基礎：RF / Measurement Fundamentals（EVM） | - / - | INSUFFICIENT_KNOWLEDGE／SOURCE_GAP or RETRIEVAL_GAP／tool | What is EVM, and which product-related measurement decisions depend on understanding it? | 1 項（foundation） |
| Q1021 | 基礎：Wireless Fundamentals（OFDM） | - / - | INSUFFICIENT_KNOWLEDGE／SOURCE_GAP or RETRIEVAL_GAP／tool | What is OFDM, and which product-related measurement decisions depend on understanding it? | 1 項（foundation） |
| Q1041 | 基礎：High-Speed / Signal Integrity（eye diagram） | - / - | INSUFFICIENT_KNOWLEDGE／SOURCE_GAP or RETRIEVAL_GAP／tool | What is eye diagram, and which product-related measurement decisions depend on understanding it? | 1 項（foundation） |
| Q1061 | 基礎：Instrument & Measurement Principles（non-signaling tester） | - / - | FAIL／REASONING_GAP／tool | What is non-signaling tester, and which product-related measurement decisions depend on understanding it? | 1 項（foundation） |
| Q1071 | 基礎：Technical Document / Paper Understanding（measurement method） | - / - | INSUFFICIENT_KNOWLEDGE／SOURCE_GAP or RETRIEVAL_GAP／tool | What is measurement method, and which product-related measurement decisions depend on understanding it? | 1 項（foundation） |
| Q1091 | 基礎：Cross-Knowledge Reasoning（signal-integrity-to-oscilloscope） | - / - | INSUFFICIENT_KNOWLEDGE／SOURCE_GAP or RETRIEVAL_GAP／tool | What is signal-integrity-to-oscilloscope, and which product-related measurement decisions depend on understanding it? | 1 項（foundation） |
