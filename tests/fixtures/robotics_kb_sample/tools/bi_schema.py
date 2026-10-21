"""Single source of truth for BI card schemas (used by bi_ingest.py).

Add or change a field here and ingest, template generation and validation follow.
Field kinds: str, int, bool, date, enum, list, link, linklist, virtual
  - link / linklist  -> written as "[[name]]" (quoted) in YAML
  - virtual          -> used only for the file name, never written to YAML

v4 (robotics): wireless + AIDC + robotics share one schema.
  * DOMAINS 加入 robotics。
  * Technology / TestSolution / Concept 改為多領域(domain 為清單),可跨領域重用。
  * CustomerProduct 新增 nodes / ecosystem / launch_date;公司型卡片新增 nodes。
  * 新增 Opportunity 卡(Application -> 我方 TestSolution -> Opportunity 鏈)。
  * test_type 加 EMC;Ecosystem role 加 institute、ipc。
"""


def F(kind, aliases=(), required=False, enum=None, default=None, rng=None):
    return {"kind": kind, "aliases": list(aliases), "required": required,
            "enum": enum, "default": default, "range": rng}


# --- domain: 同一套卡片同時服務 wireless、AIDC、robotics -----------------------------
# 單一領域的卡片(Node/Trend/Application/CustomerProduct/Signal/Opportunity)用 enum;
# 公司型(Account/Ecosystem/Competitor)與可跨領域重用的資產(Technology/TestSolution/Concept)用 list,
# 例如 [wireless, robotics]。舊卡片沒有 domain 欄位時,Dashboard 一律視為 wireless。
DOMAINS = ["wireless", "AIDC", "robotics"]
DOMAIN_ALIASES = ["領域", "domain"]


def schema(folder, filename, fields, body, tail=True, domain="one"):
    items = list(fields)
    if domain == "one":
        items.insert(1, ("domain", F("enum", DOMAIN_ALIASES, enum=DOMAINS, default="wireless")))
    elif domain == "multi":
        items.insert(1, ("domain", F("list", DOMAIN_ALIASES)))
    f = dict(items)
    if tail:
        f["confidence"] = F("enum", ["信心度", "可信度"], enum=["verified", "assumed"], default="assumed")
        f["updated"] = F("date", ["更新日期", "更新", "最後更新"], default="today")
    return {"folder": folder, "filename": filename, "fields": f, "body": body}


DV_TREND_BY_TECH = ('## 相關趨勢\n```dataview\nLIST\nFROM "BI/Trend"\n'
                    'WHERE contains(related_tech, this.file.link)\n```')
DV_SIGNALS = ('## 證據(Signal)\n```dataview\nTABLE date, summary, reliability\nFROM "BI/Signal"\n'
              'WHERE contains(related, this.file.link)\nSORT date DESC\n```')
DV_SOLUTIONS = ('## 對應的 Test Solution(廠商空白 = 我方 R&S)\n```dataview\nTABLE vendor AS 廠商\nFROM "BI/TestSolution"\n'
                'WHERE contains(applications, this.file.link)\nSORT vendor ASC\n```')

DV_CONCEPTS = ('## 相關概念(給業務的白話解釋)\n```dataview\nTABLE one_liner AS 一句話\nFROM "BI/Concept"\n'
               'WHERE contains(technologies, this.file.link)\n```')

# --- v4: 掛勾視圖(Ecosystem / Value Chain Node / Trend / CustomerProduct / Opportunity)-------------
DV_NODE_ECO = ('## 此層生態系成員\n```dataview\nTABLE role AS 角色, relationship_to_us AS 與我關係\nFROM "BI/Ecosystem"\n'
               'WHERE node = this.file.link OR contains(default(nodes, []), this.file.link)\nSORT role ASC\n```')
DV_NODE_CP = ('## 此層客戶產品\n```dataview\nTABLE account AS 客戶, launch_date AS 上市日, launch_window AS 上市時程\n'
              'FROM "BI/CustomerProduct"\n'
              'WHERE node = this.file.link OR contains(default(nodes, []), this.file.link)\nSORT launch_date ASC\n```')
DV_NODE_TRENDS = ('## 影響此層的趨勢\n```dataview\nTABLE stage AS 階段, time_to_demand AS 需求時間, measurement_impact AS 量測影響\n'
                  'FROM "BI/Trend"\nWHERE contains(default(affected_nodes, []), this.file.link)\n'
                  'SORT measurement_impact DESC\n```')
DV_ECO_CP = ('## 使用此成員的客戶產品\n```dataview\nTABLE account AS 客戶, node AS 節點, launch_date AS 上市日\n'
             'FROM "BI/CustomerProduct"\nWHERE contains(default(ecosystem, []), this.file.link)\n'
             'SORT launch_date ASC\n```')
DV_CP_ECO = ('## 供應鏈成員(Ecosystem 或 Account 卡)\n```dataview\nTABLE role AS 角色, relationship_to_us AS 與我關係, node AS 節點\n'
             'FROM "BI/Ecosystem" OR "BI/Account"\nWHERE contains(default(this.ecosystem, []), file.link)\n```')
DV_CP_TRENDS = ('## 影響此產品的趨勢(經技術或節點推得)\n```dataview\n'
                'TABLE stage AS 階段, time_to_demand AS 需求時間, measurement_impact AS 量測影響\n'
                'FROM "BI/Trend"\n'
                'WHERE length(filter(default(this.technologies, []), (t) => contains(default(related_tech, []), t))) > 0\n'
                '   OR length(filter(default(this.nodes, []), (n) => contains(default(affected_nodes, []), n))) > 0\n'
                '   OR (this.node AND contains(default(affected_nodes, []), this.node))\n'
                'SORT measurement_impact DESC\n```')
DV_CP_OPPS = ('## 相關商機\n```dataview\nTABLE deal_stage AS 階段, our_solutions AS 我方方案, expected_close AS 預計成交\n'
              'FROM "BI/Opportunity"\nWHERE customer_product = this.file.link\nSORT expected_close ASC\n```')
DV_TREND_CP = ('## 受影響的客戶產品(經技術或節點推得)\n```dataview\n'
               'TABLE account AS 客戶, node AS 節點, launch_date AS 上市日\nFROM "BI/CustomerProduct"\n'
               'WHERE length(filter(default(this.related_tech, []), (t) => contains(default(technologies, []), t))) > 0\n'
               '   OR length(filter(default(this.affected_nodes, []), (n) => contains(default(nodes, []), n) OR n = node)) > 0\n'
               'SORT launch_date ASC\n```')
DV_APP_OPPS = ('## 相關商機\n```dataview\nTABLE account AS 客戶, deal_stage AS 階段, our_solutions AS 我方方案\n'
               'FROM "BI/Opportunity"\nWHERE contains(default(applications, []), this.file.link)\n'
               'SORT deal_stage ASC\n```')
DV_SOL_OPPS = ('## 相關商機\n```dataview\nTABLE account AS 客戶, deal_stage AS 階段, expected_close AS 預計成交\n'
               'FROM "BI/Opportunity"\nWHERE contains(default(our_solutions, []), this.file.link)\n'
               'SORT expected_close ASC\n```')

NODES_ALIASES = ["涉及節點", "節點清單", "nodes"]

SCHEMAS = {
    # ------------------------------------------------------------ opportunity layer (v4)
    # Application -> 我方 TestSolution(vendor 空白)-> Opportunity。
    # our_solutions 應連到 vendor 空白的方案;schema 無法強制,由 Dashboard §19 檢查。
    "opportunity": schema("Opportunity", ["name"], [
        ("name", F("str", ["商機名稱", "商機", "名稱", "opportunity", "name"], required=True)),
        ("account", F("link", ["客戶", "account"])),
        ("customer_product", F("link", ["客戶產品", "產品", "customer product", "customer_product"])),
        ("applications", F("linklist", ["對應應用", "應用", "applications"])),
        ("our_solutions", F("linklist", ["我方方案", "提案方案", "our solutions", "our_solutions"])),
        ("competitors", F("linklist", ["競爭對手", "競品公司", "competitors"])),
        ("deal_stage", F("enum", ["商機階段", "階段", "deal stage", "deal_stage"],
                         enum=["lead", "qualified", "proposal", "eval", "negotiation", "won", "lost"],
                         default="lead")),
        ("expected_close", F("date", ["預計成交", "預計結案日", "expected close", "expected_close"])),
        ("size", F("enum", ["規模", "size"], enum=["S", "M", "L"])),
        ("lost_to", F("link", ["敗給", "lost to", "lost_to"])),
        ("owner", F("str", ["負責人", "owner"])),
    ], ["## 商機概述", "## 客戶需求與痛點", "## 提案與競爭情況", "## 下一步"]),

    # ------------------------------------------------------------ solution layer
    "test_solution": schema("TestSolution", ["name"], [
        ("name", F("str", ["方案名稱", "方案", "名稱", "solution", "solution name"], required=True)),
        ("vendor", F("link", ["廠商", "方案廠商", "競品廠商", "vendor"])),  # 空白 = 我方(Rohde & Schwarz)方案
        ("applications", F("linklist", ["對應應用", "應用", "應用場景", "application", "applications"])),
        ("technologies", F("linklist", ["技術", "technology", "technologies"])),
        ("nodes", F("linklist", ["節點", "價值鏈節點", "node", "nodes"])),
        ("test_type", F("enum", ["測試類型", "類型", "test type"],
                        enum=["conducted", "OTA", "protocol", "channel-emu", "spectrum", "power", "ATE",
                              # AIDC 新增:高速電氣、光學、通道與材料特性、晶圓級探針
                              "signal-integrity", "optical", "channel-char", "wafer-probe",
                              # robotics 新增:電磁相容
                              "EMC"])),
        ("tier", F("enum", ["方案型態", "型態", "tier"],
                   enum=["instrument", "integrated", "automated", "service"])),
        ("automation", F("enum", ["自動化程度", "自動化"], enum=["manual", "semi", "full"])),
        ("dut", F("str", ["被測物", "DUT"])),
        ("test_items", F("list", ["測試項目", "test items"])),
        ("standards", F("list", ["標準", "標準法規", "standards"])),
        ("instruments", F("list", ["儀器配置", "儀器", "設備", "instruments"])),
        ("price_band", F("enum", ["價格帶", "價格"], enum=["entry", "mid", "high"])),
        ("services", F("list", ["服務", "services"])),
        ("competing_solutions", F("linklist", ["競品方案", "競品", "competitors", "competing solutions"])),
        ("reference_customers", F("linklist", ["參考客戶", "客戶", "reference customers"])),
        ("status", F("enum", ["狀態", "status"], enum=["planning", "available", "EOL"], default="planning")),
        ("owner", F("str", ["負責人", "owner"])),
    ], [
        "## 方案概要",
        "## 技術架構與測試流程\n- 連接架構(Block Diagram):\n- 測試流程:",
        "## 驗證與證據\n- Demo 環境與腳本:\n- 實測資料與 App Note:\n- 成功案例(注意保密):",
        "## 競爭定位(Battlecard)\n- 我方差異化賣點:\n- 弱點與常見異議:\n- 回應話術:",
        "## Discovery Questions\n- ",
        "## 回饋與演進\n- 客戶回報的缺口 → Roadmap Request:",
        DV_SOL_OPPS,
    ], domain="multi"),

    "application": schema("Application", ["name"], [
        ("name", F("str", ["應用名稱", "名稱", "應用場景", "應用", "name"], required=True)),
        ("value_chain", F("enum", ["價值鏈", "價值鏈層級", "value chain"],
                          enum=["L1", "L2", "L3", "L4", "L5", "X"])),
        ("lifecycle", F("enum", ["生命週期", "階段", "lifecycle"],
                        enum=["RD", "Certification", "Production", "Reliability", "Field"])),
        ("nodes", F("linklist", ["節點", "nodes"])),
        ("technologies", F("linklist", ["技術", "technologies"])),
        ("trends", F("linklist", ["趨勢", "trends"])),
        ("measurement_topics", F("list", ["量測主題", "量測項目", "measurement topics"])),
        ("priority", F("int", ["優先度", "priority"], rng=(1, 5))),
    ], ["## 應用說明", "## 痛點與價值主張", DV_SOLUTIONS, DV_APP_OPPS]),

    "competitor": schema("Competitor", ["name"], [
        ("name", F("str", ["名稱", "公司", "廠商", "競品公司", "name"], required=True)),
        ("node", F("link", ["節點", "node"])),
        ("nodes", F("linklist", NODES_ALIASES)),
        ("technologies", F("linklist", ["技術", "technologies"])),
        ("product_lines", F("list", ["產品線", "主要產品", "product lines"])),
        ("strengths", F("list", ["強項", "優勢", "strengths"])),
        ("weaknesses", F("list", ["弱項", "劣勢", "weaknesses"])),
        ("pricing_position", F("enum", ["價格定位", "價位", "pricing position"], enum=["low", "par", "premium"])),
        ("recent_moves", F("list", ["近期動態", "動態", "recent moves"])),
        ("ticker", F("str", ["代號", "股票代號", "ticker"])),
    ], ["## 公司與產品概述", "## 強弱項與近期動態", "## Battlecard"], domain="multi"),

    # ------------------------------------------------------------ customer / ecosystem layer
    "customer_product": schema("CustomerProduct", ["product_name"], [
        ("product_name", F("str", ["產品名稱", "產品", "名稱", "product name", "product"], required=True)),
        ("account", F("link", ["客戶", "account"])),
        ("node", F("link", ["節點", "node"])),                      # 主要節點
        ("nodes", F("linklist", NODES_ALIASES)),                    # 涉及的全部節點(含主要節點)
        ("technologies", F("linklist", ["技術", "technologies"])),
        ("chipset_modules", F("linklist", ["晶片模組", "晶片/模組", "晶片商", "chipset modules"])),
        ("ecosystem", F("linklist", ["供應鏈成員", "生態系", "生態系成員", "ecosystem"])),
        ("launch_window", F("str", ["上市時程", "上市時間", "上市", "launch window"])),
        ("launch_date", F("date", ["預估上市日", "上市日期", "上市日", "launch date", "launch_date"])),
        ("volume_tier", F("enum", ["量級", "出貨量級", "volume tier"], enum=["low", "mid", "high"])),
        ("test_stage_now", F("enum", ["目前階段", "測試階段", "test stage now"], enum=["RD", "cert", "production"])),
        ("inferred_applications", F("linklist", ["推論應用", "對應應用", "inferred applications"])),
    ], ["## 產品概述", "## 時程(研發、認證、量產)", "## 推論的量測需求",
        DV_CP_ECO, DV_CP_TRENDS, DV_CP_OPPS]),

    "ecosystem": schema("Ecosystem", ["name"], [
        ("name", F("str", ["名稱", "廠商", "公司", "成員", "name"], required=True)),
        ("node", F("link", ["節點", "node"])),
        ("nodes", F("linklist", NODES_ALIASES)),
        ("role", F("enum", ["角色", "類別", "role"],
                   enum=["chipset", "module", "ODM", "OEM", "carrier", "cert-lab",
                         "integrator", "distributor", "standards", "component", "osat",
                         # AIDC 新增:晶圓代工、測試設備廠
                         "foundry", "test-equipment",
                         # robotics 新增:法人研究機構、工業電腦廠
                         "institute", "ipc"])),
        ("technologies", F("linklist", ["技術", "主要技術", "technologies"])),
        ("relationship_to_us", F("enum", ["與我關係", "關係", "relationship to us"],
                                 enum=["customer", "partner", "influencer", "competitor", "none"])),
        ("influence_on", F("linklist", ["影響客戶", "影響對象", "influence on"])),
        ("reference_design", F("bool", ["參考設計", "reference design"])),
        ("ticker", F("str", ["代號", "股票代號", "ticker"])),
    ], ["## 角色說明", "## 如何影響客戶的量測設備選型", DV_ECO_CP], domain="multi"),

    "account": schema("Account", ["name"], [
        ("name", F("str", ["客戶名稱", "名稱", "客戶", "name"], required=True)),
        ("node", F("link", ["節點", "node"])),
        ("nodes", F("linklist", NODES_ALIASES)),
        ("key_suppliers", F("linklist", ["主要供應商", "供應商", "key suppliers"])),
        ("key_customers", F("linklist", ["主要客戶", "key customers"])),
        ("region", F("str", ["地區", "region"])),
        ("ticker", F("str", ["代號", "股票代號", "ticker"])),
    ], ["## 客戶概述", "## 關鍵人物與決策鏈"], tail=False, domain="multi"),

    # ------------------------------------------------------------ skeleton / market layer
    "node": schema("Node", ["name"], [
        ("name", F("str", ["節點", "名稱", "name"], required=True)),
        ("layer", F("enum", ["層級", "layer"], enum=["L1", "L2", "L3", "L4", "L5", "X"])),
        ("upstream", F("linklist", ["上游", "upstream"])),
        ("downstream", F("linklist", ["下游", "downstream"])),
        ("typical_test_needs", F("list", ["典型量測需求", "typical test needs"])),
    ], ["## 說明", "## 此層典型量測需求", DV_NODE_ECO, DV_NODE_CP, DV_NODE_TRENDS], tail=False),

    "technology": schema("Technology", ["name"], [
        ("name", F("str", ["技術", "名稱", "name"], required=True)),
        ("standard_body", F("str", ["標準組織", "standard body"])),
        ("spec_milestones", F("list", ["標準時程", "里程碑", "spec milestones"])),
        ("maturity", F("enum", ["成熟度", "maturity"], enum=["emerging", "growth", "mature", "declining"])),
        ("affects_nodes", F("linklist", ["影響節點", "affects nodes"])),
        ("new_test_requirements", F("list", ["新增測試需求", "new test requirements"])),
    ], ["## 標準時程與重點", "## 新增或加嚴的量測需求", DV_CONCEPTS, DV_TREND_BY_TECH], domain="multi"),


    "concept": schema("Concept", ["name"], [
        ("name", F("str", ["名詞", "概念", "術語", "名稱", "name", "term"], required=True)),
        ("aliases", F("list", ["別名", "英文", "全名", "aliases"])),
        ("category", F("enum", ["類別", "分類", "category"],
                       enum=["radio", "protocol", "metric", "measurement", "standard", "device"])),
        ("one_liner", F("str", ["一句話", "一句話定義", "one liner", "one_liner"])),
        ("analogy", F("str", ["比喻", "生活比喻", "analogy"])),
        ("technologies", F("linklist", ["相關技術", "技術", "technologies"])),
        ("applications", F("linklist", ["相關應用", "應用", "applications"])),
        ("test_solutions", F("linklist", ["相關方案", "對應方案", "test solutions", "test_solutions"])),
        ("related_concepts", F("linklist", ["相關概念", "related concepts"])),
        ("audience", F("enum", ["對象", "讀者", "audience"], enum=["sales", "sales+FAE", "engineer"], default="sales")),
        ("review_status", F("enum", ["審閱狀態", "審閱", "review status", "review_status"],
                            enum=["draft", "reviewed"], default="draft")),
        ("reviewer", F("str", ["審閱者", "審閱人", "reviewer"])),
    ], ["## 30 秒版", "## 客戶會怎麼說", "## 我們量什麼、用什麼量", "## 常見誤解與不要說的話", "## 深入版(選填)"],
        domain="multi"),

    "trend": schema("Trend", ["name"], [
        ("name", F("str", ["趨勢", "名稱", "name"], required=True)),
        ("related_tech", F("linklist", ["相關技術", "技術", "related tech"])),
        ("affected_nodes", F("linklist", ["影響節點", "節點", "affected nodes"])),
        ("related_applications", F("linklist", ["相關應用", "應用", "related applications"])),
        ("stage", F("enum", ["階段", "stage"], enum=["watch", "emerging", "accelerating", "peak", "fading"])),
        ("time_to_demand", F("enum", ["需求時間", "time to demand"], enum=["0-6m", "6-18m", "18-36m", "36m+"])),
        ("market_impact", F("int", ["市場影響", "market impact"], rng=(1, 5))),
        ("measurement_impact", F("int", ["量測影響", "measurement impact"], rng=(1, 5))),
        ("our_fit", F("int", ["我方契合度", "契合度", "our fit"], rng=(1, 5))),
    ], ["## 趨勢描述", "## 為什麼對量測需求有影響", DV_SIGNALS, DV_TREND_CP, "## 我們的行動"]),

    "signal": schema("Signal", ["date", "title"], [
        ("title", F("virtual", ["標題", "主題", "名稱", "title"], required=True)),
        ("date", F("date", ["日期", "時間", "date"], required=True, default="today")),
        ("source_type", F("enum", ["來源類型", "source type"],
                          enum=["standard", "regulator", "report", "filing", "news",
                                "conference", "customer", "competitor", "internal"])),
        ("source", F("str", ["來源", "出處", "連結", "source"])),
        ("summary", F("str", ["摘要", "重點", "summary"], required=True)),
        ("related", F("linklist", ["相關", "相關卡片", "related"])),
        ("so_what", F("str", ["所以呢", "意涵", "對我們的意義", "so what", "so_what"], required=True)),
        ("reliability", F("enum", ["可靠度", "reliability"], enum=["high", "medium", "low"], default="medium")),
    ], ["## 重點(用自己的話寫,不貼原文)", "## So what?"], tail=False),
}

GLOBAL_ALIASES = {"body": ["body", "內文", "備註", "說明", "notes", "note", "description", "描述"]}

ENUM_ALIASES = {
    "domain": {"無線": "wireless", "無線通訊": "wireless", "資料中心": "AIDC", "ai資料中心": "AIDC",
               "機器人": "robotics", "機器人與智慧自動化": "robotics", "智慧自動化": "robotics"},
    "test_type": {
        "傳導": "conducted", "傳導式": "conducted", "傳導式射頻量測": "conducted", "射頻量測": "conducted",
        "ota": "OTA", "空中": "OTA", "空中量測": "OTA", "暗室": "OTA",
        "協定": "protocol", "信令": "protocol", "協定與信令": "protocol", "互通": "protocol",
        "通道模擬": "channel-emu", "衰落": "channel-emu", "通道": "channel-emu", "網路模擬": "channel-emu",
        "頻譜": "spectrum", "頻譜監測": "spectrum", "訊號分析": "spectrum",
        "功耗": "power", "電源": "power", "功耗與電源": "power",
        "ate": "ATE", "產線": "ATE", "參數化": "ATE", "量產測試": "ATE",
        # AIDC
        "si": "signal-integrity", "訊號完整性": "signal-integrity", "高速電氣": "signal-integrity",
        "pam4": "signal-integrity",
        "光學": "optical", "光學量測": "optical", "光電": "optical",
        "通道特性": "channel-char", "材料": "channel-char", "vna": "channel-char", "tdr": "channel-char",
        "晶圓": "wafer-probe", "晶圓測試": "wafer-probe", "探針": "wafer-probe",
        "pi": "power", "電源完整性": "power",
        # robotics
        "電磁相容": "EMC", "emc": "EMC", "emi": "EMC", "cispr": "EMC", "預相容": "EMC",
    },
    "tier": {
        "單機": "instrument", "單機量測": "instrument", "儀器": "instrument",
        "整合": "integrated", "整合方案": "integrated",
        "自動化": "automated", "自動化系統": "automated", "系統": "automated",
        "服務": "service", "服務方案": "service",
    },
    "automation": {"手動": "manual", "半自動": "semi", "全自動": "full", "自動": "full"},
    "price_band": {"入門": "entry", "低": "entry", "低階": "entry", "中階": "mid", "中": "mid",
                   "高階": "high", "高": "high"},
    "status": {"規劃中": "planning", "規劃": "planning", "可銷售": "available", "可販售": "available",
               "上市": "available", "停產": "EOL", "即將停產": "EOL"},
    "confidence": {"已驗證": "verified", "驗證": "verified", "推測": "assumed", "假設": "assumed",
                   "未驗證": "assumed"},
    "lifecycle": {
        "研發": "RD", "研發與設計驗證": "RD", "設計驗證": "RD",
        "認證": "Certification", "標準符合性與認證": "Certification",
        "量產": "Production", "量產測試": "Production", "產線": "Production",
        "可靠度": "Reliability", "品質與可靠度": "Reliability",
        "現場": "Field", "維運": "Field", "現場與維運": "Field",
    },
    "test_stage_now": {"研發": "RD", "認證": "cert", "量產": "production"},
    "volume_tier": {"低": "low", "中": "mid", "高": "high"},
    "role": {
        "晶片商": "chipset", "晶片": "chipset", "模組": "module", "模組廠": "module",
        "代工": "ODM", "品牌": "OEM", "電信商": "carrier",
        "認證實驗室": "cert-lab", "實驗室": "cert-lab", "整合商": "integrator",
        "代理": "distributor", "代理商": "distributor", "通路": "distributor",
        "標準組織": "standards", "協會": "standards",
        "元件": "component", "零組件": "component", "封測": "osat", "封測廠": "osat",
        "晶圓代工": "foundry", "代工廠": "foundry", "測試設備": "test-equipment", "測試機台": "test-equipment",
        # robotics
        "法人": "institute", "研究機構": "institute", "研究法人": "institute",
        "工業電腦": "ipc", "工控": "ipc", "工控電腦": "ipc",
    },
    "relationship_to_us": {"客戶": "customer", "夥伴": "partner", "合作": "partner", "影響者": "influencer",
                           "競爭": "competitor", "競品": "competitor", "無": "none"},
    "source_type": {"標準": "standard", "法規": "regulator", "報告": "report", "財報": "filing",
                    "法說": "filing", "新聞": "news", "展會": "conference", "研討會": "conference",
                    "客戶": "customer", "競品": "competitor", "內部": "internal"},
    "category": {"無線電": "radio", "射頻": "radio", "協定": "protocol", "指標": "metric", "量測": "measurement",
                 "量測方法": "measurement", "標準": "standard", "規範": "standard", "設備": "device", "裝置": "device"},
    "audience": {"業務": "sales", "業務+FAE": "sales+FAE", "工程師": "engineer"},
    "review_status": {"草稿": "draft", "已審閱": "reviewed", "已確認": "reviewed"},
    "reliability": {"高": "high", "中": "medium", "低": "low"},
    "stage": {"觀察": "watch", "萌芽": "emerging", "新興": "emerging", "加速": "accelerating",
              "高峰": "peak", "衰退": "fading"},
    "maturity": {"新興": "emerging", "成長": "growth", "成熟": "mature", "衰退": "declining"},
    "pricing_position": {"低": "low", "同等": "par", "持平": "par", "高": "premium", "高價": "premium"},
    # Opportunity
    "deal_stage": {"線索": "lead", "潛在": "lead", "初步接觸": "lead",
                   "合格": "qualified", "已確認需求": "qualified",
                   "提案": "proposal", "報價": "proposal",
                   "評估": "eval", "試用": "eval", "demo": "eval",
                   "議價": "negotiation", "談判": "negotiation",
                   "成交": "won", "贏單": "won", "贏": "won",
                   "失敗": "lost", "輸單": "lost", "輸": "lost", "丟單": "lost"},
    "size": {"小": "S", "中": "M", "大": "L"},
}
