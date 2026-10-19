---
type: node
layer: L2
name: L2-RF-FEM-Module
upstream: ["[[L1-Chipset]]"]
downstream: ["[[L3-Handset]]", "[[L3-WiFi-Router-CPE]]"]
typical_test_needs: [PA/濾波器特性, 線性度 ACLR EVM, 量產 ATE 測試]
---

功率放大器、濾波器、前端模組。
