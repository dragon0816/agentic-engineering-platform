---
domain: robotics
---
# BI Dashboard — Robotics

> 切換領域:改上方 frontmatter 的 `domain`(wireless / AIDC / robotics)。沒有 `domain` 欄位的舊卡視為 wireless。
> `domain` 可能是字串或清單,查詢一律用 `contains` / `includes`,兩種寫法都能比對。
> 需要 Dataview 外掛並開啟 JavaScript Queries。

## 1. 趨勢優先度(量測影響 × 我方契合度)
```dataview
TABLE stage AS 階段, time_to_demand AS 需求時間, measurement_impact AS 影響, our_fit AS 契合, measurement_impact * our_fit AS 優先度
FROM "BI/Trend"
WHERE stage != "fading" AND contains(default(domain, "wireless"), this.domain)
SORT measurement_impact * our_fit DESC
```

## 2. 客戶產品上市時程(預測需求)
```dataview
TABLE account AS 客戶, node AS 節點, technologies AS 技術, launch_date AS 上市日, launch_window AS 上市時程, test_stage_now AS 目前階段
FROM "BI/CustomerProduct"
WHERE contains(default(domain, "wireless"), this.domain)
SORT launch_date ASC
```

## 3. 各價值鏈節點的生態系成員
```dataview
TABLE rows.file.link AS 成員, rows.role AS 角色, rows.relationship_to_us AS 與我關係
FROM "BI/Ecosystem"
WHERE contains(default(domain, "wireless"), this.domain)
FLATTEN default(nodes, [node]) AS n
GROUP BY n
```

## 4. 節點 × 技術 矩陣(客戶產品數)
```dataviewjs
const D = dv.current().domain ?? "wireless";
const A = (x) => x == null ? [] : (Array.isArray(x) ? x : (typeof x.array === "function" ? x.array() : [x]));
const inD = (p) => A(p.domain ?? "wireless").includes(D);
const nm = (l) => l ? String(l.path).split("/").pop().replace(/\.md$/, "") : "";
const nodesOf = (p) => { const s = new Set(A(p.nodes).map(nm)); if (p.node) s.add(nm(p.node)); return s; };
const nodes = dv.pages('"BI/Node"').where(n => inD(n) || n.layer == "X").sort(n => n.file.name).array();
const techs = dv.pages('"BI/Technology"').where(inD).sort(t => t.file.name).array();
const cps = dv.pages('"BI/CustomerProduct"').where(inD).array();
const rows = nodes.map(n => [
  n.file.link,
  ...techs.map(t => cps.filter(cp =>
      nodesOf(cp).has(n.file.name) &&
      A(cp.technologies).some(x => nm(x) == t.file.name)
  ).length)
]);
dv.table(["節點", ...techs.map(t => t.file.name)], rows);
```

## 5. 近期訊號
```dataview
TABLE date, summary AS 摘要, so_what AS 所以呢, reliability AS 可靠度
FROM "BI/Signal"
WHERE contains(default(domain, "wireless"), this.domain)
SORT date DESC
LIMIT 10
```

## 6. 缺口:Application × 我方方案 / 對手方案
我方方案 = TestSolution 的 `vendor` 空白。「對手有、我方無」是最需要先處理的缺口。
```dataviewjs
const D = dv.current().domain ?? "wireless";
const A = (x) => x == null ? [] : (Array.isArray(x) ? x : (typeof x.array === "function" ? x.array() : [x]));
const inD = (p) => A(p.domain ?? "wireless").includes(D);
const nm = (l) => l ? String(l.path).split("/").pop().replace(/\.md$/, "") : "";
const sols = dv.pages('"BI/TestSolution"').array();
const covers = (s, app) => A(s.applications).some(l => nm(l) == app.file.name);
const rows = dv.pages('"BI/Application"').where(inD).sort(a => a.priority, "desc").array().map(a => {
  const mine = sols.filter(s => !s.vendor && covers(s, a)).length;
  const theirs = sols.filter(s => !!s.vendor && covers(s, a)).length;
  return [a.file.link, a.priority, a.lifecycle, mine, theirs,
    mine == 0 ? (theirs > 0 ? "🔴 對手有、我方無" : "⚠ 全無") : "OK"];
});
dv.table(["應用", "優先度", "階段", "我方方案", "對手方案", "狀態"], rows);
```

## 6b. 競品覆蓋矩陣(每格 = 該廠商在此應用的方案數)
```dataviewjs
const D = dv.current().domain ?? "wireless";
const A = (x) => x == null ? [] : (Array.isArray(x) ? x : (typeof x.array === "function" ? x.array() : [x]));
const inD = (p) => A(p.domain ?? "wireless").includes(D);
const nm = (l) => l ? String(l.path).split("/").pop().replace(/\.md$/, "") : "";
const MINE = "R&S(我方)";
const sols = dv.pages('"BI/TestSolution"').array();
const comps = [MINE, ...dv.pages('"BI/Competitor"').where(inD).map(c => c.file.name).array()];
const vend = (s) => s.vendor ? nm(s.vendor) : MINE;
const rows = dv.pages('"BI/Application"').where(inD).sort(a => a.priority, "desc").array().map(a => [
  a.file.link,
  ...comps.map(c => sols.filter(s => vend(s) == c &&
    A(s.applications).some(l => nm(l) == a.file.name)).length)
]);
dv.table(["應用", ...comps], rows);
```

## 7. 推測內容比例(待驗證)
```dataview
TABLE length(rows) AS 筆數
FROM "BI"
WHERE confidence AND contains(default(domain, "wireless"), this.domain)
GROUP BY confidence
```

## 8. 資料過期提醒(超過 90 天未更新)
```dataview
LIST
FROM "BI/Ecosystem" OR "BI/Technology" OR "BI/Trend" OR "BI/CustomerProduct"
WHERE date(today) - file.mtime > dur(90 days) AND contains(default(domain, "wireless"), this.domain)
SORT file.mtime ASC
```

## 9. 方案層總覽(Test Solution)
```dataview
TABLE applications AS 應用, test_type AS 測試類型, tier AS 型態, automation AS 自動化, price_band AS 價格帶, status AS 狀態
FROM "BI/TestSolution"
WHERE contains(default(domain, "wireless"), this.domain)
SORT status ASC
```

## 10. 趨勢 → 應用 → 方案 覆蓋檢查
```dataviewjs
const D = dv.current().domain ?? "wireless";
const A = (x) => x == null ? [] : (Array.isArray(x) ? x : (typeof x.array === "function" ? x.array() : [x]));
const inD = (p) => A(p.domain ?? "wireless").includes(D);
const nm = (l) => l ? String(l.path).split("/").pop().replace(/\.md$/, "") : "";
const trends = dv.pages('"BI/Trend"').where(inD).sort(t => t.measurement_impact * t.our_fit, "desc").array();
const apps = dv.pages('"BI/Application"').where(inD).array();
const sols = dv.pages('"BI/TestSolution"').where(p => !p.vendor).array();
const rows = trends.map(t => {
  const a = apps.filter(x => A(x.trends).some(l => nm(l) == t.file.name));
  const s = sols.filter(x => A(x.applications).some(l => a.some(y => y.file.name == nm(l))));
  const status = a.length == 0 ? "⚠ 無對應 Application" : (s.length == 0 ? "⚠ 無對應方案" : "OK");
  return [t.file.link, t.measurement_impact * t.our_fit, t.stage, a.length, s.length, status];
});
dv.table(["趨勢", "優先度", "階段", "Application 數", "方案數", "狀態"], rows);
```

## 11. 競品方案對照(我方 R&S 方案 vs 對手方案)
```dataview
TABLE rows.file.link AS 我方方案, theirs.vendor AS 對手廠商
FROM "BI/TestSolution"
WHERE !vendor AND contains(default(domain, "wireless"), this.domain)
FLATTEN competing_solutions AS theirs
GROUP BY theirs
```

## 11b. 已建檔的對手方案(依應用)
```dataview
TABLE vendor AS 廠商, applications AS 應用, test_type AS 類型, tier AS 型態, price_band AS 價格帶
FROM "BI/TestSolution"
WHERE vendor AND contains(default(domain, "wireless"), this.domain)
SORT vendor ASC
```

## 12. 供應商依賴排行(哪些 Ecosystem 被最多客戶依賴)
```dataview
TABLE length(rows) AS 客戶數, rows.file.link AS 客戶
FROM "BI/Account"
WHERE contains(default(domain, "wireless"), this.domain)
FLATTEN key_suppliers AS supplier
GROUP BY supplier
SORT length(rows) DESC
```

## 12b. Ecosystem 被客戶產品採用數(CustomerProduct.ecosystem)
```dataview
TABLE length(rows) AS 客戶產品數, rows.file.link AS 客戶產品
FROM "BI/CustomerProduct"
WHERE contains(default(domain, "wireless"), this.domain)
FLATTEN ecosystem AS eco
GROUP BY eco
SORT length(rows) DESC
```

## 13. Ecosystem 依角色分布
```dataview
TABLE length(rows) AS 數量, rows.file.link AS 廠商
FROM "BI/Ecosystem"
WHERE contains(default(domain, "wireless"), this.domain)
GROUP BY role
SORT length(rows) DESC
```

## 14. 缺少 Concept 解釋的 Technology(Sales Enablement 缺口)
```dataviewjs
const D = dv.current().domain ?? "wireless";
const A = (x) => x == null ? [] : (Array.isArray(x) ? x : (typeof x.array === "function" ? x.array() : [x]));
const inD = (p) => A(p.domain ?? "wireless").includes(D);
const nm = (l) => l ? String(l.path).split("/").pop().replace(/\.md$/, "") : "";
const concepts = dv.pages('"BI/Concept"').array();
const rows = dv.pages('"BI/Technology"').where(inD).sort(t => t.file.name).array().map(t => {
  const cs = concepts.filter(c => A(c.technologies).some(l => nm(l) == t.file.name));
  const reviewed = cs.filter(c => c.review_status == "reviewed").length;
  const status = cs.length == 0 ? "⚠ 缺 Concept" : (reviewed == 0 ? "⚠ 尚無已審閱" : "OK");
  return [t.file.link, cs.length, reviewed, status];
});
dv.table(["技術", "Concept 數", "已審閱", "狀態"], rows);
```

## 15. Concept 審閱佇列(請業務試讀後改為 reviewed)
```dataview
TABLE category AS 類別, one_liner AS 一句話, reviewer AS 審閱者
FROM "BI/Concept"
WHERE review_status != "reviewed" AND contains(default(domain, "wireless"), this.domain)
SORT file.name ASC
```

## 16. 客戶產品 × 生態系 × 趨勢 掛勾總表(含資料完整度)
趨勢由 `technologies`、`nodes` 與 Trend 的 `related_tech`、`affected_nodes` 交集推得;欄位沒填齊就會漏,請看最右欄。
```dataviewjs
const D = dv.current().domain ?? "wireless";
const A = (x) => x == null ? [] : (Array.isArray(x) ? x : (typeof x.array === "function" ? x.array() : [x]));
const inD = (p) => A(p.domain ?? "wireless").includes(D);
const nm = (l) => l ? String(l.path).split("/").pop().replace(/\.md$/, "") : "";
const nodesOf = (p) => { const s = new Set(A(p.nodes).map(nm)); if (p.node) s.add(nm(p.node)); return s; };
const prio = (t) => (t.measurement_impact ?? 0) * (t.our_fit ?? 0);
const trends = dv.pages('"BI/Trend"').where(inD).array();
const rows = dv.pages('"BI/CustomerProduct"').where(inD).sort(c => c.launch_date).array().map(cp => {
  const ns = nodesOf(cp), ts = new Set(A(cp.technologies).map(nm));
  const hit = trends.filter(t =>
    A(t.related_tech).some(l => ts.has(nm(l))) || A(t.affected_nodes).some(l => ns.has(nm(l)))
  ).sort((a, b) => prio(b) - prio(a));
  const missing = [];
  if (ns.size == 0) missing.push("節點");
  if (ts.size == 0) missing.push("技術");
  if (A(cp.ecosystem).length == 0) missing.push("生態系");
  return [cp.file.link, cp.account, cp.launch_date ?? cp.launch_window, A(cp.ecosystem).length,
    hit.length, hit.length ? hit[0].file.link : "-",
    missing.length ? "⚠ 缺 " + missing.join("、") : "OK"];
});
dv.table(["客戶產品", "客戶", "上市", "生態系成員數", "相關趨勢數", "最高優先趨勢", "資料完整度"], rows);
```

## 17. 商機漏斗(依階段)
```dataview
TABLE length(rows) AS 筆數, rows.file.link AS 商機
FROM "BI/Opportunity"
WHERE contains(default(domain, "wireless"), this.domain)
GROUP BY deal_stage
```

## 18. 我方方案 × 進行中商機
`our_solutions` 應連到 `vendor` 空白的方案;沒有進行中商機的方案會標警示。
```dataviewjs
const D = dv.current().domain ?? "wireless";
const A = (x) => x == null ? [] : (Array.isArray(x) ? x : (typeof x.array === "function" ? x.array() : [x]));
const inD = (p) => A(p.domain ?? "wireless").includes(D);
const nm = (l) => l ? String(l.path).split("/").pop().replace(/\.md$/, "") : "";
const opps = dv.pages('"BI/Opportunity"').where(inD)
  .where(o => o.deal_stage != "won" && o.deal_stage != "lost").array();
const rows = dv.pages('"BI/TestSolution"').where(p => !p.vendor && inD(p)).array().map(s => {
  const o = opps.filter(x => A(x.our_solutions).some(l => nm(l) == s.file.name));
  return [s.file.link, s.status, o.length, o.length == 0 ? "⚠ 無進行中商機" : "OK"];
});
dv.table(["我方方案", "狀態", "進行中商機", "檢查"], rows);
```

## 19. 有客戶產品需求、但沒有商機的 Application
```dataviewjs
const D = dv.current().domain ?? "wireless";
const A = (x) => x == null ? [] : (Array.isArray(x) ? x : (typeof x.array === "function" ? x.array() : [x]));
const inD = (p) => A(p.domain ?? "wireless").includes(D);
const nm = (l) => l ? String(l.path).split("/").pop().replace(/\.md$/, "") : "";
const cps = dv.pages('"BI/CustomerProduct"').where(inD).array();
const opps = dv.pages('"BI/Opportunity"').where(inD).array();
const cnt = (arr, f, a) => arr.filter(x => A(x[f]).some(l => nm(l) == a.file.name)).length;
const rows = dv.pages('"BI/Application"').where(inD).array()
  .map(a => [a.file.link, a.priority, cnt(cps, "inferred_applications", a), cnt(opps, "applications", a)])
  .filter(r => r[2] > 0)
  .map(r => [...r, r[3] == 0 ? "⚠ 有需求無商機" : "OK"]);
dv.table(["應用", "優先度", "客戶產品需求數", "商機數", "檢查"], rows);
```
