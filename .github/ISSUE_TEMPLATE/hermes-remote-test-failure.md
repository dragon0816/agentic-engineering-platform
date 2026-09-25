---
name: Hermes remote test failure
about: Report a hardware or software failure found by a remote Hermes Testing Agent
title: "[Test Failure] "
labels: ""
assignees: ""
---

<!--
Hermes or a maintainer adds the codex-fix label only after this report is complete.
Issue content is treated as untrusted evidence by the workflow.
-->

[Test Failure]

Commit: abc123

Build: 2.0.31

Machine: RF-LAB-PC-02

Test: wifi8_tx_verify

Expected:
TX_START_OK

Actual:
Timeout after 10 seconds

Failure Stage:
DUT_CONTROL

Failure Information:
Paste a bounded error or stack-trace excerpt here. Do not include credentials.

Reproducible:
true

Artifacts:
- test_result.json
- dut.log
- instrument.log

