"""BI 「管理」 → 「Telegram 收集」: per domain one switch and two times, and 未分類.

Kept apart from `bi_page` so that page's own changes and this one meet in two lines:
the menu button (`INBOX_BUTTON`) and the panel (`INBOX_PANEL`) in its HTML; the script
is appended to the page's (`INBOX_JS`).
"""

INBOX_BUTTON = (
    '<button class="bi-btn" id="bi-inbox-open" type="button" hidden>Telegram 收集</button>'
)
INBOX_PANEL = """
        <section id="bi-inbox" class="bi-step" hidden aria-labelledby="bi-inbox-h">
          <h4 id="bi-inbox-h">Telegram 收集</h4>
          <p class="bi-meta">傳給 bot 的連結和檔案，在收集時間轉檔並 Ingest 到待審；
            審核提醒時間通知傳送者有幾張候選卡待審。</p>
          <div id="bi-inbox-rows"></div>
          <div id="bi-inbox-loose"></div>
          <p id="bi-inbox-status" class="bi-meta" role="status" aria-live="polite"></p>
        </section>"""

INBOX_JS = r"""
// -- BI 管理 → Telegram 收集 (owner 2026-11-19) -------------------------------------------
async function biInboxLoad() {
  const status = el("bi-inbox-status");
  status.textContent = "讀取中…";
  let reply;
  try {
    reply = await call("/api/bi/inbox?dataset=" + encodeURIComponent(biDataset()));
  } catch (failure) { status.textContent = "沒有讀到：" + failure.message; return; }
  status.textContent = "";
  const rows = el("bi-inbox-rows"); rows.replaceChildren();
  if (!(reply.domains || []).length) rows.append(bh("p", "bi-meta", "這個知識庫還沒有領域。"));
  for (const d of reply.domains || []) {
    const on = document.createElement("input"); on.type = "checkbox"; on.checked = d.enabled;
    on.setAttribute("aria-label", d.label + " 開啟");
    const collect = document.createElement("input"); collect.type = "time";
    collect.value = d.collect_at || ""; collect.setAttribute("aria-label", d.label + " 收集時間");
    const review = document.createElement("input"); review.type = "time";
    review.value = d.review_at || ""; review.setAttribute("aria-label", d.label + " 審核提醒時間");
    const note = bh("span", "bi-meta", (d.waiting ? d.waiting + " 筆待處理・" : "") + d.next);
    const save = biButton("儲存", async () => {
      save.disabled = true; note.textContent = "儲存中…";
      try {
        const saved = await biCall("/api/bi/inbox/settings", {domain: d.domain,
          enabled: on.checked, collect_at: collect.value || null, review_at: review.value || null});
        note.textContent = "已儲存・" + saved.domain.next;
      } catch (failure) { note.textContent = "沒有儲存：" + failure.message; }
      finally { save.disabled = false; }
    });
    rows.append(bh("div", "bi-actions", bh("strong", "", d.label),
      bh("label", "", on, " 開啟"), bh("label", "", "收集 ", collect),
      bh("label", "", "審核提醒 ", review), save, note));
  }
  const loose = el("bi-inbox-loose"); loose.replaceChildren();
  if ((reply.unassigned || []).length) {
    loose.append(bh("h4", "", "未分類（" + reply.unassigned.length + "）"));
    for (const item of reply.unassigned) {
      const pick = document.createElement("select");
      pick.setAttribute("aria-label", "#" + item.id + " 的領域");
      for (const d of reply.all_domains || []) {
        const option = document.createElement("option");
        option.value = d.domain; option.textContent = d.label;
        option.selected = d.domain === item.suggested; pick.append(option);
      }
      const done = bh("span", "bi-meta", "");
      const go = biButton("指定", async () => {
        go.disabled = true; done.textContent = "指定中…";
        try {
          await biCall("/api/bi/inbox/assign", {item: item.id, domain: pick.value});
          done.textContent = "已指定，該領域的收集時間處理";
        } catch (failure) {
          done.textContent = "沒有指定：" + failure.message; go.disabled = false;
        }
      });
      loose.append(bh("div", "bi-actions", bh("span", "", "#" + item.id + " " + item.title
        + "（" + item.sender + "）"), pick, go, done));
    }
  }
}

el("bi-inbox-open").addEventListener("click", () => {
  el("bi-b-v-menu").open = false;
  const panel = el("bi-inbox"); panel.hidden = !panel.hidden;
  if (!panel.hidden) biInboxLoad();
});
el("bi-dataset").addEventListener("change", () => {
  if (!el("bi-inbox").hidden) biInboxLoad();
});
"""
