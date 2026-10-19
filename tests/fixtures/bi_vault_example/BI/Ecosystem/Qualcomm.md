---
type: ecosystem
name: Qualcomm
node: "[[L1-Chipset]]"
role: chipset
technologies: ["[[WiFi-7]]", "[[5G-NR-FR2]]", "[[NTN-Satellite]]"]
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
- 【5G Modem】5G FWA CPE modem-RF平台 / 說明:Qualcomm Snapdragon X75/X80 / MediaTek T830為2026年baseline平台，支援5G-Advanced AI beamforming、4CA / 對應產品:5G FWA CPE / 來源地區:全球
- 【5G Baseband】O-RAN RU/DU baseband SoC / FPGA / 說明:啟碁O-RU整合NVIDIA Aerial平台；明泰採用O-RAN RU+DU/CU架構。FPGA廣泛用於O-RAN RU前傳/加速器 / 對應產品:Small Cell / O-RAN RU / 來源地區:全球
- 【RF PA (砷化鎵)】WiFi 7 / 5G PA / LNA / FEM / 說明:NXP退出5G RFGaN PA市場（2027年前關閉亞利桑那廠），台廠PA三雄有望承接轉單。穩懋為全球最大砷化鎵晶圓代工廠，WiFi 7導入帶動PA用量增加 / 對應產品:WiFi AP、5G CPE、Small Cell / 備註:RF360 / 來源地區:全球
- 【毫米波天線】mmWave phased array antenna module (PAM) / 說明:台揚Ka頻段相控陣列天線與RF Chain為中長期方向 / 對應產品:5G mmWave Small Cell、LEO終端 / 來源地區:全球
- 【上游】WiFi / BT SoC
- 【上游】基頻／RedCap 晶片
