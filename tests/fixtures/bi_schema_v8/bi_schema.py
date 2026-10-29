"""Single source of truth for BI card schemas (used by bi_ingest.py).

Add or change a field here and ingest, template generation and validation follow.
Field kinds: str, int, float, bool, date, enum, list, link, linklist, virtual
  - link / linklist  -> written as "[[name]]" (quoted) in YAML
  - virtual          -> used only for the file name, never written to YAML
  - list with allowed=[...] -> values are validated (aliases from ENUM_ALIASES[field] accepted)

v8 (AIDC): Ecosystem role += hyperscaler / power-system / thermal-system; RevenueFact += segment_name,
  yoy_pct, not_confirmed. Additive only. 運算鏈 CMP / 電力鏈 PWR / 散熱鏈 THM 由節點名稱(L2-PWR-...)推得,不是欄位。

v7 (aerospace): adds domain "aerospace" and 2 card types (SupplyLink, RevenueFact) -> 21 types.
  * DOMAINS 加入 aerospace。
  * Ecosystem role 加 material、operator;test_type 加 environmental。
  * Ecosystem / Account / CustomerProduct 新增 segment(list,允許值 SEGMENTS)。
  * Trend 新增 related_ecosystem(明確連結,取代只靠 technologies / nodes 的推算掛勾)。
  * SupplyLink:供應商→客戶的供貨關係 + 證據等級 A/B/C/D + 階段;CustomerProduct 的 ecosystem 只放有證據的成員。
  * RevenueFact:公司 / 區段 / 客戶 三層收入事實,標示 reported / media / estimated / target。
  * Dashboard §25-28 讀取以上欄位(Dashboard-Aerospace.md)。

v6 (steps 6-9): adds 7 card types - WinLoss, RoadmapRequest, Pitch, DemoScript, Battlecard, Contact, VisitLog.
  Existing 12 types unchanged. WinLoss/RoadmapRequest/VisitLog are single-domain; Pitch/DemoScript/Battlecard/Contact are multi.
v5 (mobile): adds domain "mobile"; Node becomes multi-domain (list) so mobile reuses Wireless nodes.
v4 (robotics): wireless + AIDC + robotics share one schema.
  * DOMAINS 加入 robotics。
  * Technology / TestSolution / Concept 改為多領域(domain 為清單),可跨領域重用。
  * CustomerProduct 新增 nodes / ecosystem / launch_date;公司型卡片新增 nodes。
  * 新增 Opportunity 卡(Application -> 我方 TestSolution -> Opportunity 鏈)。
  * test_type 加 EMC;Ecosystem role 加 institute、ipc。
"""


def F(kind, aliases=(), required=False, enum=None, default=None, rng=None, allowed=None):
    return {"kind": kind, "aliases": list(aliases), "required": required,
            "enum": enum, "default": default, "range": rng, "allowed": allowed}


# --- domain: 同一套卡片同時服務 wireless、AIDC、robotics -----------------------------
# 單一領域的卡片(Trend/Application/CustomerProduct/Signal/Opportunity)用 enum;Node 自 v5 起為 list;
# 公司型(Account/Ecosystem/Competitor)與可跨領域重用的資產(Technology/TestSolution/Concept)用 list,
# 例如 [wireless, robotics]。舊卡片沒有 domain 欄位時,Dashboard 一律視為 wireless。
DOMAINS = ["wireless", "AIDC", "robotics", "mobile", "aerospace"]
# v7: 衛星供應鏈的區段(一家公司可跨多個區段,所以是 list)
SEGMENTS = ["space", "gateway", "ut", "launch", "mro"]
EVIDENCE_GRADES = ["A", "B", "C", "D"]  # A 原廠/具名確認 B 可信報導或公司說明 C 產品能力 D 傳聞/待確認
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

# --- v6: 步驟 6–9 新卡種的反向視圖 -------------------------------------------------------
DV_WL_RR = ('## 由此產生的 Roadmap Request\n```dataview\nTABLE gap_type AS 缺口類型, impact AS 影響, request_status AS 狀態\n'
            'FROM "BI/RoadmapRequest"\nWHERE contains(default(source_win_loss, []), this.file.link)\nSORT impact DESC\n```')
DV_RR_WL = ('## 來源 Win-Loss\n```dataview\nTABLE outcome AS 結果, primary_reason AS 主因\nFROM "BI/WinLoss"\n'
            'WHERE contains(default(this.source_win_loss, []), file.link)\n```')
DV_CONTACT_VISITS = ('## 拜訪紀錄\n```dataview\nTABLE date, visit_type AS 類型, summary AS 摘要\nFROM "BI/VisitLog"\n'
                     'WHERE contains(default(contacts, []), this.file.link)\nSORT date DESC\n```')

# --- v7: 供貨關係 / 收入事實 / 明確趨勢連結的反向視圖 ------------------------------------
DV_ECO_TRENDS = ('## 相關趨勢(明確連結 related_ecosystem)\n```dataview\nTABLE stage AS 階段, time_to_demand AS 需求時間, measurement_impact AS 量測影響\n'
                 'FROM "BI/Trend"\nWHERE contains(default(related_ecosystem, []), this.file.link)\n'
                 'SORT measurement_impact DESC\n```')
DV_ECO_SUPPLY = ('## 供貨關係(SupplyLink)\n```dataview\nTABLE supplier AS 供應商, customer AS 客戶, evidence_grade AS 等級, supply_stage AS 階段, product AS 交付品\n'
                 'FROM "BI/SupplyLink"\nWHERE supplier = this.file.link OR customer = this.file.link\n'
                 'SORT evidence_grade ASC\n```')
DV_CP_SUPPLY = ('## 供貨證據(SupplyLink,A/B 才算已確認)\n```dataview\nTABLE supplier AS 供應商, evidence_grade AS 等級, supply_stage AS 階段, product AS 交付品, source AS 來源\n'
                'FROM "BI/SupplyLink"\nWHERE contains(default(customer_products, []), this.file.link)\n'
                'SORT evidence_grade ASC\n```')
DV_REV = ('## 收入事實(RevenueFact)\n```dataview\nTABLE period AS 期間, rev_layer AS 層級, customer AS 客戶, amount AS 金額, share_pct AS 占比, basis AS 口徑\n'
          'FROM "BI/RevenueFact"\nWHERE company = this.file.link\nSORT period DESC\n```')

NODES_ALIASES = ["涉及節點", "節點清單", "nodes"]

SCHEMAS = {
    # ------------------------------------------------------------ opportunity layer (v4)
    # Application -> 我方 TestSolution(vendor 空白)-> Opportunity。
    # our_solutions 應連到 vendor 空白的方案;schema 無法強制,由 Dashboard §29 檢查(§18 只計連到我方方案的商機)。
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
                              "EMC",
                              # aerospace 新增:環境與輻射驗證(熱真空、振動、輻射);相控陣校正與 OTA 沿用 OTA
                              "environmental"])),
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
        ("segment", F("list", ["區段", "segment"], allowed=SEGMENTS)),
    ], ["## 產品概述", "## 時程(研發、認證、量產)", "## 推論的量測需求",
        DV_CP_ECO, DV_CP_SUPPLY, DV_CP_TRENDS, DV_CP_OPPS]),

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
                         "institute", "ipc",
                         # aerospace 新增:材料(磊晶/基板/CCL/銲料)、衛星營運商
                         "material", "operator",
                         # AIDC 新增:雲端業者、電力系統商、散熱系統商
                         "hyperscaler", "power-system", "thermal-system"])),
        ("segment", F("list", ["區段", "segment"], allowed=SEGMENTS)),
        ("technologies", F("linklist", ["技術", "主要技術", "technologies"])),
        ("relationship_to_us", F("enum", ["與我關係", "關係", "relationship to us"],
                                 enum=["customer", "partner", "influencer", "competitor", "none"])),
        ("influence_on", F("linklist", ["影響客戶", "影響對象", "influence on"])),
        ("reference_design", F("bool", ["參考設計", "reference design"])),
        ("ticker", F("str", ["代號", "股票代號", "ticker"])),
    ], ["## 角色說明", "## 如何影響客戶的量測設備選型", DV_ECO_CP, DV_ECO_SUPPLY, DV_ECO_TRENDS, DV_REV],
        domain="multi"),

    "account": schema("Account", ["name"], [
        ("name", F("str", ["客戶名稱", "名稱", "客戶", "name"], required=True)),
        ("node", F("link", ["節點", "node"])),
        ("nodes", F("linklist", NODES_ALIASES)),
        ("key_suppliers", F("linklist", ["主要供應商", "供應商", "key suppliers"])),
        ("key_customers", F("linklist", ["主要客戶", "key customers"])),
        ("region", F("str", ["地區", "region"])),
        ("segment", F("list", ["區段", "segment"], allowed=SEGMENTS)),
        ("ticker", F("str", ["代號", "股票代號", "ticker"])),
    ], ["## 客戶概述", "## 關鍵人物與決策鏈", DV_REV], tail=False, domain="multi"),

    # ------------------------------------------------------------ skeleton / market layer
    "node": schema("Node", ["name"], [
        ("name", F("str", ["節點", "名稱", "name"], required=True)),
        ("layer", F("enum", ["層級", "layer"], enum=["L1", "L2", "L3", "L4", "L5", "X"])),
        ("upstream", F("linklist", ["上游", "upstream"])),
        ("downstream", F("linklist", ["下游", "downstream"])),
        ("typical_test_needs", F("list", ["典型量測需求", "typical test needs"])),
    ], ["## 說明", "## 此層典型量測需求", DV_NODE_ECO, DV_NODE_CP, DV_NODE_TRENDS], tail=False, domain="multi"),

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
        ("related_ecosystem", F("linklist", ["相關生態系", "受影響供應商", "related ecosystem", "related_ecosystem"])),
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
    # ---- v6: Win-Loss / Roadmap Request / Sales Enablement / Contact / Visit Log ----
    # ---- step 6: Win-Loss (links to the existing Opportunity card; Opportunity.deal_stage won/lost + lost_to already exist)
    "win_loss": schema("WinLoss", ["name"], [
        ("name", F("str", ["案例名稱", "名稱", "name"], required=True)),
        ("opportunity", F("link", ["商機", "opportunity"])),
        ("account", F("link", ["客戶", "account"])),
        ("outcome", F("enum", ["結果", "outcome"], enum=["won", "lost", "no-decision"])),
        ("decided_date", F("date", ["決定日", "結案日", "decided date", "decided_date"])),
        ("applications", F("linklist", ["對應應用", "應用", "applications"])),
        ("our_solutions", F("linklist", ["我方方案", "our solutions", "our_solutions"])),
        ("competitors", F("linklist", ["競爭對手", "competitors"])),
        ("winner", F("link", ["勝出者", "得標廠商", "winner"])),
        ("primary_reason", F("enum", ["主要原因", "原因", "primary reason", "primary_reason"],
                             enum=["price", "performance", "features", "relationship", "timing",
                                   "incumbent", "budget", "other"])),
        ("gaps", F("list", ["缺口", "gaps"])),
        ("lessons", F("list", ["心得", "lessons"])),
    ], ["## 結果摘要", "## 原因分析(客戶怎麼說 / 我們怎麼看)", "## 缺口 → Roadmap Request", DV_WL_RR,
        "## 可複製的做法"], tail=True),

    # ---- step 7: Roadmap Request
    "roadmap_request": schema("RoadmapRequest", ["name"], [
        ("name", F("str", ["需求名稱", "名稱", "name"], required=True)),
        ("applications", F("linklist", ["對應應用", "應用", "applications"])),
        ("our_solutions", F("linklist", ["我方方案", "our solutions", "our_solutions"])),
        ("competitors", F("linklist", ["相關競品", "competitors"])),
        ("source_win_loss", F("linklist", ["來源案例", "source win loss", "source_win_loss"])),
        ("source_opportunities", F("linklist", ["來源商機", "source opportunities", "source_opportunities"])),
        ("gap_type", F("enum", ["缺口類型", "gap type", "gap_type"],
                       enum=["feature", "performance", "price", "integration", "certification", "service"])),
        ("impact", F("int", ["影響程度", "影響", "impact"], rng=(1, 5))),
        ("customer_count", F("int", ["受影響客戶數", "客戶數", "customer count", "customer_count"])),
        ("request_status", F("enum", ["需求狀態", "request status", "request_status"],
                             enum=["idea", "submitted", "accepted", "planned", "shipped", "declined"],
                             default="idea")),
        ("target_release", F("str", ["目標版本", "target release", "target_release"])),
        ("owner", F("str", ["負責人", "owner"])),
    ], ["## 缺口描述", "## 客戶需求證據", "## 影響評估(商機數、被拒原因、營收)", DV_RR_WL, "## 建議方案與替代",
        "## 回覆與時程"]),

    # ---- step 8: Sales Enablement (Pitch / DemoScript / Battlecard)
    "pitch": schema("Pitch", ["name"], [
        ("name", F("str", ["簡報名稱", "名稱", "name"], required=True)),
        ("pitch_audience", F("enum", ["對象", "pitch audience", "pitch_audience"],
                             enum=["sales", "customer-engineer", "customer-manager", "executive"])),
        ("applications", F("linklist", ["對應應用", "應用", "applications"])),
        ("our_solutions", F("linklist", ["我方方案", "our solutions", "our_solutions"])),
        ("technologies", F("linklist", ["技術", "technologies"])),
        ("concepts", F("linklist", ["白話概念", "概念", "concepts"])),
        ("accounts", F("linklist", ["適用客戶", "accounts"])),
        ("duration_min", F("int", ["時間(分鐘)", "分鐘", "duration min", "duration_min"], rng=(1, 180))),
        ("content_status", F("enum", ["內容狀態", "content status", "content_status"],
                             enum=["draft", "reviewed", "in-use"], default="draft")),
        ("owner", F("str", ["負責人", "owner"])),
    ], ["## 一句話價值主張", "## 客戶痛點與切入問題", "## 三個重點", "## 證據與案例", "## 下一步(CTA)"],
        domain="multi"),

    "demo_script": schema("DemoScript", ["name"], [
        ("name", F("str", ["腳本名稱", "名稱", "name"], required=True)),
        ("our_solutions", F("linklist", ["我方方案", "our solutions", "our_solutions"])),
        ("applications", F("linklist", ["對應應用", "應用", "applications"])),
        ("duration_min", F("int", ["時間(分鐘)", "分鐘", "duration min", "duration_min"], rng=(1, 480))),
        ("demo_env", F("list", ["展示環境", "環境", "demo env", "demo_env"])),
        ("content_status", F("enum", ["內容狀態", "content status", "content_status"],
                             enum=["draft", "reviewed", "in-use"], default="draft")),
        ("owner", F("str", ["負責人", "owner"])),
    ], ["## 目標與聽眾", "## 環境與準備", "## 步驟(操作 → 要說的話 → 預期畫面)", "## 常見狀況與備案", "## 收尾與下一步"],
        domain="multi"),

    "battlecard": schema("Battlecard", ["name"], [
        ("name", F("str", ["名稱", "name"], required=True)),
        ("competitor", F("link", ["競爭對手", "對手", "competitor"], required=True)),
        ("our_solutions", F("linklist", ["我方方案", "our solutions", "our_solutions"])),
        ("applications", F("linklist", ["對應應用", "應用", "applications"])),
        ("competing_solutions", F("linklist", ["對手方案", "競品方案", "competing solutions"])),
        ("our_advantages", F("list", ["我方優勢", "our advantages", "our_advantages"])),
        ("our_weaknesses", F("list", ["我方弱點", "our weaknesses", "our_weaknesses"])),
        ("content_status", F("enum", ["內容狀態", "content status", "content_status"],
                             enum=["draft", "reviewed", "in-use"], default="draft")),
        ("owner", F("str", ["負責人", "owner"])),
    ], ["## 一句話定位", "## 差異化賣點(附證據)", "## 對手常用說法與回應", "## 我們的弱點與誠實回應",
        "## 陷阱問題(引導客戶評估)", "## Discovery Questions"], domain="multi"),

    # ---- step 9: Contact / VisitLog (Account and Opportunity already exist). No email/phone fields on purpose.
    "contact": schema("Contact", ["name"], [
        ("name", F("str", ["姓名", "名稱", "name"], required=True)),
        ("account", F("link", ["客戶", "公司", "account"])),
        ("job_title", F("str", ["職稱", "job title", "job_title"])),
        ("contact_function", F("enum", ["職能", "部門", "contact function", "contact_function"],
                               enum=["procurement", "rd", "test", "quality", "management", "sales", "other"])),
        ("decision_role", F("enum", ["決策角色", "decision role", "decision_role"],
                            enum=["decision", "influencer", "user", "gatekeeper"])),
        ("relationship_status", F("enum", ["關係", "relationship status", "relationship_status"],
                                  enum=["champion", "supporter", "neutral", "blocker", "unknown"],
                                  default="unknown")),
        ("reports_to", F("link", ["主管", "reports to", "reports_to"])),
        ("applications", F("linklist", ["關注應用", "應用", "applications"])),
        ("last_contact", F("date", ["最近聯絡", "last contact", "last_contact"])),
    ], ["## 角色與關注點", "## 與我們的關係", DV_CONTACT_VISITS], tail=False, domain="multi"),

    "visit_log": schema("VisitLog", ["date", "title"], [
        ("title", F("virtual", ["標題", "主題", "title"], required=True)),
        ("date", F("date", ["日期", "date"], required=True, default="today")),
        ("account", F("link", ["客戶", "account"])),
        ("contacts", F("linklist", ["對象", "聯絡人", "contacts"])),
        ("opportunity", F("link", ["商機", "opportunity"])),
        ("applications", F("linklist", ["討論應用", "應用", "applications"])),
        ("our_solutions", F("linklist", ["討論方案", "our solutions", "our_solutions"])),
        ("visit_type", F("enum", ["類型", "visit type", "visit_type"],
                         enum=["visit", "call", "demo", "workshop", "conference", "email"])),
        ("summary", F("str", ["摘要", "重點", "summary"], required=True)),
        ("next_steps", F("list", ["下一步", "next steps", "next_steps"])),
        ("follow_up_date", F("date", ["跟進日", "follow up date", "follow_up_date"])),
    ], ["## 討論重點", "## 客戶需求與痛點(新發現)", "## 下一步", "## 回饋 → Signal / Roadmap Request"], tail=False),

    # ---- v7: 供貨關係與收入事實(航太衛星報告的核心原則:產品→客戶/任務→量產階段→收入,逐層要有證據)
    # SupplyLink:一條「供應商→客戶」的供貨關係。只有 A/B 級才算已確認,Dashboard §25 據此計入生態系。
    # 建議檔名:<供應商>→<客戶>-<交付品>,例如 啟碁→SpaceX-路由器。
    "supply_link": schema("SupplyLink", ["name"], [
        ("name", F("str", ["供貨關係", "名稱", "name"], required=True)),
        ("supplier", F("link", ["供應商", "supplier"], required=True)),
        ("customer", F("link", ["客戶", "品牌", "營運商", "customer"])),
        ("product", F("str", ["交付品", "產品", "product"])),
        ("platform", F("str", ["平台", "專案", "platform"])),
        ("segment", F("list", ["區段", "segment"], allowed=SEGMENTS)),
        ("nodes", F("linklist", NODES_ALIASES)),
        ("technologies", F("linklist", ["技術", "technologies"])),
        ("customer_products", F("linklist", ["客戶產品", "對應客戶產品", "customer products", "customer_products"])),
        ("evidence_grade", F("enum", ["證據等級", "等級", "evidence grade", "evidence_grade"],
                             enum=EVIDENCE_GRADES, default="D")),
        ("supply_stage", F("enum", ["供貨階段", "商業化階段", "supply stage", "supply_stage"],
                           enum=["demo", "sample", "cert", "pilot", "mass"])),
        ("source", F("str", ["來源", "出處", "連結", "source"])),
        ("source_date", F("date", ["來源日期", "報導日期", "source date", "source_date"])),
        ("not_confirmed", F("list", ["尚待確認", "待確認", "not confirmed", "not_confirmed"])),
    ], ["## 供貨關係說明", "## 證據與來源(只寫來源明確說的,不外推)", "## 尚待確認"], domain="multi"),

    # RevenueFact:一筆收入數字。rev_layer 分公司 / 區段(衛星) / 客戶(SpaceX)三層,三層不可互相替代。
    # share_pct = 占上一層的比例(區段占公司、客戶占區段);沒有客戶層的資料就不要填,Dashboard §28 會標「未揭露」。
    "revenue_fact": schema("RevenueFact", ["name"], [
        ("name", F("str", ["名稱", "name"], required=True)),
        ("company", F("link", ["公司", "company"], required=True)),
        ("period", F("str", ["期間", "period"], required=True)),
        ("rev_layer", F("enum", ["收入層級", "層級", "rev layer", "rev_layer"],
                        enum=["company", "segment", "customer"], required=True)),
        ("customer", F("link", ["客戶", "customer"])),
        ("segment_name", F("str", ["區段名稱", "產品別", "segment name", "segment_name"])),  # v8 AIDC
        ("amount", F("float", ["金額", "amount"])),
        ("share_pct", F("float", ["占比", "占上層比例", "share pct", "share_pct"], rng=(0, 100))),
        ("yoy_pct", F("float", ["年增", "年增率", "yoy", "yoy pct", "yoy_pct"])),  # v8 AIDC
        ("unit", F("str", ["單位", "unit"], default="億TWD")),
        ("basis", F("enum", ["口徑", "basis"], enum=["reported", "media", "estimated", "target"],
                    default="estimated")),
        ("source", F("str", ["來源", "出處", "連結", "source"])),
        ("source_date", F("date", ["來源日期", "source date", "source_date"])),
        ("not_confirmed", F("list", ["不可比較", "未確認", "not confirmed", "not_confirmed"])),  # v8 AIDC
    ], ["## 口徑說明", "## 不可比較之處"], domain="multi"),
}

GLOBAL_ALIASES = {"body": ["body", "內文", "備註", "說明", "notes", "note", "description", "描述"]}

ENUM_ALIASES = {
    "domain": {"無線": "wireless", "無線通訊": "wireless", "資料中心": "AIDC", "ai資料中心": "AIDC",
               "機器人": "robotics", "機器人與智慧自動化": "robotics", "智慧自動化": "robotics",
               "行動通訊": "mobile", "行動終端": "mobile", "手機": "mobile",
               "航太": "aerospace", "衛星": "aerospace", "太空": "aerospace", "低軌": "aerospace",
               "航太衛星": "aerospace", "太空與衛星": "aerospace"},
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
        # aerospace
        "環境": "environmental", "環境驗證": "environmental", "熱真空": "environmental",
        "tvac": "environmental", "振動": "environmental", "輻射": "environmental", "輻射驗證": "environmental",
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
        # aerospace
        "材料": "material", "材料廠": "material", "磊晶": "material", "基板": "material", "銲料": "material",
        "營運商": "operator", "衛星營運商": "operator", "星座營運商": "operator",
        # AIDC
        "雲端業者": "hyperscaler", "超大規模雲端": "hyperscaler",
        "電力系統": "power-system", "電力設備": "power-system",
        "散熱系統": "thermal-system", "液冷": "thermal-system", "冷卻": "thermal-system",
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
    # ---- v6 ----
    "outcome": {"贏": "won", "成交": "won", "贏單": "won", "得標": "won", "輸": "lost", "丟單": "lost", "輸單": "lost",
                "失標": "lost", "無決定": "no-decision", "擱置": "no-decision"},
    "primary_reason": {"價格": "price", "效能": "performance", "功能": "features", "關係": "relationship",
                       "時程": "timing", "既有廠商": "incumbent", "預算": "budget", "其他": "other"},
    "gap_type": {"功能": "feature", "效能": "performance", "價格": "price", "整合": "integration",
                 "認證": "certification", "服務": "service"},
    "request_status": {"構想": "idea", "已提出": "submitted", "已接受": "accepted", "排程": "planned",
                       "已上市": "shipped", "婉拒": "declined"},
    "pitch_audience": {"業務": "sales", "客戶工程師": "customer-engineer", "客戶主管": "customer-manager",
                       "高階主管": "executive"},
    "content_status": {"草稿": "draft", "已審閱": "reviewed", "使用中": "in-use"},
    "contact_function": {"採購": "procurement", "研發": "rd", "測試": "test", "品保": "quality",
                         "主管": "management", "業務": "sales", "其他": "other"},
    "decision_role": {"決策者": "decision", "影響者": "influencer", "使用者": "user", "守門人": "gatekeeper"},
    "relationship_status": {"擁護者": "champion", "支持": "supporter", "中立": "neutral", "反對": "blocker",
                            "未知": "unknown"},
    "visit_type": {"拜訪": "visit", "電話": "call", "展示": "demo", "工作坊": "workshop", "展會": "conference",
                   "郵件": "email"},
    # ---- v7 ----
    "segment": {"星載": "space", "衛星": "space", "酬載": "space", "地面站": "gateway", "地面": "gateway",
                "終端": "ut", "使用者終端": "ut", "發射": "launch", "火箭": "launch",
                "維修": "mro", "航空": "mro", "民航": "mro"},
    "evidence_grade": {"原廠確認": "A", "官方": "A", "具名確認": "A", "可信報導": "B", "公司說明": "B", "報導": "B",
                       "產品能力": "C", "能力": "C", "傳聞": "D", "待驗證": "D", "待確認": "D"},
    "supply_stage": {"展示": "demo", "送樣": "sample", "認證": "cert", "試產": "pilot", "量產": "mass"},
    "rev_layer": {"公司": "company", "整體": "company", "總營收": "company", "區段": "segment", "衛星": "segment",
                  "產品": "segment", "客戶": "customer"},
    "basis": {"財報": "reported", "公司揭露": "reported", "已公布": "reported", "報導": "media", "媒體": "media",
              "報導口徑": "media", "推算": "estimated", "估算": "estimated", "估計": "estimated",
              "目標": "target", "展望": "target", "預期": "target"},
}
