# BI Knowledge round 2, Agent Web layout and Telegram bots — handoff

Updated 2026-11-21. Local `main` = merge `de0c5e14` of branch
`bi-knowledge-round2-20261120` (45 commits) on top of 8 earlier local commits
(agents sidebar, Telegram typing indicator, three-area layout decision). Pushed to
origin/main with the owner's consent on 2026-11-21. CI was not yet green when this
was written; check the run for this push first.

## Goal and scope
The owner reviewed BI Knowledge live and asked for a simpler build flow. They also
asked for Telegram bots bound to agents and for BI collection bots. All of it was
reviewed on the owner's live AEP before the full suite ran, per the owner's rule.
Each decision is a dated 2026-11-20/21 entry in `docs/DECISIONS.md`. Don't re-ask
any of them.

## Done (in main)
- **Three-area Agent Web.** A right side area holds tabs: file viewer, AI sessions,
  card previews and stage settings. The file viewer keeps 預覽／程式碼, 複製, Esc and
  44 px controls (`ea0d16fa`).
- **BI build stages renamed:** Data input / Ingest / Benchmark testing.
  - Each stage has a ⚙ that opens its settings as a side tab. The main views only run
    and show results.
  - One progress row sits under the stage bar.
  - 自動執行 runs convert → ingest → auto-accept → test without stopping. It has a 停止
    button, never jumps between views, and resumes after a reload.
- **2c review** is one list (新卡片 / 修改既有卡片) with a 狀態 filter that defaults to 全部.
  The reason field is always optional, and judgement fields are bulk-acceptable.
- **Ingest** reads 4 parts in parallel and merges them in document order. 停止 really
  stops. The total part count shows up front. A run cut off by a restart becomes
  `partial`, and retrying it reuses cached parts.
- **Settings → Agents:**
  - A pasted bot token is stored as a per-user environment variable through
    `winreg`, never in a file.
  - The bot's @username is resolved with getMe.
  - The save result shows beside the button.
  - The Skills picker shows names and descriptions.
  - Senders are prefilled with the owner's own id.
- **BI collection bots:**
  - A link or file is collected into the bot's domain.
  - A plain question is answered from that domain's cards through a scoped `bi__query`.
  - The collect time is set in the Data input ⚙ or in the 新增 BI 收集 bot form.
- **Verification on `0848b0d4` + test commits:**
  - ruff check, ruff format --check and mypy (src + tests, 1088 files) are clean.
  - The full suite with `-n 4 --dist loadfile` gave 7306 passed, 7 failed and 16
    skipped. All 7 failures pass when rerun alone; they were load and timing flakes.

## Known issues / risks
- **Sub-agents never get Host tools.** An agent with the `engineering/bi-knowledge`
  Skill cannot call `bi__query` (contract "Turn scope"). The owner was told this and
  advised to use a collection bot for BI questions. Changing this needs a core gateway
  change and owner consent.
- **Benchmark tests keep running after 停止.** Stopping 自動執行 at step 4 only stops
  following it; the test itself runs on (there is no cancel API for tests).
- **Collection bot answers are text only.** Charts are not sent.
- **Leftover code:** unused Session A code in `bi_page.py` (biBuildSessA,
  biSchemaSources) and the old 「請和 AI 調整」 text. The rule form's folder hint
  misses a domain created in the same operation.
- **Run full local suites with `-n 4` at below-normal priority.** `-n auto` starved
  the PC and the LLM gateway on 11-21.

## Next actions
1. Watch CI for this push and fix any failure.
2. Once CI is green and AEP is idle (`/api/activity`, `/api/tasks`), restart the
   owner's AEP from main. It currently runs the preview worktree
   `C:/TEMP/claude-preview/wt`. Then remove the preview and round-2 worktrees.
3. Cloudflare port 7844 and Paseo autostart on 141 were dropped by the owner
   (2026-11-21). Don't raise them again.
4. In progress (2026-11-21): improve the X (twitter) link fetch. Follow the single linked
   article, strip the login noise, and treat x.com as its own platform.
5. Don't write the BI/Wiki user manuals until the owner has reviewed the feature and
   asks for them.
