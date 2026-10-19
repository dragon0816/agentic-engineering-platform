# 上下游供應鏈列表(節錄)

> 節錄自專案文件「Small Cell / CPE / WiFi AP 上下游供應鏈列表」(整理日期 2026-10-07)。
> 只保留匯入示範所需的表格,已移除來源連結,「說明」欄部分節錄。完整內容請以專案原文件為準。

## 2.1 晶片/SoC

| 供應鏈層級 | 料件/技術 | 全球代表廠 | 台系代表廠 | 對應產品 | 說明 |
|:---|:---|:---|:---|:---|:---|
| WiFi SoC | WiFi 7/8 基頻/RF SoC | Qualcomm、Broadcom、MediaTek、Realtek | 聯發科(2454)、瑞昱(2379) | WiFi AP、CPE gateway、router | Qualcomm主導手機/行動整合；Broadcom主導企業基礎設施AP；MediaTek主打中階/IoT；Realtek主打入門級。三家合計WiFi 7晶片市占約71% |
| DOCSIS SoC | DOCSIS 3.1/4.0 modem SoC | Broadcom、MaxLinear | — | DOCSIS gateway/CPE | MaxLinear Puma 8支援ESD版D4.0；Broadcom「unified」D4.0晶片支援ESD+FDX。CableLabs已授予VFI認證 |
| PON SoC | 50G PON / XGS-PON / 10G PON ONU SoC | Broadcom、MaxLinear、Marvell(Cortina) | — | PON ONU/gateway | 中磊50G PON ONU符合ITU-T G.9804.3，支援tri-PON共存；Broadcom為PON SoC主要供應商 |
| 5G Modem | 5G FWA CPE modem-RF平台 | Qualcomm、MediaTek | 聯發科(2454) | 5G FWA CPE | Qualcomm Snapdragon X75/X80 / MediaTek T830為2026年baseline平台，支援5G-Advanced AI beamforming、4CA |
| 5G Baseband | O-RAN RU/DU baseband SoC / FPGA | Qualcomm、Picocom、Intel/Altera(FPGA)、AMD/Xilinx(FPGA)、NVIDIA(AI-RAN) | — | Small Cell / O-RAN RU | 啟碁O-RU整合NVIDIA Aerial平台；明泰採用O-RAN RU+DU/CU架構。FPGA廣泛用於O-RAN RU前傳/加速器 |
| Ethernet Switch | 資料中心交換器ASIC | Broadcom (Tomahawk 5 / Jericho3 / Ramon3) | — | AI資料中心交換器、Small Cell回傳 | 智邦51.2Tbps 800G交換器基於Broadcom Tomahawk 5；明泰1.6T水冷交換器搭載Broadcom TH6晶片(102.4Tbps) |

## 2.2 RF 前端/PA/LNA/濾波器

| 供應鏈層級 | 料件/技術 | 全球代表廠 | 台系代表廠 | 對應產品 | 說明 |
|:---|:---|:---|:---|:---|:---|
| RF PA (砷化鎵) | WiFi 7 / 5G PA / LNA / FEM | Qorvo、Skyworks、Broadcom(FBAR)、Qualcomm(RF360)、Murata | **穩懋(3105)**、**宏捷科(8086)**、**全新(2455)** | WiFi AP、5G CPE、Small Cell | NXP退出5G RFGaN PA市場（2027年前關閉亞利桑那廠），台廠PA三雄有望承接轉單。穩懋為全球最大砷化鎵晶圓代工廠，WiFi 7導入帶動PA用量增加 |
| RF PA (GaN) | 5G基站/Small Cell高功率PA | Qorvo(GaN)、Sumitomo、MACOM | 穩懋(GaN佈局中) | Small Cell RU、高功率ODU | NXP退出GaN PA市場，Qorvo/MACOM為GaN主要供應商 |
| RF濾波器 | BAW/SAW/FBAR濾波器 | Broadcom(FBAR)、Qorvo(BAW)、Murata(SAW)、Taiyo Yuden | — | WiFi AP、5G CPE共存 | 合勤WBE660S內建4G/5G干擾濾波器，需BAW/SAW濾波器支援5GHz/6GHz共存 |
| RF Switch | RF開關/雙工器 | Qorvo、Skyworks、Peregrine | — | 所有無線產品 | — |

## 2.3 天線/RF設計

| 供應鏈層級 | 料件/技術 | 全球代表廠 | 台系代表廠 | 對應產品 | 說明 |
|:---|:---|:---|:---|:---|:---|
| 天線設計/製造 | WiFi天線、5G MIMO天線、mmWave相控陣列 | Amphenol、Molex、TE Connectivity、Taoglas、Laird | 耀登(3138)、啟碁(內建天線設計能力)、台揚(射頻/微波/天線) | WiFi AP、5G CPE、Small Cell RU、LEO終端 | 啟碁為台廠中RF天線設計能力最強者，自建天線/RF/OTA測試能力；耀登為天線設計/製造與OTA量測專業廠 |
| 毫米波天線 | mmWave phased array antenna module (PAM) | Qualcomm、Keysight(OTA測試) | 台揚(Ka頻段相控陣列天線研發中) | 5G mmWave Small Cell、LEO終端 | 台揚Ka頻段相控陣列天線與RF Chain為中長期方向 |
| OTA測試 | 毫米波OTA暗室、3D pattern量測 | Keysight、Rohde & Schwarz、Anritsu、EMC-ESD | 耀登(3138)、倚強(Aethertek) | 所有無線產品認證 | 耀登提供天線OTA量測服務；倚強為5G mmWave自動化測試方案領導者 |

## 2.4 PCB / 基板 / 銅箔基板

| 供應鏈層級 | 料件/技術 | 台系代表廠 | 對應產品 | 說明 |
|:---|:---|:---|:---|:---|
| HDI PCB | 高密度互連多層板 | **華通(2313)**、**欣興(3037)** | WiFi AP、5G CPE、Small Cell | 華通為HDI技術龍頭，同時為SpaceX Starlink最大PCB供應商 |
| 多層板/網通板 | 網通設備高層數PCB | **南電(8046)**、**金像電(2368)**、**燿華(2367)** | Small Cell RU、交換器、CPE | 南電網通產品營收占比逐年放大；金像電為全球伺服器PCB板王 |

## 2.5 光通訊 / 光模組

| 供應鏈層級 | 料件/技術 | 全球代表廠 | 台系代表廠 | 對應產品 | 說明 |
|:---|:---|:---|:---|:---|:---|
| 光收發模組 | 800G/1.6T光模組、PON ONU光模組 | Coherent、Lumentum、Innolight、Source Photonics | **波若威(3164)**、**聯鈞(3450)**、**眾達-KY(3130)**、**光環(3234)**、**上詮(3633)** | PON ONU、AI資料中心、CPE光模組 | 正文與NewPhotonics合作開發AiPhoton 1.6T OSFP光模組；中磊50G PON ONU系列含SFP可插拔式ONU |
| 光晶片/雷射 | 光通訊雷射/光偵測器 | Lumentum、Coherent、Broadcom | 穩懋(光通訊VCSEL/PD代工) | PON ONU、光模組 | 穩懋光通訊營收占比從Q1的5-10%升至Q2的10-15%，Q3持續成長 |

## 三、中游製造商對應表

| 公司 | 代號 | Small Cell | CPE | WiFi AP | 主要上游依賴 | 主要下游市場 |
|:---|:---:|:---:|:---:|:---:|:---|:---|
| **啟碁 WNC** | 6285 | ✅ O-RU / AI-RAN | ✅ 5G FWA / LEO終端 | ⚠️ WiFi 7 router | Qualcomm(5G modem)、Broadcom(交換器)、NVIDIA(AI-RAN)、穩懋(PA)、NXP/FPGA | 歐洲電信商、北美FWA、LEO衛星營運商、企業 |
| **中磊 Sercomm** | 5388 | ✅ Sub-6G+mmWave | ✅ DOCSIS/PON/FWA | ✅ Enterprise AP | Broadcom(DOCSIS/PON/Switch)、Qualcomm(WiFi)、MaxLinear(DOCSIS)、穩懋(PA) | 北美MSO、歐洲電信商、企業 |
| **智易 Arcadyan** | 3596 | ✅ 4G/LTE Small Cell | ✅ 5G CPE/DOCSIS/WiFi | ⚠️ WiFi CPE/Extender | Qualcomm(5G/WiFi)、Broadcom(DOCSIS)、MediaTek | 全球電信商ODM/OEM |
| **明泰 Alpha** | 3380 | ✅ RU+DU/CU+Small Cell | ✅ 5G FWA/DOCSIS 4.0 | ⚠️ WiFi 7 router | Broadcom(TH6/交換器)、Qualcomm(WiFi)、FPGA(Xilinx/Intel) | 美洲57%、亞洲33%、歐洲9%、印度LBR |
| **合勤控 Zyxel** | 3704 | ❌ | ✅ 5G FWA/10G PON | ✅ WiFi 7/8 AP品牌 | Qualcomm(WiFi 7 SoC)、Broadcom(PON/交換器) | 歐洲電信商(40%)、企業/SMB、國防 |
| **神準 EnGenius** | 3558 | ❌ | ⚠️ 寬頻CPE | ✅ WiFi 7 Cloud AP品牌 | Qualcomm(WiFi 7 SoC)、穩懋(PA) | 北美企業/SMB品牌通路 |
| **仲琦 Hitron** | 2419 | ❌ | ✅ DOCSIS 4.0/Fiber ONU | ❌ | Broadcom/MaxLinear(DOCSIS SoC)、Qualcomm(WiFi) | 北美MSO、有線電視營運商 |
| **正文 Gemtek** | 4906 | ❌ | ✅ 5G mmWave/Sub-6 CPE | ⚠️ WiFi router/模組 | Qualcomm(5G modem)、MaxLinear(Puma 8)、NewPhotonics(光模組) | 印度電信商(mmWave FWA)、CSP/AI資料中心 |
| **亞旭 Askey** | — | ✅ 5G/4G Small Cell | ✅ 5G FWA CPE | ✅ WiFi 7 ODM | Qualcomm(5G/WiFi)、Broadcom | 5G專網、電信商ODM |
| **友訊 D-Link** | 2332 | ❌ | ❌ | ✅ WiFi AP品牌 | Qualcomm/Broadcom(WiFi SoC) | 企業AI資料中心、區域型機房 |
| **台揚** | 2314 | ⚠️ O-RAN RU卡位 | ❌ | ❌ | FPGA(Xilinx/Intel)、RF元件(Qorvo/MACOM) | 衛星營運商、電信商O-RAN |

## 5.1 測試儀器

| 儀器類別 | 代表廠 | 應用場景 | 對應產品 |
|:---|:---|:---|:---|
| 網路分析儀/頻譜分析儀 | Keysight、Rohde & Schwarz、Anritsu | RF性能量測、PA/LNA S參數、天線pattern | Small Cell RU、5G CPE、WiFi AP RF校準 |
| 無線綜測儀 | LitePoint(Teradyne)、Rohde & Schwarz(CMW500) | WiFi 7/5G TX/RX測試、throughput測試 | WiFi AP、5G FWA CPE量產測試 |
| OTA量測系統 | Keysight(OTA暗室)、Anritsu、EMC-ESD | 毫米波OTA、3D天線pattern、SAR | WiFi AP、5G CPE、Small Cell RU |
| 毫米波自動化測試 | 倚強科技(Aethertek) | 5G mmWave自動化測試方案、FR2 O-RU測試 | 5G mmWave Small Cell、O-RAN RU |

## 5.2 認證/合規實驗室

| 認證類別 | 代表機構 | 驗證內容 | 對應產品 |
|:---|:---|:---|:---|
| O-RAN OTIC | **Auray Technology(耀睿科技)** — 台灣唯一O-RAN OTIC | O-RAN RU/DU互通性、Plugfest、Fronthaul、SMO/RIC/M-plane | O-RAN RU、Small Cell |
| WiFi Alliance | Wi-Fi Alliance認證實驗室 | WiFi 7(802.11be)認證、WPA3、EasyMesh | WiFi AP、CPE gateway |
| DOCSIS | CableLabs | DOCSIS 3.1/4.0認證、VFI(Verified for Interoperability) | DOCSIS gateway/CPE |
| 電信法規 | NCC(國家通訊傳播委員會)、TTC(電信技術中心) | 型式認證、頻率使用、技術審驗 | 所有無線通訊設備在台銷售/使用 |
| 國際安規/EMC | SGS、Bureau Veritas、TÜV | 安規、EMC、SAR、環境可靠性 | 所有無線產品出口認證 |
| PTP/SyncE | IEEE 1588 PTP認證 | 高精度時間同步、SyncE | Small Cell回傳、電信級交換機 |
| BBF | Broadband Forum | TR-069/TR-369管理、Gfast | CPE gateway管理、遠端管理 |
