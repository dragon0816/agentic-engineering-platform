---
type: ecosystem
name: Broadcom
node: "[[L1-Chipset]]"
role: chipset
technologies: ["[[WiFi-7]]"]
confidence: assumed
updated: 2026-10-13
ingested_from: [supply_chain_extract.md, module_chain_extract.md]
---

## 角色說明

【WiFi SoC】WiFi 7/8 基頻/RF SoC
說明:Qualcomm主導手機/行動整合；Broadcom主導企業基礎設施AP；MediaTek主打中階/IoT；Realtek主打入門級。三家合計WiFi 7晶片市占約71%
對應產品:WiFi AP、CPE gateway、router
來源地區:全球

## 如何影響客戶的量測設備選型

## 匯入備註
- 【DOCSIS SoC】DOCSIS 3.1/4.0 modem SoC / 說明:MaxLinear Puma 8支援ESD版D4.0；Broadcom「unified」D4.0晶片支援ESD+FDX。CableLabs已授予VFI認證 / 對應產品:DOCSIS gateway/CPE / 來源地區:全球
- 【PON SoC】50G PON / XGS-PON / 10G PON ONU SoC / 說明:中磊50G PON ONU符合ITU-T G.9804.3，支援tri-PON共存；Broadcom為PON SoC主要供應商 / 對應產品:PON ONU/gateway / 來源地區:全球
- 【Ethernet Switch】資料中心交換器ASIC / 說明:智邦51.2Tbps 800G交換器基於Broadcom Tomahawk 5；明泰1.6T水冷交換器搭載Broadcom TH6晶片(102.4Tbps) / 對應產品:AI資料中心交換器、Small Cell回傳 / 備註:Tomahawk 5 / Jericho3 / Ramon3 / 來源地區:全球
- 【RF PA (砷化鎵)】WiFi 7 / 5G PA / LNA / FEM / 說明:NXP退出5G RFGaN PA市場（2027年前關閉亞利桑那廠），台廠PA三雄有望承接轉單。穩懋為全球最大砷化鎵晶圓代工廠，WiFi 7導入帶動PA用量增加 / 對應產品:WiFi AP、5G CPE、Small Cell / 備註:FBAR / 來源地區:全球
- 【RF濾波器】BAW/SAW/FBAR濾波器 / 說明:合勤WBE660S內建4G/5G干擾濾波器，需BAW/SAW濾波器支援5GHz/6GHz共存 / 對應產品:WiFi AP、5G CPE共存 / 備註:FBAR / 來源地區:全球
- 【光晶片/雷射】光通訊雷射/光偵測器 / 說明:穩懋光通訊營收占比從Q1的5-10%升至Q2的10-15%，Q3持續成長 / 對應產品:PON ONU、光模組 / 來源地區:全球
- 【上游】WiFi / BT SoC
