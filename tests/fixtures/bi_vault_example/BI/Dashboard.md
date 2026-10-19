# BI Dashboard(範例)

## 1. 趨勢優先度(量測影響 × 我方契合度)
```dataview
TABLE stage AS 階段, time_to_demand AS 需求時間, measurement_impact AS 影響, our_fit AS 契合, measurement_impact * our_fit AS 優先度
FROM "BI/Trend"
WHERE stage != "fading"
SORT measurement_impact * our_fit DESC
```

## 2. 客戶產品上市時程(預測需求)
```dataview
TABLE account AS 客戶, node AS 節點, technologies AS 技術, launch_window AS 上市, test_stage_now AS 目前階段
FROM "BI/CustomerProduct"
SORT launch_window ASC
```

## 3. 各價值鏈節點的生態系成員
```dataview
TABLE rows.file.link AS 成員, rows.role AS 角色, rows.relationship_to_us AS 與我關係
FROM "BI/Ecosystem"
GROUP BY node
```

## 4. 節點 × 技術 矩陣(客戶產品數)
```dataviewjs
const nodes = dv.pages('"BI/Node"').sort(n => n.file.name);
const techs = dv.pages('"BI/Technology"').sort(t => t.file.name);
const cps = dv.pages('"BI/CustomerProduct"');
const nm = (l) => l ? String(l.path).split("/").pop().replace(/\.md$/, "") : "";
const rows = nodes.map(n => [
  n.file.link,
  ...techs.map(t => cps.where(cp =>
      nm(cp.node) == n.file.name &&
      dv.array(cp.technologies).some(x => nm(x) == t.file.name)
  ).length)
]);
dv.table(["節點", ...techs.map(t => t.file.name)], rows);
```

## 5. 近期訊號
```dataview
TABLE date, summary AS 摘要, so_what AS 所以呢, reliability AS 可靠度
FROM "BI/Signal"
SORT date DESC
LIMIT 10
```

## 6. 缺口:沒有任何 Test Solution 連結的 Application
```dataview
TABLE priority AS 優先度, lifecycle AS 階段, trends AS 趨勢
FROM "BI/Application"
WHERE length(filter(file.inlinks, (l) => contains(l.path, "TestSolution"))) = 0
SORT priority DESC
```

## 7. 推測內容比例(待驗證)
```dataview
TABLE length(rows) AS 筆數
FROM "BI"
WHERE confidence
GROUP BY confidence
```

## 8. 資料過期提醒(超過 90 天未更新)
```dataview
LIST
FROM "BI/Ecosystem" OR "BI/Technology" OR "BI/Trend" OR "BI/CustomerProduct"
WHERE date(today) - file.mtime > dur(90 days)
SORT file.mtime ASC
```

## 9. 方案層總覽(Test Solution)
```dataview
TABLE applications AS 應用, test_type AS 測試類型, tier AS 型態, automation AS 自動化, price_band AS 價格帶, status AS 狀態
FROM "BI/TestSolution"
SORT status ASC
```

## 10. 趨勢 → 應用 → 方案 覆蓋檢查
```dataviewjs
const nm = (l) => l ? String(l.path).split("/").pop().replace(/\.md$/, "") : "";
const trends = dv.pages('"BI/Trend"').sort(t => t.measurement_impact * t.our_fit, "desc");
const apps = dv.pages('"BI/Application"').array();
const sols = dv.pages('"BI/TestSolution"').where(p => !p.vendor).array();
const rows = trends.map(t => {
  const a = apps.filter(x => dv.array(x.trends).some(l => nm(l) == t.file.name));
  const s = sols.filter(x => dv.array(x.applications).some(l => a.some(y => y.file.name == nm(l))));
  const status = a.length == 0 ? "⚠ 無對應 Application" : (s.length == 0 ? "⚠ 無對應方案" : "OK");
  return [t.file.link, t.measurement_impact * t.our_fit, t.stage, a.length, s.length, status];
});
dv.table(["趨勢", "優先度", "階段", "Application 數", "方案數", "狀態"], rows);
```

## 11. 競品方案對照(我方 R&S 方案 vs 對手方案)
```dataview
TABLE rows.file.link AS 我方方案, theirs.vendor AS 對手廠商
FROM "BI/TestSolution"
WHERE !vendor
FLATTEN competing_solutions AS theirs
GROUP BY theirs
```

## 11b. 已建檔的對手方案(依應用)
```dataview
TABLE vendor AS 廠商, applications AS 應用, test_type AS 類型, tier AS 型態, price_band AS 價格帶
FROM "BI/TestSolution"
WHERE vendor
SORT vendor ASC
```

## 12. 供應商依賴排行(哪些 Ecosystem 被最多客戶依賴)
```dataview
TABLE length(rows) AS 客戶數, rows.file.link AS 客戶
FROM "BI/Account"
FLATTEN key_suppliers AS supplier
GROUP BY supplier
SORT length(rows) DESC
```

## 13. Ecosystem 依角色分布
```dataview
TABLE length(rows) AS 數量, rows.file.link AS 廠商
FROM "BI/Ecosystem"
GROUP BY role
SORT length(rows) DESC
```

## 14. 缺少 Concept 解釋的 Technology(Sales Enablement 缺口)
```dataviewjs
const nm = (l) => l ? String(l.path).split("/").pop().replace(/\.md$/, "") : "";
const concepts = dv.pages('"BI/Concept"').array();
const rows = dv.pages('"BI/Technology"').sort(t => t.file.name).map(t => {
  const cs = concepts.filter(c => dv.array(c.technologies).some(l => nm(l) == t.file.name));
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
WHERE review_status != "reviewed"
SORT file.name ASC
```
