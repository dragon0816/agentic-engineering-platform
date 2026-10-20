# Hermes 如何自動產生 Skill，以及 Skill suggestions S3 該怎麼借鏡（研究）

Owner request: 2026-10-21（「如果是自動生成skill，我覺得可以參考hermes agent, 我覺得它做的蠻好的」）。
Status: **research only, no code change.** 本文件是 `docs/phases/SKILL_SUGGESTIONS.md` S3（Create draft）
的輸入；S3 仍 on hold，要等 owner 看過本文的 open questions 再開始。

Source studied (read only, Hermes 未執行、設定未變更、未讀任何 credential 檔):

- Hermes source: `%LOCALAPPDATA%\hermes\hermes-agent\`（git `9fe737aef2`, 2026-09-22）。下文路徑都相對於這個資料夾。
- Hermes live config: `%LOCALAPPDATA%\hermes\config.yaml` line 95-96（只讀 `skills:` 段）。
- Hermes skills: `%LOCALAPPDATA%\hermes\skills\`（AEP 的 `packages/hermes-skill-pack/` 就是從這裡 port 的，見
  `docs/phases/HERMES_SKILL_PACK.md`），以及其中的 `.usage.json` 與 `.curator_ledger.jsonl`（只統計 action/actor，不讀內容）。

## 1. Hermes 的機制

### 1.1 什麼會觸發建立 Skill

Hermes 有**三條**路徑，其中只有第一條是「自動」的：

1. **Background review（主要機制）。** 計數器 `_iters_since_skill` 數的是 **tool-calling iterations**（agent loop 每一輪呼叫模型、
   且當時有 `skill_manage` 工具，就 +1），**不是** user turns、也不是 tasks：
   - 遞增：`agent/turn_iteration_prep.py:120-122`。
   - 只要 agent 呼叫了 `skill_manage` 就歸零：`agent/tool_executor.py:713-715`。
   - 跨 turn 累積，每個 turn 開始時**刻意不歸零**：`agent/turn_context.py:560-561`。
   - 門檻 `skills.creation_nudge_interval`：程式預設 10（`agent/agent_init.py:1337-1339`），範例設定 15
     （`cli-config.yaml.example:1109-1113`，註解 "Every N tool-calling iterations, remind the model to consider saving a skill. Set to 0 to disable."），
     本機 live config 也是 15（`config.yaml:95-96`）。
   - 判斷時機是 **turn 結束、答案已送出之後**：`agent/turn_finalizer.py:675-705`。條件是有 final response、沒被中斷、不是 cron
     （`skip_background_review`，理由是「~30K tokens / event with no human-in-the-loop benefit」）。達標就 fork 一個 background review agent，
     **不會**在主對話裡插一句提示。
   - Memory 有另一個 nudge（`memory.nudge_interval`，數的是 user turns，預設 10，`cli-config.yaml.example:973`）；兩者同時達標時用 combined prompt。
2. **Foreground 的自我判斷（system prompt）。**
   - `agent/prompt_builder.py:256-262` `SKILLS_GUIDANCE`: "When you work out a non-trivial workflow, record it with skill_manage for future reuse."
   - `agent/prompt_builder.py:1381-1398` Skills index 的開場白:
     "If a skill has issues, fix it with skill_manage(action='patch'). After difficult/iterative tasks, offer to save as a skill.
     If a skill you loaded was missing steps, had wrong commands, or needed pitfalls you discovered, update it before finishing."
   - `agent/prompt_builder.py:191-228` 的 memory guidance 說 "Skills come first"：procedure、pitfall、使用者對這類工作的偏好與糾正都寫進 skill，
     memory 只放跨所有 session 的事實。
   - 附帶一提：`prompt_builder.py:242-255` 的註解記錄舊版句子 "After completing a complex task (5+ tool calls)... save the approach as a skill"
     會被 Anthropic 的 server-side filter 擋（subscription OAuth 回 400），所以改寫成現在的措辭。
3. **使用者明確要求。** 使用者叫 agent 存成 skill，或用 `/refine [focus]`（`hermes_cli/commands.py:124`，"Review this conversation now and save lessons to memory/skills"），
   後者會立刻跑同一個 review fork，標記為 attended（`agent/background_review.py:1133-1146`）。

沒有「error recovery」專屬觸發器；錯誤修復是 review prompt 裡的一個 signal（見 1.2）。也沒有像 AEP S1 那種「跨 session 重複請求」的偵測：
Hermes 看的是**單一對話裡做了多少事**，而不是**同一件事做了幾次**。

### 1.2 Review prompt（nudge 的實際文字）

`agent/background_review.py:417-501` `_SKILL_REVIEW_PROMPT`（combined 版在 503-567）。重點逐段摘錄：

- 開頭："Review the conversation above and update the skill library. Be ACTIVE — most sessions produce at least one skill update, even if small.
  A pass that does nothing is a missed learning opportunity, not a neutral outcome."
- 目標形狀："CLASS-LEVEL skills, each with a SKILL.md of always-on rules and a small `references/` set of topical depth.
  Not a flat list of narrow one-session skills, and not an umbrella hoarding a references/ file per session."
- `_LESSON_LAYER_BLOCK`（362-390）：skill 是「依這位使用者的規格、最有效正確地做某一類工作的指示」。Procedure first；pitfall 寫成
  「可推廣的規則 + 一句 why」；不放 PR/issue 編號、日期、引用使用者原話；同一個教訓只寫一條（先搜尋再加）；不重複 AGENTS.md
  或 tool schema 已經教的；常駐規則寫在 SKILL.md、偶爾才需要的深度放 `references/<topic>.md`；錯了就原地修正，不要在下面加 "UPDATE: actually..."。
- Signals（任何一個成立就該動作）：使用者糾正風格、格式、語氣、冗長（"Frustration ... FIRST-CLASS skill signals"）；使用者糾正流程或步驟；
  出現非 trivial 的技巧、修法、workaround、debug 路徑；這次載入的 skill 錯了、缺步驟或過時，"Patch it NOW"。
- **Preference order**：1. 更新這次對話中載入過的 skill；2. 更新既有的 umbrella skill；3. 在既有 umbrella 下加 support file
  （`references/`、`templates/`、`scripts/`）；4. 沒有任何 skill 涵蓋時才新建 class-level umbrella。命名規則："MUST NOT be a specific PR number,
  error string, feature codename, library-alone name, or 'fix-X / debug-Y / audit-Z-today' session artifact."
- Read-before-write（強制）：patch 既有 skill 前必須在本次 review 內 `skill_view`，對話中先前出現的內容不算。
- Protected skills：bundled、hub-installed、external dirs、pinned、**user-owned**（不是 background review 建立的）都不能改；
  若它們錯了，只能在回覆中說明並建議 `hermes curator adopt <name>`。
- `_DO_NOT_CAPTURE_BLOCK`（392-415）：不要把環境問題（缺 binary、未設定 credential）、對工具的負面斷言（"X tool is broken"）、
  已自行恢復的暫時錯誤、one-off 任務敘事、**沒有真正找到可行方法的失敗嘗試**寫成 skill；setup 問題只記「修法」。
- 結尾："'Nothing to save.' is a real option but should NOT be the default."

### 1.3 Agent 寫出什麼、存在哪、怎麼更新

- **格式**：`<skills>/[category/]<name>/SKILL.md` + optional `references/ templates/ scripts/ assets/`（`tools/skill_manager_tool.py:1-8`）。
  SKILL.md 必須以 YAML frontmatter 開頭，必有 `name`、`description`，body 不可為空（`_validate_frontmatter`, 156-189）。
  Linter 另外建議 `version`、`author`、`license`、`metadata.hermes.tags`、`## When to Use` 段落（`tools/skill_linter.py:84-163`）。
  本機實例：`skills/email/outlook-email-workflows/SKILL.md`（description "Use when searching Leo's Outlook mail via COM."，`## Procedure` 編號步驟）。
- **存放**：新 skill 一律寫到 `~/.hermes/skills/`（或 `skills.create_dir`），external dirs 唯讀（`cli-config.yaml.example:1115-1119`）。
- **唯一的寫入工具** `skill_manage`（`tools/skill_manager_tool.py:762-813`，schema 說明 816-832）：operations array、原子性
  （任何一步失敗全部 rollback）。Actions：`create`、`patch`（old_string/new_string，**preferred**）、`edit`（整檔重寫，last resort）、
  `write_file` / `remove_file`（support files）、`delete`。Schema 描述直接教寫法："Keep the description's first 57 chars a self-contained trigger:
  'Use when <trigger>. <one-line behavior>.' Write lessons, not logs."
- **版本**：沒有 semver 版本號流程；`frontmatter version` 只是 metadata。真正的「版本史」是 audit ledger：每次 mutation 都在
  `skills/.curator_ledger.jsonl` 追加一筆 before/after manifest，內容以 sha256 存在 `.curator_backups/blobs/`（`tools/skill_ledger.py:1-8`），
  actor 為 `curator`（background review / curator）、`agent`（foreground）、`user`（CLI）（66-77）。
- **Patch vs new**：由 prompt 的 preference order 強烈偏向 patch。本機實際數據（ledger 71 筆，2026-09-06 起）：
  background review 建立 5 個、patch 48 次、archive 1 個；foreground agent 建立 2 個、patch 14 次。也就是**約 9 成的寫入是修補既有 skill**。
  最常用的 `outlook-email-workflows`（background 建立）`use_count` 78、patch 2 次。

### 1.4 品質控制

| 控制 | 位置 | 內容 |
|---|---|---|
| 名稱 | `skill_manager_tool.py:110-116, 136-141` | `^[a-z0-9][a-z0-9._-]*$`，≤ 64 字元；同名已存在則 `create` 拒絕（424-429） |
| Description | `skill_manager_tool.py:178-185`, `agent/skill_utils.py:763` | ≤ 1024；**新 skill 的 description 必須 ≤ 60 字元**（index 會截斷，routing signal 會消失） |
| 大小 | `skill_manager_tool.py:112-113, 192-198`, `skill_linter.py:51, 56` | SKILL.md ≤ 100,000 字元（硬上限），body > 24,000 警告；support file ≤ 1 MiB；`references/` > 60 檔警告 "references-sprawl" |
| Linter（advisory） | `skill_manager_tool.py:397-415`, `skill_linter.py` | 寫入成功後把 lint warnings 回給 agent 讓它自己 patch：name/dir 不符、description 太長或有行銷字眼、缺 `When to Use`、PR 編號密度過高（"incident-log-shape"）、dangling `references/` 連結、POSIX-only script 沒宣告 `platforms` |
| 安全掃描 | `skill_manager_tool.py:42-66` | `skills.guard_agent_created`（預設**關**），開了才掃描 agent 建立的 skill |
| De-dup | prompt + `skill_view` / `skills_list` | 建立前由模型自己查（preference order 1-3）；程式只擋同名。跨 skill 的重疊交給 curator |
| Ownership guard | `tools/skill_manager_guards.py:164-217` | background review 只能改 `created_by: agent` 的 skill；user-owned、pinned、bundled、hub、external 一律拒絕 |
| Read-before-write | `skill_manager_guards.py:220-230` | 沒在本次 review 內讀過目標檔就拒寫 |
| Tool whitelist | `agent/background_review.py:1074-1123, 1037-1041` | review fork 只有 skills 工具（+ read_file/search_files）；危險指令 auto-deny；skill-only review 拿不到 memory 工具 |
| 預算 | `background_review.py:150-159` | review fork 最多 16 iterations；input token 上限 |
| Curator（之後） | `agent/curator.py:1-7, 30-34, 188-242, 269-449` | 每 7 天、idle ≥ 2 小時才跑；14 天未用標 stale、30 天 archive（可 restore，從不 delete）；LLM consolidation pass（合併成 umbrella）**預設關**（`DEFAULT_CONSOLIDATE = False`） |

沒有測試或執行驗證：Hermes 不會「試跑」一個新 skill。品質靠 prompt 的寫作規範、linter、以及之後使用時再被 patch。

### 1.5 人的參與

- **預設沒有核准。** `skills.write_approval` 預設 false，直接寫入（`tools/write_approval.py:1-10, 170-185`）；本機 config 沒開。
- **事後通知。** Review 結束後，把成功的動作整理成一行："💾 Self-improvement review: Skill 'x' created · Skill 'y' patched"，
  印在 CLI 並經 `background_review_callback` 送到 gateway（Telegram 等）（`background_review.py:702-736, 1197-1202`）；`memory_notifications`
  可設 off / on / verbose。只回報真正寫入成功的動作，不回報「要求了但沒寫成」的。
- **可選核准。** 開 `skills.write_approval` 後，所有 skill 寫入（不論來源）都 stage 到 `<HERMES_HOME>/pending/skills/<id>.json`，
  用 `/skills pending | diff | approve | reject` 審（`write_approval.py:254-285` 產生 create 全文或 unified diff；`hermes_cli/commands.py:217-222`）。
- **Undo。** `hermes curator rollback --entry <ledger id>` 單筆回復（`skill_ledger.py:568-627`，fail-closed，先存 safety entry）；
  `restore` 救回 archive；`pin` 讓 skill 不被自動改；`adopt` 把 user-owned skill 交給 curator 管；`status` / `usage` 看清單與使用次數
  （`hermes_cli/curator.py` 約 606-700）。
- **所有權概念。** 使用者叫 foreground agent 建立的 skill 算 user-owned，background review 不能動；background review 建立的才是
  "curator-managed"（`skill_manager_tool.py:744-751`）。

### 1.6 Skill 之後怎麼被找到與使用（progressive disclosure）

1. **Index**：system prompt 的 `## Skills` 段落列出每個 skill 的 `name: description`（按 category），並要求 "If a skill matches or is even partially
   relevant to your task, you MUST load it with skill_view(name)"（`agent/prompt_builder.py:1343-1400`）。這就是 description 要短、trigger 寫在最前面的原因。
2. **Body**：`skill_view(name)` 載入 SKILL.md，同時回傳 `linked_files` 清單（`tools/skills_tool.py:618-639, 671`）。
3. **Depth**：需要時才 `skill_view(name, file_path='references/x.md')`。
4. 重複 view 未變更的檔案回傳短 stub，省 context（`tools/skills_tool_dedup.py`）；寫入後清掉 skills prompt cache（`skill_manager_tool.py:736-738`）。

### 1.7 為什麼它好用（值得抄的設計）

1. **觸發在「做完一段實質工作之後」，且在答案送出之後背景跑**，不打斷使用者，也不需要累積多天的重複證據；第一次做完就能學。
2. **偏向修補而不是新建**。Skill library 不會爆炸成幾百個窄 skill；被載入且出錯的 skill 會立刻被修正（本機 9 成寫入是 patch）。
3. **寫作規範寫在 prompt 裡、很具體**：class-level 命名、procedure first、pitfall = rule + why、不寫 incident、不寫環境失敗、不寫沒驗證過的嘗試。
4. **使用者的糾正是第一等訊號**，直接寫進負責該類工作的 skill，下次一開始就做對。
5. **Description 是 routing key**：硬性 60 字元、"Use when ..." 開頭，搭配 index → body → references 三層載入。
6. **所有權與保護**：自動流程只能動自己建的 skill；pinned / 使用者自己的 / 安裝來的都不碰。
7. **可回復**：每次寫入有 ledger 與 blob，單筆 rollback；curator 只 archive 不 delete。
8. **成本控制**：只在達門檻時跑、cron 不跑、iteration 上限、可 route 到較便宜模型。

## 2. AEP 今天的狀態

- **S1**（2026-10-16 實作）：nightly 從本人的對話挖「跨 session 的重複請求」，deterministic score 只當 pre-filter，**模型分組**
  （owner decision 1），門檻 Normal = 3 requests / 3 sessions / 2 days，每晚最多 3 張新卡（`docs/phases/SKILL_SUGGESTIONS.md` "S1 as built"）。
- **S2**（2026-10-16 實作）：Reviews tab 的 `skill_suggestion` 卡，只有 ids 與日期、證據可點開原對話，Ignore（含 reason quick pick）/
  Snooze 7 days / Reopen，Sensitivity Low/Normal/High（"S2 as built"）。卡片目前**沒有 draft**，`accept` 會回 `suggestion_has_no_draft_yet`。
- **S3 "Create draft"：on hold**，owner 想先看卡片品質（"Owner decision after S2"）。
- **規則**：模型不安裝、不核准；只有人的 Install 按下才安裝（AGENTS.md rules 13、15；`docs/phases/EXPERIENCE_REVIEW.md` principle 1
  "Propose, never apply"；`SKILL_SUGGESTIONS.md` §1 "the Agent suggests and drafts; only a person's button creates a draft, and only the Capabilities
  Install press installs it"，§9 "Never self-install"）。
- **既有可重用的路徑**：
  - `host_runtime/skill_authoring.py`：`assemble_skill`（host 決定 owner、`private`、`draft`、版本）、`check_skill`（不可有 `rules` / `script_tools`、
    instructions 必填且不含 secret、commands 只能指向已安裝的 capability/Workflow、名稱不衝突），instructions 上限 20,000 字元。
  - `host_runtime/chat_authoring.py` `check_skill` / `draft_skill`（candidate `sk-...`，有 `source`、`session_id`、`revision`）、
    `request_skill_install` / `_decide_skill`（digest 不符就失敗：「candidate changed after the request」）。
  - `host_runtime/draft_cards.py`：對話中產生或修改 draft 後顯示的 install card（Install / Run once to try / Not now），模型按不到；
    新 revision 會把舊卡標成 "Replaced"。
  - 對話中的模型只有 Workflow authoring tools（`authoring__draft_workflow` / `revise_workflow` / `install_workflow` 等，
    `chat_authoring.py:1596-1750`）；**Skill 只能從外部 agent 經 MCP 送進來**（`aep_check_skill` / `aep_submit_skill` / `aep_install_skill`，`mcp_server.py:132-144`）。
- **AEP 的 Skill 使用方式與 Hermes 不同**：Gateway 把 Skill 的 `instructions` 全文放進每個 command tool 的 description，`selector_hint`（≤ 240）
  當 routing hint（`agent/gateway.py:762-781`）。沒有 index → body → references 的分層載入；Hermes pack 的 references 只在 coding-agent 那份
  （`HERMES_SKILL_PACK.md`）。所以 AEP 的 Skill 越長，每一輪成本越高。

## 3. 差異總覽

| 面向 | Hermes | AEP S1/S2 |
|---|---|---|
| 觸發 | 單一對話累積 N 個 tool iterations；使用者糾正；使用者要求 | 跨 session 的重複請求（nightly） |
| 時機 | 每個達標 turn 之後，背景 | 每晚一次 |
| 誰判斷值不值得 | 模型（prompt 偏向「要動作」） | 門檻 + 模型分組；人決定 |
| 產出 | 直接寫入 skill（create / patch / support file） | 一張卡，沒有 draft |
| 偏好 | 修補既有 > 新建 | 只有新建（Update existing 在 S4） |
| 人 | 事後通知、可 rollback；可選 staging | 一定要人按 Create draft 與 Install |
| De-dup | 模型自己查 + 同名擋 + 之後 curator 合併 | deterministic：已安裝、pending candidate、已回報群組 |

## 4. 建議的 S3 設計

原則不變：**模型可以提議與起草；只有人的按鈕產生 candidate，只有 Install 按下才安裝。** 在這條線內儘量吸收 Hermes 的做法。

### 4.1 逐項決定（adopt / adapt / reject）

| # | Hermes 做法 | 決定 | 在 AEP 的樣子與理由 |
|---|---|---|---|
| 1 | 模型自己寫 SKILL 內容 | **Adopt** | Nightly 對每張 qualified 卡呼叫一次結構化模型（`SKILL_SUGGESTIONS.md` §6.2 的 `skill_suggestion_draft`），產出 Skill（或 Workflow）的作者欄位，經 `assemble_skill` → `check_skill`，失敗重試一次。Draft 存在 suggestion 記錄裡，卡片顯示 read-only preview。按 **Create draft** 才變成 candidate（`draft_skill(..., source="suggestion:<id>")`）。 |
| 2 | Review prompt 的寫作規範（`_LESSON_LAYER_BLOCK`、`_DO_NOT_CAPTURE_BLOCK`、命名規則） | **Adopt** | 幾乎原樣搬進 draft prompt：class-level 命名（禁止日期、單號、錯誤字串、"fix-X" 類名稱）、procedure first、pitfall = rule + why、不寫 incident 與原話、不寫環境失敗與負面工具斷言、**沒有成功解法的對話不起草**（證據中的 answer status 必須是 answered 且未被負評）。這是 Hermes 最有價值、也最便宜的部分。 |
| 3 | 修補既有 skill 優先（preference order） | **Adapt** | 把 S4 的 **Update existing** 拉進 S3 的判斷順序：證據中用過的、或任務描述被已安裝 Skill 涵蓋的，且**這個人擁有**的 Skill → 產生 revision candidate（現有 manifest + 改動，卡片顯示 diff，Install 走正常 version bump）；沒有才新建。理由：Hermes 實際 9 成寫入是 patch，library 才不會爆。不同的是 AEP 的 patch 也要人按 Install。 |
| 4 | Read-before-write | **Adapt** | 不給 nightly 模型工具；改由 host 把要修改的 Skill 現行 manifest 放進 input，並在 candidate 記錄 base digest；Install 時 base 已變更就拒絕（沿用 `_decide_skill` 的 digest 檢查精神）。 |
| 5 | 所有權保護（只動自己建的，pinned / bundled / hub 不動） | **Adopt** | Update existing 只限 owner 是本人的 Skill；organization / published、Hermes pack、別人的 Skill 一律不產生 patch candidate，只在卡片上寫「已有 X 涵蓋，建議通知 owner」。 |
| 6 | Description 是 routing key（≤ 60 字元、"Use when ..."） | **Adapt** | AEP 的對應欄位是 `selector_hint`（≤ 240）。Draft prompt 要求一句 trigger-first 的 `selector_hint`；host 端加 advisory 檢查（長度、行銷字眼）。 |
| 7 | 大小與 lint（body 預算、`When to Use`、PR 編號密度） | **Adapt** | AEP 的 instructions 會整段進每一輪 prompt，所以預算要比 Hermes 嚴：建議 draft instructions 目標 ≤ 4,000 字元（硬上限仍是 20,000），必須有「When to use」與步驟。超過就在卡片上標註，不自動截斷。數字是提案，見 open question 6。 |
| 8 | 使用者糾正是第一等訊號 | **Adopt（S3 後段）** | 把 §4.3 corrections signal 與 Update existing 一起做：同一類糾正在 ≥ 2 個 session 出現 → 對負責那類工作的 Skill 提 update。這是 Hermes 認為最有價值的訊號。 |
| 9 | 每 N 個 tool iterations 在 turn 後背景 review | **Adapt，預設關** | 新增「對話結束後的 review」：一個 turn 結束、答案已送出後，若本 session 自上次 draft 以來累計 tool calls ≥ N（建議 15，與 Hermes 本機設定相同）且最後一次 answered，背景跑一次 review。產出是 **suggestion 卡（含 draft preview）**，不是 candidate。理由：S1 只抓「重複了 3 次」，Hermes 證明「做了一次很長的事」也值得學。和 owner decision 3（end-of-conversation card 在 S6 前關閉）衝突，所以預設關、放 Reviews tab，不在對話裡插卡；見 open question 1。 |
| 10 | 使用者主動要求（`/refine`、「存成 skill」） | **Adopt** | 在 Agent Web 對話加 **Save as Skill** 按鈕（或使用者打「把這個存成 Skill」），立即跑一次 review，結果走既有 `draft_cards.py` install card。這是人按的按鈕，所以可以直接產生 candidate，符合「只有人的按鈕產生 draft」。需要 Gateway 有 skill 版的 authoring 路徑（目前只有 Workflow 工具），見 open question 5。 |
| 11 | Foreground prompt "After difficult/iterative tasks, offer to save as a skill" | **Adopt** | Gateway system prompt 加一句：做完長任務時可以**用文字提議**存成 Skill，但不可自行起草或安裝；使用者同意後走 #10。 |
| 12 | "Be ACTIVE — most sessions produce at least one update" | **Reject** | Hermes 可以積極，因為寫入是靜默、可 rollback、不需人看。AEP 每一個產出都花人的注意力，積極偏向會灌爆 Reviews。AEP prompt 改成「沒有充分證據就回 `same_task: false` / nothing to suggest」，並維持 S1 的每晚卡片上限。 |
| 13 | 直接寫入、事後通知 | **Reject**（寫入）／**Adopt**（通知） | 自行安裝違反 AGENTS.md 13/15 與 principle 1。但「💾 Self-improvement review: …」這種一行通知值得抄：背景 review 產出卡片時，在 Agent Web（與 S5 的 Telegram link line）顯示一行「有一個 Skill 建議在 Reviews 等你」。 |
| 14 | 可選的 staging + diff + approve（`write_approval`） | **Adopt（已經是 AEP 的預設）** | AEP 本來就是 Hermes 的 `write_approval: true` 模式。抄 diff 呈現：create 顯示全文、update 顯示 unified diff（`write_approval.py:254-285` 的做法）。 |
| 15 | Ledger + 單筆 rollback | **Adapt** | AEP 有版本號與 disabled folder；建議在 Capabilities 對「從 suggestion 安裝的 Skill」提供「回到前一版」，並在 suggestion 記錄保存 candidate id 與 base digest，讓 audit 能追溯。範圍不大，可放 S3 末或 S4。 |
| 16 | Curator：stale / archive / LLM consolidation | **Reject 自動執行；之後 Adapt 成建議** | 自動 archive 與合併會改變行為且沒有人參與。之後可以做「這兩個 Skill 很像，要合併嗎」的 Reviews 卡，以及依使用次數提示「30 天沒用」；不在 S3。 |
| 17 | De-dup 交給模型 + 之後 curator | **Adapt** | 保留 S1 的 deterministic dedupe（已安裝、pending candidate、已回報群組），再加模型的 `overlaps` 欄位；有 overlap 時優先走 #3 Update existing 而不是丟掉。 |
| 18 | Background fork 共享 prompt cache、工具白名單 | **Reject（不需要）** | AEP 的 draft 呼叫是無工具的 structured output，本來就寫不了東西；不必複製 fork 與白名單機制。 |
| 19 | 只有 skill（+ scripts/） | **Reject** | 保留 AEP 的 Skill vs Workflow 判斷（`SKILL_SUGGESTIONS.md` §6.1）：固定步驟、只有值不同 → Workflow draft（有表單）；需要判斷 → Skill draft。 |
| 20 | Index → body → references 分層載入 | **Out of scope，記錄風險** | AEP 沒有這種分層；draft 不寫 references，所有內容在 instructions 內，因此 #7 的預算更重要。是否為 AEP Skill 加分層載入，是另外的架構議題。 |

### 4.2 S3 的流程

```text
來源 A（已有）  nightly S1 群組達門檻 ───────────────┐
來源 B（新，預設關）turn 結束後，累計 tool calls ≥ N ─┤
                                                    ▼
             host 先做 deterministic dedupe，並找出「本人擁有、可修補」的 Skill
                                                    ▼
             一次 structured 模型呼叫（Hermes 寫作規範 + DO NOT CAPTURE）
             輸出：same_task、task、draft_kind、update_of | new、draft、parameters、overlaps
                                                    ▼
             assemble_skill / check_skill（或 check_workflow），失敗重試一次，有 secret 就丟棄
                                                    ▼
             Reviews 卡：任務、證據、draft preview 或 diff、表單 preview
             按鈕：Create draft | Update existing | Ignore | Snooze
                                                    ▼  （人按）
             candidate（source=suggestion:<id>）→ draft install card / Capabilities → Install（人按）

來源 C（新）使用者在對話中按 Save as Skill → 同一個模型呼叫 → candidate → draft install card → Install（人按）
```

### 4.3 建議的切片

| Slice | 內容 | Done when |
|---|---|---|
| S3a | Nightly draft：對 qualified 卡呼叫 draft 模型（Hermes 規範 prompt），check + 一次重試，卡片 preview，**Create draft** 產生 candidate | Owner 從一張真實卡片按 Create draft，再按 Install 裝好 |
| S3b | Update existing 優先（原 S4 前半）：本人擁有的 Skill → revision candidate + diff；base digest 檢查 | 一張卡變成某個既有 Skill 的 update candidate 並被安裝 |
| S3c | 對話中的 **Save as Skill** 按鈕與 Gateway 的 skill draft 路徑；system prompt 的「可提議」一句 | 在 Agent Web 一段長任務後按按鈕，出現 install card |
| S3d | Corrections signal（原 S4 後半） | 一個重複糾正變成 update candidate |
| S3e | Turn 後背景 review（來源 B），預設關，與 S6 trial 一起評估 | Owner 開啟後一週內的卡片品質可接受 |

## 5. Open questions for the owner

1. **對話中的觸發（來源 B）。** 要不要像 Hermes 一樣，「一段很長的工作做完」就背景起草建議，而不只是 nightly 的「重複 3 次」？
   這和 2026-10-16 decision 3（S6 前不在對話中出卡）有關。*建議：* 做，但預設關，只產生 Reviews 卡、不在對話中插卡；門檻 15 個 tool calls。
2. **Draft 何時生成。** Nightly 對每張 qualified 卡先起草（卡片立即有 preview，每晚最多 3 次模型呼叫），還是等人按 Create draft 才起草？
   *建議：* nightly 先起草（Hermes 的做法；人看 preview 才判斷得了要不要）。
3. **Update existing 拉進 S3？** Hermes 9 成是修補既有 skill。*建議：* 是，S3b；只限本人擁有的 Skill。
4. **別人的 Skill。** 對 organization、Hermes pack 或同事的 Skill，只顯示「已有 X 涵蓋」、不產生 patch？ *建議：* 是（等同 Hermes 的 protected skills）。
5. **對話中的 Save as Skill。** 要不要在 Agent Web 加這個按鈕，並讓 Gateway 有 skill 起草路徑（目前只有 Workflow 工具與 MCP）？
   *建議：* 要（S3c）；這是人按的，最符合 AEP 規則。
6. **Draft 長度預算。** AEP 的 Skill instructions 每輪都整段放進 prompt。Draft 目標上限 4,000 字元可以嗎？ *建議：* 可以，超過只警示不截斷。
7. **Corrections signal。** Hermes 把「使用者糾正」當最重要的訊號。要在 S3 就做（S3d），還是維持 S4？ *建議：* 放 S3d，在 S3b 之後。
8. **Curator 類功能。** 之後要不要「合併相似 Skill」與「長期沒用」的建議卡（不自動執行）？ *建議：* 先記在 backlog，S6 trial 後再談。

## 6. 不採用的理由摘要

- **自行寫入／安裝**：違反 AGENTS.md rules 13、15 與 `EXPERIENCE_REVIEW.md` principle 1。Hermes 能這樣做，是因為它是單人個人 agent，
  而且有 ledger rollback；AEP 的 Skill 可能分享給同事，行為變更必須有人負責。
- **"Be ACTIVE" 的偏向**：Hermes 的產出不需要人看，AEP 的每一張卡都需要；積極偏向在 AEP 會變成噪音。
- **自動 curator（archive / consolidation）**：一樣是沒有人參與的行為變更；Hermes 自己也把 LLM consolidation 預設關閉。
