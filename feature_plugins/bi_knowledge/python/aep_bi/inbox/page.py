"""BI 「管理」 → 「Telegram 收集」: per domain its bot, one switch and two times.

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
          <p class="bi-meta">每個領域一個 Telegram bot：傳給它的連結、檔案和文字，
            在收集時間轉檔並 Ingest 到待審；審核提醒時間通知傳送者有幾張候選卡待審。
            bot 要先在這台電腦的 Telegram 設定加入（見 BI 建置指南）。</p>
          <div id="bi-inbox-rows"></div>
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
    const bot = document.createElement("select");
    bot.setAttribute("aria-label", d.label + " 的 bot");
    for (const b of [{name: ""}, ...(reply.bots || [])]) {
      const option = document.createElement("option");
      option.value = b.name; option.textContent = b.name || "（沒有 bot）";
      option.selected = (d.bot || "") === b.name; bot.append(option);
    }
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
        const saved = await biCall("/api/bi/inbox/settings", {domain: d.domain, bot: bot.value,
          enabled: on.checked, collect_at: collect.value || null, review_at: review.value || null});
        note.textContent = "已儲存・" + saved.domain.next;
      } catch (failure) { note.textContent = "沒有儲存：" + failure.message; }
      finally { save.disabled = false; }
    });
    rows.append(bh("div", "bi-actions", bh("strong", "", d.label), bot,
      bh("label", "", on, " 開啟"), bh("label", "", "收集 ", collect),
      bh("label", "", "審核提醒 ", review), save, note));
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
