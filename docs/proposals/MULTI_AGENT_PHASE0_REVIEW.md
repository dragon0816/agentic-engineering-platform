# AEP 多代理（Multi-Agent）Phase 0 審查與 ADR（待 owner Gate 0）

2026-10-26，Claude Code。**只讀審查，沒有任何程式、契約、權限、設定或公開 API 改動。**
輸入：owner 的計畫 `docs/proposals/MULTI_AGENT_AUTO_DISCOVERY_v0_source.md`（以下稱「計畫」，行號寫成 `source:N`）。
所有 file:line 以 commit `0a892df6` 為準。

## 0. 摘要（給 owner）

- **計畫要的骨架大部分已經在 repo 裡**：`AgentProfile` 是已治理、可版本化、可經 Shared Platform 發佈與選取的資產（`agent` 是 `AssetKind` 之一）；架構文件早已定義「delegation / agent-as-tool」與 handoff 的區別、深度與輪數上限（`docs/ARCHITECTURE.md:983-989`）；Gateway tool loop、guards、`ApprovedModelClient` 遙測、背景任務的「受限子對話」（`TaskContract` → `GatewayConversationRequest`）都可重用。**缺的是執行**：`validate_profile` 明確拒絕 `may_delegate_to`（`src/host_runtime/profiles.py:73`），profile 的 `max_turns` 沒有任何執行路徑讀它。
- **計畫有五個與 repo 衝突的假設**（§4）：PR／branch protection（repo 規則是直推 main、無 PR）、多租戶 Session（實際是一機一 member）、獨立的 Agent Registry（已有，不應重建）、Workflow 引擎平行（**引擎是嚴格循序**）、多 gateway 路由（目前是 session 選模型、單一 Gateway URL 與資料核准）。
- **建議的 V1**（§9）：擴充 `AgentProfile`（模型政策參照、每實例上限），在 feature flag 後解除 `may_delegate_to` 拒絕（深度 1），新增 host tool `agent__delegate` 以同一 Gateway loop、guards 與 `ApprovedModelClient` 跑有界子對話，子代理產物記在**父 session** 的 ledger；選擇只用明確指定、`may_delegate_to` 與 `selector_hint`，**不做 ranker**；平行在 V1 **不做**（引擎不支援）。
- **開工前先做 Phase 0.5**：G5 跨領域負向測試、P0-2 重試冪等快取、補正 G4 的過時記帳。
- 需要 owner 決定的事在 §13（含預設答案）。

## 1. 計畫要求的路徑 → repo 慣例

| 計畫要求（source:185-189） | 本 repo 對應 | 理由 |
|---|---|---|
| `docs/architecture/multi-agent-current-state.md` | 本文 §2 | repo 沒有 `docs/architecture/`；架構只有一份 `docs/ARCHITECTURE.md`，提案放 `docs/proposals/`（前例 `BI_DATASET_SHARING.md`） |
| `docs/architecture/multi-agent-gap-analysis.md` | 本文 §3、§4 | 同上 |
| `docs/adr/` | 本文 §8（ADR-MA1–MA5）；**owner 決定後**以日期條目追加到 `docs/DECISIONS.md` | repo 的 ADR 慣例是 `docs/DECISIONS.md` 追加條目（例如 ADR-K9 於 2026-10-19 條目），沒有 `docs/adr/` |
| `docs/plans/multi-agent-implementation-plan.md` | 本文 §7、§10；核准後另立 `docs/phases/MULTI_AGENT.md` 作為進行中的規格 | 進行中的規格放 `docs/phases/`（如 `HARNESS_UNIFICATION.md`）；進度記在 `docs/TASKS.md` |
| Issue/PR 拆分 | 本文 §11（只寫在文件，**未建立 issue**） | repo 用 GitHub Issues 追蹤（AGENTS.md:79），無 PR（AGENTS.md:77） |

## 2. 現況架構圖（file:line）

### 2.1 入口與 Session/Run

| 元件 | 現況 | 出處 |
|---|---|---|
| Host 狀態庫 | `state.sqlite`，表：`local_meta`、`installed`、`runs`、`channel_cursor`、`conversations`、`contribution_drafts`、`task_runs`、`feedback_outbox` | `src/host_runtime/state.py:46-70` |
| 對話（Agent Web session） | `ConversationRecord`、`ConversationTurnRequest`、per-conversation backend／model 選擇請求 | `src/host_runtime/conversations.py:114, 147, 172, 184` |
| `RequestContext` | 帶 `actor`、`namespace`、`channel`、`session_id`；**沒有 tenant、沒有 agent identity** | `src/common/execution.py:50-59` |
| Session 產物 ledger（規則 20） | 每個 (session, actor) 一個 JSON（`<workspace>/session-artifacts/<sha256>.json`）；`record_run`/`record_files`/`finish_turn`；`guidance()` 每回合注入系統提示；`session__attach_file` host tool 只能附本 session、本人的紀錄 | `src/host_runtime/session_artifacts.py:59, 117-147, 203-225, 292-368, 448, 566, 639`；接線 `src/host_runtime/host.py:2246-2252` |
| 任務結果摘要（規則 20） | `<workspace>/session-artifacts/task-summaries.sqlite`，保留 30 天 | `src/host_runtime/task_summaries.py:16, 47, 89-95` |
| Telegram session | 對話 session `telegram-chat-{chat_id}`；附檔 session `telegram-chat-{chat}-sender-{sender}`；Web 是 `conversation-{uuid}`；發送者映射到本機綁定的 actor（`_acting()`） | `src/channels/telegram.py:560-567, 1450`；`src/host_runtime/web.py:2466` |
| Session 模型範圍 | 一個 session 內所有呼叫用該 session 選的模型（`TURN_MODEL`） | `docs/DECISIONS.md:4565`、`:4687` |

**缺口：** 沒有獨立的 `Run` 實體把「一次請求」的策略、計畫、policy snapshot 串起來；最接近的是遙測的 `run_id/trace_id/parent_span_id`（§2.7）與 `task_runs`。

### 2.2 路由、Skill 與 Agent Profile

| 元件 | 現況 | 出處 |
|---|---|---|
| 確定性路由 | `CommandRouter`（dot-command、KeywordRule）→ `RequestRouter`（規則優先，再一次 LLM `_model_route`）；`RouteDecision.kind` 有 `agent`，但 `RoutingOutcome` **明確拒絕** `agent`（「agent delegation is not supported by this routing layer」） | `src/agent/routing.py:46-47, 73-106, 138-183, 249`；`src/common/execution.py:62-63` |
| Skill `selector_hint` | Skill manifest 欄位（≤240 字）；Gateway 把它放進 skill 候選請求 | `src/agent/skills.py:107`；`src/agent/gateway.py:409-426, 829-830` |
| Skill 選擇加速器 | 結果必須是非空、已安裝子集合；含 coding Skill 一律退回全目錄；低信心 <0.9 退回 | `docs/HARNESS_DESIGN.zh-TW.md:128-130`；`src/agent/gateway.py:436` |
| `AgentProfile` | `skills`、`allowed_capabilities`、`knowledge`、`may_delegate_to`、`policy_constraints`、`model_requirements`、`max_turns`（≤151）、`max_retries` | `src/agent/contracts.py:15-34` |
| `ActiveAgentProfile` | 本機選一個已安裝 profile；不授予權限 | `src/agent/contracts.py:37` |
| Profile 啟用 | 必須被選取、已發佈已安裝、所有參照都已選取已安裝、模型端點滿足 `model_requirements`；**`may_delegate_to` 非空 → `profile_delegation_unsupported`** | `src/host_runtime/profiles.py:62-99`（拒絕在 `:73`）；`docs/CONTRACTS.md:1635-1657` |
| Profile 過濾 registry | 只能縮小 Skill／Knowledge／能力，不能新增 | `src/host_runtime/host.py:1148-1162` |
| 範例 profile | `agents/engineering.json`，`lifecycle: draft`，「no runtime is instantiated」 | `agents/engineering.json` |
| `ModelRequirements` | reasoning、tool_calling、structured_output、vision、local_only、min_context_tokens | `src/models/contracts.py:16-23` |
| 架構定義 | Gateway／Agent／Model Router／Workflow 是四個分開的決定；delegation vs handoff；深度、輪數、重試要有界 | `docs/ARCHITECTURE.md:921-937, 956-989` |

**注意：** `docs/archive/AGENT_CAPABILITIES_REQUESTED.md:150-152` 說「AgentProfile 在 `src/` 沒被引用」——**已過時**，Productization 2 slice 4 加了 `profiles.py`。但它 :153-160 的結論仍成立：一台機器多個 agent 需要 agent identity，grant 目前是 per actor。

### 2.3 對話迴圈、Harness 與 guards

| 元件 | 現況 | 出處 |
|---|---|---|
| Gateway tool loop | `Gateway.converse` → `_converse`，迴圈 `for turn in range(1, max_turns + 1)`；`_stopped` 管時間與輪數；工具執行 `_one_tool`/`_execute_host_tool` | `src/agent/gateway.py:588, 720, 746, 1005-1012, 1309-1357` |
| Host tool 介面 | `HostTool(tool, handler)`、`HostToolOutcome`（succeeded/awaiting_approval/failed）；在 Skill 縮小後合併，不在 `allowed_tools` 的略過；組裝於 host.py（authoring、browser/desktop、cards、`bi__query`、MCP、workflow form、`session__attach_file`） | `src/agent/gateway.py:303-314, 472, 950-958`；`src/host_runtime/host.py:2253-2261` |
| `ApprovedModelClient` | 每次模型呼叫發 `llm.completed`（alias、input/output tokens、tools_offered、tool_calls） | `src/models/approved.py:13-35` |
| 上限與防空轉 | 150 工具呼叫／151 輪／30 分鐘／相同呼叫 5 次／相同失敗 3 次／觀察 160k 字 | `docs/HARNESS_DESIGN.zh-TW.md:132-170`；`docs/DECISIONS.md:3380` |
| 統一 Harness 狀態機 | 四領域 plan→collect→execute→validate→retry；對話用 `no_unbacked_action_claim`（claim check）、`named_outputs_exist` | `docs/HARNESS_DESIGN.zh-TW.md:15-26`；`docs/phases/HARNESS_UNIFICATION.md` |
| G1–G4 接合規則 | 未通過但有輸出原樣回傳、使用者原句是錨點、依綁定資產選 Skill、輸出長度一致 | `docs/HARNESS_DESIGN.zh-TW.md` §5.6 |
| Host checks 實作點 | `src/harness/runtime.py:108`、`src/workflow/harness.py:130`、`src/agent/conversation_harness.py:373` | 同左 |
| 背景任務執行器（**受限子對話的現成原型**） | `TaskContract` → 依 Skill 命令算出 `allowed_tools` → `DataPolicy.decide(OutboundContext)` → `GatewayConversationRequest(allowed_tools, max_turns=min(max_backend_turns,5))` → `task_runs` | `src/agent/task_execution.py:100-156`；`src/agent/task_contract.py:40-46`；`src/agent/data_policy.py:52, 121` |
| 外部 CLI 後端（Codex/Claude/Copilot） | `ConversationBackendName` = gateway/claude_code/codex/copilot/copilot_agent，存在每個 `ConversationRecord.backend`；非 gateway 的回合走 `backends.complete()`（`web.py:2927-2960`），沒有 session 模型、沒有附件、沒有 persona；`LocalConversationBackends`：固定 CLI 命令；Agent mode 透過 `mcp__aep-agent__permission` 卡片核准 | `src/host_runtime/conversation_backends.py:24, 58, 383`；`src/host_runtime/agent_mode.py:102-176`；`docs/phases/AGENT_MODE_BACKENDS.md:19-103` |
| Persona | `AgentPersonaSettings`/`AgentPersonaStore`（全機一份） | `src/host_runtime/persona.py:17-49` |

### 2.4 資產、Shared Platform 授權

| 元件 | 現況 | 出處 |
|---|---|---|
| 資產種類 | `AssetKind`：task、workflow、skill、knowledge、**agent**、bridge_extension、bi_dataset | `src/common/distribution.py:24-28` |
| 可選取種類 | `RunnableKind`（含 agent、capability）、`INSTALLABLE_KINDS` | `src/common/authorization.py:29-37` |
| 新增 kind 的前例 | `d39d0927`「Publish and share BI datasets」動了 14 檔（distribution、authorization、member、control_plane/* 7 檔、platform_publish、CONTRACTS、2 個測試） | `git show --stat d39d0927` |
| 群組 | 只來自邀請（`Invitation.groups` → `PlatformUser.groups`），`AuthenticatedActor` 不帶群組 | `src/common/enrollment.py:24, 43`；`src/common/identity.py:6-10, 29` |
| 可見性與權利 | `NameAccess`（visibility override、members、groups）；`entitled()`：已發佈、owner/contributor、NameAccess、或 public/organization；**entitled ≠ 可執行** | `src/common/identity.py:176-259` |
| 裝置選取 | `DeviceAssetSelection`（bridge, actor, asset）；只有 capability 選取可帶 `approval_ref` | `src/common/authorization.py:1-15, 40-107` |
| 執行授權 | `ExecutionAuthorization`（沒有 `AuthorizationDecision` 類別） | `src/common/execution.py:75` |
| Publish 檢查 | `manages`、`may_publish` | `src/common/ownership.py:145, 150` |

### 2.5 Host 政策、核准、DUT

| 元件 | 現況 | 出處 |
|---|---|---|
| `CapabilityGrant` | actor、asset、permissions、policy_refs、approval_ref；只來自可信 host 設定 | `src/capabilities/runtime.py:104-111` |
| `LocalPolicy` | default-deny，以 (actor, asset) 為鍵；`owner_mode` 下模型自選的非 read 副作用需本人確認 | `src/capabilities/runtime.py:114-181` |
| 核准契約 | `ApprovalRequest`（business/technical_policy/execution 三層）；另有 BackendDataApproval、GatewayHostApproval 等領域核准；**沒有通用 ApprovalDecision** | `src/common/execution.py:209-216`；`src/agent/data_policy.py:69` |
| DUT | 兩個 DUT 能力 `approval_required`；runtime 依序檢查 admit、actor 綁定、identity、`physical_enabled`、非模擬器、Skill、儀器 | `src/capabilities/dut_engineering/handlers.py:22, 43`；`src/dut/runtime.py:153-188`；`docs/ARCHITECTURE.md:845-858` |
| 裝置設定檔 | company_workstation = dedicated_user/corporate_internal/**single_user**；shared_test_workstation = shared_user/external_only/cooperative_workspace；`interactive_slots == 1` | `src/common/enrollment.py:68-95` |
| 一機一 member | `device_single_user`；共用測試機綁虛擬 member | `src/control_plane/enrollment.py:385-390`；`docs/ARCHITECTURE.md:883-893` |
| `on_behalf_of` | 只記錄，不參與授權；company workstation 拒絕 `delegation_not_allowed` | `src/common/local_agent.py:76-80`；`src/host_runtime/agent.py:164-165` |
| 資料分類 | INTERNAL 只送公司內部 Gateway，不送外部 agent | `docs/DECISIONS.md:4176` |

### 2.6 Workflow、MCP

| 元件 | 現況 | 出處 |
|---|---|---|
| Workflow 引擎 | **嚴格循序**：`_drive_steps` 逐步 await；無 parallel/fan-out/depends_on；`dispatch.py` 的 RLock 序列化所有寫入與 workflow run | `src/workflow/engine.py:1, 1047-1118`；`src/workflow/dispatch.py:51-56` |
| 步驟模型 | 單一 `WorkflowStep`（capability、inputs、retry 1–3）；`StepInput` 是唯一資料依賴 | `src/common/assets.py:240, 265-274` |
| Run 層冪等 | (actor, namespace, idempotency_key)，最多 50 key | `src/workflow/engine.py:68, 342-439`；`src/workflow/checkpoints_sqlite.py:44-57` |
| MCP（AEP 自己提供） | `aep`（authoring, stdio）、`aep-assistant` | `src/host_runtime/mcp_server.py:45, 243`；`src/host_runtime/agent_setup.py:49-51` |
| MCP（使用者加的） | `McpHub`，`<workspace>/mcp-servers.json`，每個工具變成能力 `mcp-<server>/<tool>@1.0.0`，secret 在 `AEP_MCP_<SERVER>_<KEY>` | `src/host_runtime/mcp_servers.py:5, 46, 87-88, 124` |

### 2.7 遙測、Atlas、CI、benchmark

| 元件 | 現況 | 出處 |
|---|---|---|
| 遙測 schema | `aep.telemetry.v1` `TelemetryEvent`（run_id、trace_id、span_id、**parent_span_id**…）；run kinds 不含 delegation | `src/telemetry/events.py:25-33, 68-80` |
| Token 統計 | 每次呼叫 `llm.completed`；per-run llm_calls、input/output tokens；**只記 alias、沒有成本／預算** | `src/models/approved.py:13-29`；`src/telemetry/recorder.py:57-59, 286-289, 349-357` |
| 遙測 API | GET-only、loopback-only；`runs` 可用 `parent_run_id` 過濾 | `src/host_runtime/telemetry_api.py:66-129` |
| Atlas | 外部儀表板消費者，**尚未建置** | `docs/telemetry/AEP_ATLAS_TELEMETRY_CONTRACT.md:3, 11` |
| CI | 單一 `verify` job（windows）：pytest、ruff、format、mypy、build、Windows preview 與 Shared Platform preview 冒煙測試；push main 與 PR 觸發 | `.github/workflows/verify.yml:8-321` |
| Benchmarks | `authoring_v1`、`business_workflow_lab`、`coding_v1`（20 題）、`knowledge_v1`（1,100 題）、`w13_parity` | `benchmarks/*` |
| Fixtures | `tests/fixtures/harness_skills/`、`e2e_01..05`、`routing_cases.json`、`bi_vault_example` | `tests/fixtures/` |
| Hermes profiles（只看名稱） | emailagent、instrumentagent、reportagent、teamopsagent | `%LOCALAPPDATA%\hermes\profiles\` |
| 分支保護 | `main` `protected: false` | `gh api repos/dragon0816/agentic-engineering-platform/branches/main` |

## 3. 重用／缺口矩陣

| 計畫要的東西 | 判定 | 依據與做法 |
|---|---|---|
| AgentDefinition（id/version/owner/visibility/status） | **existing** | `AgentProfile` + `AssetMetadata`；版本、owner、visibility、lifecycle、發佈、選取都已有 |
| description/skill_refs/tool_refs/domains | existing（domains 缺） | `skills`、`allowed_capabilities`、`knowledge`；domains 可用 `selector_hint` 式欄位補 |
| model_policy_ref | **extend** | `model_requirements` 只描述能力，不指定 alias／分類規則；加 `model_policy` 參照 |
| resource_limits／step budget／timeout | **extend** | `max_turns`/`max_retries` 存在但無人讀；加 `max_tool_calls`、`time_limit_s`、`max_output_chars` |
| requested_permissions | existing | `allowed_capabilities` 就是 allowlist；授權仍由 `DeviceAuthorization`+`LocalPolicy` |
| Admin API／版本化／停用 | existing | Shared Platform 發佈、lifecycle、`NameAccess`；不需新 registry |
| Session | existing | Agent Web conversation、Telegram chat、`session_id` |
| Run（策略、policy snapshot） | **extend（Phase 2）** | 先用遙測 run + 父 session ledger；需要時再加持久欄位 |
| 策略選擇 direct/delegation/workflow | **extend** | `RouteDecision.kind` 已有 agent；delegation 由父 agent 以工具呼叫決定（ADR-MA1） |
| Ephemeral AgentInstance | **new（小）** | 不持久化；以子對話的 telemetry run（`parent_span_id`）表示 |
| DelegationTask／結果 | **new** | 參考 `TaskContract`；結構化 task/result 契約（ARCHITECTURE.md:989 要求） |
| Eligibility filter | extend | `validate_profile` 已做「全部參照已允許」；改為每次委派時檢查 |
| Candidate ranker | **defer** | 無基準資料；規則 8 偏好確定性路由 |
| 平行派工 | **defer** | Workflow 引擎循序；需另行設計 |
| 多 gateway 路由／fallback | **defer** | 目前 session 模型 + 單一核准 URL |
| 成本預算 | **defer（只記 token）** | src 無成本；先記 token 與子代理數 |
| 每次工具執行重查授權 | existing | Bridge policy 每次 dispatch；子對話走同一路徑即可繼承 |
| Agent identity（同機多 agent） | **new（Phase 4）** | 目前只有 actor；V1 子代理以父 actor 執行，effective = 交集 |
| 跨 Bridge 排程 | defer | 一機一 member；remote 是 typed job |
| Atlas 追蹤 | defer | Atlas 未建置；先寫 AEP 遙測 |

## 4. 計畫中的錯誤假設

1. **PR 與 branch protection（source:174-177）。** repo 規則是驗證過直接 commit 到 `main`、不需 PR（`AGENTS.md:77`，來源 `docs/DECISIONS.md:3571` 2026-10-19 ADR-K9 option A）；`main` 沒有保護（`protected: false`）。計畫自己說「與 Leo 協調衝突」——建議維持現行規則，PR 描述欄位改寫在 commit message／`docs/TASKS.md`。
2. **tenant/team、多租戶 Session（source:79、108）。** 架構是**每台機器綁一個 member**、本機 Agent 以該 member 身分執行（`ARCHITECTURE.md:883-893`；`enrollment.py:385-390`）；沒有 tenant。Team Platform 是控制平面，不是共用執行環境（`ARCHITECTURE.md:865-881`）。「並行 session 互相隔離」在同一台機器上其實是「同一人」的多個 session，跨人隔離發生在機器之間與 Shared Platform 的 entitlement。
3. **需要新建 Agent Registry 與 admin API（source:120-126）。** 已存在：`AgentProfile` 是 `agent` 資產，經 Shared Platform 發佈／選取／安裝（`CONTRACTS.md:1635-1657`）。新建會違反「避免重複 registry」（source:85 自己也這樣要求）。
4. **用既有 Workflow 引擎平行派工（source:96）。** 引擎嚴格循序、寫入被 RLock 序列化（§2.6）。
5. **多 gateway profiles 與 fallback（source:22、147）。** 目前是 session 選模型（`DECISIONS.md:4687`）、資料核准綁定單一 Gateway URL（`DECISIONS.md:4565`）、INTERNAL 只能走內部 Gateway（`:4176`）。fallback 到另一個 provider 會碰到資料核准，不是單純路由。
6. **成本預算（source:83、95）。** src 沒有成本計算，只有 token（且 provider 未回報時為 null）。
7. **「auth checks 在 Phase 1 開始」與「policy service fail closed」（source:109、113）。** AEP 沒有獨立 policy service；授權是 host 本地 default-deny（`LocalPolicy`），本來就 fail closed。
8. **Hermes／Muse parity（source:30）。** Hermes 本機有 4 個 profile（emailagent、instrumentagent、reportagent、teamopsagent）；它們是**另一個系統**的設定，不是 AEP profile 的來源，本審查未讀其內容。
9. **CLI 後端（Codex/Claude Code）也能當子代理。** CLI 後端是純文字、不進 AEP Gateway loop、不跑 AEP 工具（`docs/archive/MULTI_BACKEND_ORCHESTRATOR_PHASE0.md` 執行路徑表），且 INTERNAL 資料不得外送；V1 不適用。

## 5. 依賴圖

```text
Phase 0.5
  G4 記帳修正 ─┐
  G5 跨領域負向測試 ─┼─> Phase 1 (profile 契約擴充, flag)
  P0-2 重試冪等快取 ─┘          │
                               v
                     Phase 2 (agent__delegate 子對話, depth 1,
                              父 session ledger, 遙測 parent run)
                               │
              ┌────────────────┼──────────────────┐
              v                v                  v
   Phase 3 (選擇:        Phase 4 (模型政策,    Phase 5 (benchmark
    explicit/may_        per-agent identity,   baseline, 7 情境,
    delegate_to/hint)    DUT/MCP 負向測試)     Agent Web 呈現)
              └────────────────┴───────┬──────────┘
                                       v
                       Deferred: ranker, 平行, 多 gateway, 跨 Bridge
```

外部依賴：P0-1 內容檢查器（部分完成）讓子代理結果的驗收更有意義，但不阻擋 V1；Atlas 未建置，不阻擋。

## 6. 風險登記

| # | 風險 | 可能性/影響 | 緩解 |
|---|---|---|---|
| R1 | 子代理重試重做副作用（P0-2 未解） | 中/高 | Phase 0.5 先做冪等快取；子代理預設只允許 read，寫入需父的核准流程 |
| R2 | 權限擴大：profile allowlist 被當成授權 | 低/高 | effective = 父 actor 授權 ∩ profile allowlist（ADR-MA4）；負向測試 |
| R3 | INTERNAL 資料經子代理流向外部 | 低/高 | 子代理一律走 `ApprovedModelClient` 與 `DataPolicy`；CLI 後端不能當子代理 |
| R4 | 子代理宣稱完成但無證據 | 中/中 | 子結果經 claim check（`no_unbacked_action_claim`）＋父的 Host checks；G1：未通過但有輸出原樣回傳並標註 |
| R5 | token／時間暴增（150 呼叫 × N 子代理） | 中/中 | 子代理數上限、子對話自己的工具／輪數／時間上限，且計入父回合時間上限 |
| R6 | 重啟中斷子代理（規則 19） | 中/中 | 子對話屬於父回合，`/api/activity` 已把進行中回合視為活動；子狀態不持久化 → 重啟被拒而不是遺失 |
| R7 | 子代理產物遺失或可被他人附檔（規則 20） | 低/中 | 產物寫入父 session、父 actor 的 ledger；子代理沒有自己的 session |
| R8 | 子代理重問使用者已給的資訊（規則 18） | 中/低 | 子代理不能直接問使用者；缺資訊回 `needs_input` 給父，由父彙整 |
| R9 | 計畫範圍蔓延（ranker、平行、多 gateway） | 高/中 | 明確 defer；Gate 0 核准 V1 範圍 |
| R10 | Hermes 4 個 profile 期望被一比一搬遷 | 中/低 | 列為開放問題 Q7 |

## 7. 分階段估計（工作天，單人 + agent，含測試）

| 階段 | 內容 | 估計 |
|---|---|---|
| 0.5 | G5 測試組、P0-2 冪等快取、G4 記帳 | 3–5 |
| 1 | `AgentProfile` 擴充（model policy ref、limits）、CONTRACTS、flag、相容測試 | 2–3 |
| 2 | `agent__delegate`、子對話、ledger、遙測、guards 負向測試 | 5–8 |
| 3 | 選擇（explicit/`may_delegate_to`/`selector_hint`）、no-eligible fallback、Agent Web/Telegram 顯示 | 3–5 |
| 4 | per-agent 模型政策、DUT/MCP/分類負向測試、agent identity 設計 | 4–6 |
| 5 | 7 情境 baseline 量測、使用者文件、rollback | 3–5 |
| 合計 V1 | | **約 20–32 天** |

數字是粗估，沒有基準；Phase 2 完成後重估。

## 8. ADR

### ADR-MA1：直接執行 vs 委派 vs Workflow

- **A. 只有直接執行（現狀）**：最簡單、可預測；無法隔離 context 或用不同模型／Skill 組合。
- **B. 委派作為工具（agent-as-tool）**：父 agent 在 Gateway loop 內呼叫 `agent__delegate`，拿回結構化結果繼續。符合 `ARCHITECTURE.md:983-989`；父仍對使用者負責；需要上限與驗收。
- **C. 加一個前置「策略路由器」**（source:57-61）自動決定三選一：多一層 LLM 決策，違反規則 8（確定性優先），且與 Gateway／Agent 的職責切分（`ARCHITECTURE.md:931-936`）重疊。
- **D. Workflow**：確定性、可續跑、有核准；但不能做推理，且引擎循序。
- **建議：** 確定性路由不變（已知命令、已知 Workflow 先走）；推理路徑中由**父 agent 自己**決定是否委派（B）；Workflow 維持「HOW EXACTLY」。不做 C。策略記在遙測（工具呼叫本身就是紀錄），不另建 Run 策略欄位。因為委派是工具呼叫而不是路由結果，`src/agent/routing.py:46-47` 對 `agent` 路由的拒絕**維持不變**。

### ADR-MA2：持久定義（`AgentProfile`）vs 臨時實例

- **A. 新建 `AgentDefinition` 契約與 registry**：與 `AgentProfile` 重複，違反規則 11/14 的單一治理資產。
- **B. 擴充 `AgentProfile` 為定義；實例臨時、不持久化**：重用發佈、選取、安裝、啟用驗證；實例只是父回合裡的一個子對話，以遙測 run（`parent_span_id`）追蹤。
- **C. 持久化 AgentInstance 表**：可以續跑，但子對話本來就 bounded 且屬於父回合；持久化帶來規則 19 的狀態恢復負擔。
- **建議：B。** 契約變更走 `contract-development` skill；新欄位都有預設值，舊 profile 檔不變（向後相容）。

### ADR-MA3：每個 agent 的模型政策與 gateway 路由

- **A. 子代理沿用 session 模型**（`DECISIONS.md:4687`）：零新增；不能用不同模型。
- **B. Profile 帶 `model_policy` 參照：允許的 routing alias 清單＋偏好**，只能在**已核准的同一 Gateway** 內選（LiteLLM Gateway 一個 URL 多模型），資料核准不變；不符合 → 退回 session 模型或拒絕。
- **C. 多 Gateway、跨 provider fallback、成本上限**：碰到資料核准（綁 URL）與 INTERNAL 規則，需要新的核准模型。
- **建議：V1 = A 為預設，B 在 Phase 4 加入（同一 Gateway 內的 alias allowlist + `ModelRequirements` 檢查）**；C defer。分類規則（INTERNAL）永遠是硬閘門，由 `DataPolicy` 判，不在 profile 裡覆寫。

### ADR-MA4：Host + Shared Platform 的多使用者權限模型

- 現況：Shared Platform 決定「誰看得到／可安裝」（`entitled()`，不等於可執行）；機器決定「誰能執行」（`DeviceAuthorization` + `LocalPolicy` per actor）；一機一 member。
- **A. 子代理以父 actor 身分執行，effective grant = 父 actor 的有效授權 ∩ profile allowlist（`allowed_capabilities`、`skills`、`knowledge`）∩ 本次委派請求的工具子集**：不需新身分；不會擴權；與 `host.py:1148-1162` 的「profile 只能縮小」一致。
- **B. 每個 agent 一個獨立 principal 與自己的 grant**：可做同機多 agent、各自稽核；但需要改 grant 鍵（actor → actor+agent）、Shared Platform 選取模型、核准流程，影響面大。
- **C. Registry 可見即可用**：違反規則 13。
- **建議：V1 = A。** 遙測與稽核記錄 `agent=<profile key>` 屬性（不是授權依據）。核准仍由父 actor 本人按（`owner_mode`）；DUT／instrument 規則不變（子代理呼叫 DUT 能力時一樣需要 `approval_ref` 與 `physical_enabled`）。B 列為 Phase 4 設計題目，不實作。Fail closed：任何參照缺失或授權查詢失敗 → `delegation_refused`。

### ADR-MA5：context 與產物隔離、深度與上限

- **Context**：子代理只拿到 objective、父指定的輸入產物 id、profile 的 Skill／Knowledge；**不帶父的對話歷史**（最小 context）。子代理不能讀其他 session 的 ledger。
- **產物**：子代理產生的 run、檔案記入**父 session、父 actor** 的 `SessionLedger`（規則 20），標註來源 agent；子代理沒有自己的 session。
- **深度與上限**：depth = 1（子代理的工具集合中移除 `agent__delegate`）；每回合子代理數上限（建議預設 3）；子對話工具呼叫上限（建議 ≤ 20）、輪數 ≤ profile `max_turns`、時間計入父回合的 `turn_time_limit`；相同呼叫／相同失敗 guards 原樣套用；觀察字數上限套用。
- **規則 18**：子代理不能直接問使用者；缺資訊回 `needs_input` 給父，父依規則 18 只問缺的必要值。
- **規則 19（重啟安全）**：子對話是父回合的一部分，進行中回合已被重啟前的活動檢查涵蓋；子狀態不持久化，因此重啟必須等待或被拒，而不是中斷後恢復。
- **規則 20**：見上「產物」；結果摘要（「結果摘要」）由父統一產生。
- **G1–G4 與 claim check**：子結果回到父時 (G1) 未通過驗收但有輸出 → 原樣回傳並附 Host 註記；(G2) 錨點是**使用者原句**與父給的 objective；(G3) 子代理依 profile 綁定資產選 Skill；(G4) 輸出長度遵守子對話上限。子代理的最終回答也跑 `no_unbacked_action_claim`：宣稱寫檔／執行卻無對應成功工具紀錄 → 標為未驗證。
- **替代方案**：共享完整父歷史（簡單但洩漏 context、耗 token）；子代理各自 session（違反規則 20 的「本 session 記得」）。
- **建議：** 如上。

## 9. 建議的 V1

1. **擴充 `AgentProfile`**（向後相容、都有預設）：`model_policy`（參照：alias allowlist，Phase 4 才生效；V1 預設沿用 session 模型）、per-instance limits：`max_tool_calls`、`time_limit_s`（`max_turns`、`max_retries` 開始被讀）。
2. **在 feature flag（預設關）後解除 `may_delegate_to` 拒絕**（`profiles.py:73`），只允許深度 1；目標 profile 也必須通過 `validate_profile` 的所有檢查。
3. **新增 host tool `agent__delegate(profile, objective, input_artifact_ids)`**：以 `GatewayConversationRequest` 在**同一個 Gateway loop**、同一套 guards 與 `ApprovedModelClient` 跑有界子對話（參考 `task_execution.py:100-156` 的 allowed_tools 推導與 `DataPolicy` 檢查）；結果是結構化的 `{status, answer, artifacts, tool_calls, stop_reason, validation}`。
4. **產物記入父 session ledger**；遙測新增子 run 以 `parent_span_id` 連到父回合（若需新 run kind，屬契約變更，Phase 2 一起提）。
5. **選擇**：使用者明確指定 > 父 profile 的 `may_delegate_to` > 目標 profile 的 `selector_hint` 提供給父模型參考；**沒有 ranker**；沒有合格候選 → 父直接執行或回 `needs_input`。
6. **平行**：Workflow 引擎**不支援**（循序），V1 不做平行；若需要，Phase 3 之後另設計「`agent__delegate` 多目標、有上限的 asyncio 並行」，仍走同一 guards。
7. **只支援 Gateway 後端的父**；CLI 後端（Codex/Claude Code/Copilot）父不能委派。
8. **Deferred**：ranker、多 gateway 路由與 fallback、跨 Bridge 排程、同機多 agent identity、成本上限。

## 10. Phase 0.5 前置

- **G5**：建立 `tests/test_harness_cross_domain.py`（目前不存在），四個領域各一個刻意錯誤輸出必須被 Host checks 拒絕，停止原因與遙測 phase 一致（`docs/archive/HARNESS_GAP_PLAN.zh-TW.md` P2-1；`docs/phases/HARNESS_6_LAYER_INCREMENTAL.md:13`）。之後子代理結果也加一題。
- **P0-2**：同一回合內 `(能力, 參數雜湊)` 的非 read 成功呼叫冪等快取，重試時回傳先前結果（`HARNESS_GAP_PLAN` P0-2）。目前只有 Workflow run 層冪等（`engine.py:342-439`），沒有工具層。
- **G4 記帳**：G4 實質已在 U2/U3（2026-10-09）完成（`HARNESS_DESIGN.zh-TW.md:15-26`），但 `HARNESS_DESIGN.zh-TW.md:58` 仍寫「G4…仍未完成」、`docs/TASKS.md:923` 仍是 `[ ] G4–G6`。修正為 G4 done、G5/G6 open。
- （不阻擋）P0-1 內容檢查器部分完成；G6 Agent Web 證明。

## 11. 建議 Issue 拆分（只寫在文件，未建立）

| 階段 | Issue（建議標題） | 標籤 |
|---|---|---|
| 0 | Approve multi-agent Phase 0 review and ADR-MA1–MA5 (Gate 0) | decision-needed |
| 0.5 | Add the cross-domain negative harness suite (G5) | implementation |
| 0.5 | Cache side-effecting tool results within a turn for retries (P0-2) | implementation |
| 0.5 | Mark G4 done in HARNESS_DESIGN and TASKS | implementation |
| 1 | Extend AgentProfile with model policy reference and instance limits | implementation |
| 1 | Allow may_delegate_to behind a flag, depth 1 | implementation |
| 2 | Add the agent__delegate host tool running a bounded sub-conversation | implementation |
| 2 | Record sub-agent artifacts in the parent session ledger and telemetry | implementation |
| 3 | Select delegation targets by explicit choice, may_delegate_to and selector_hint | implementation |
| 3 | Show sub-agent results in Agent Web and Telegram | implementation |
| 4 | Restrict sub-agent models to an alias allowlist on the approved Gateway | implementation |
| 4 | Negative tests: DUT, MCP, INTERNAL routing through a sub-agent | implementation |
| 4 | Design per-agent identity for several agents on one machine | decision-needed |
| 5 | Measure the 7-scenario baseline (direct vs delegation vs workflow) | verification |

依 AGENTS.md:77，每個 implementation issue 由完成它的 commit（`Closes #N`）直接進 main，不開 PR。

## 12. Benchmark 基準定義（只定義，不跑；不用真實 Bridge 或硬體）

共同量測：成功率、選擇正確率、latency p50/p95、llm_calls 與 input/output tokens（`llm.completed`）、重試、policy 拒絕、工具失敗；三種模式 direct / delegation / workflow 各跑一次。**數值門檻在 baseline 量測後才定**（source:169）。

| # | 情境（source:161-167） | 對應現有 benchmark／fixture | 基準定義 |
|---|---|---|---|
| 1 | 只需 Knowledge | `benchmarks/knowledge_v1`（選一組 RF/Wi-Fi 題）、`tests/fixtures/harness_skills/knowledge-evidence*.json` | direct 路徑答案通過 `claim_support`；delegation 模式量「不必要的子代理次數」（期望 0） |
| 2 | 平行分析兩份文件 | 無現成；用 `tests/fixtures/robotics_kb_sample` 式的合成雙文件 | V1 循序兩次委派 vs direct；量 provenance 完整度（每段結論帶來源 id） |
| 3 | Coding（parser＋測試） | `benchmarks/coding_v1`（20 題，獨立 validator）、`harness_skills/coding-verify.json` | 選 3 題 log-parser 類，沙箱 `declared_commands` 通過率 |
| 4 | Workflow（SOP→code→test→review，模擬失敗） | `tests/fixtures/e2e_01..05`、`benchmarks/business_workflow_lab`、`harness_skills/workflow-check.json` | 注入一步失敗；量 `steps_succeeded` 與續跑是否重做副作用（依賴 P0-2） |
| 5 | Bridge 安全（CMP180 無 grant） | DUT 模擬器（`src/dut/runtime.py` 非 physical 拒絕路徑）、現有 DUT 測試 | 無 grant → 拒絕＋遙測 policy-denied；mock device + approval_ref → 只在模擬器成功；**不碰真機** |
| 6 | 模型路由（INTERNAL 不外送；gateway 故障） | `DataPolicy` 測試、`tests/test_conversation_models*` | INTERNAL objective 經子代理 → 外部 backend 0 次；Gateway 停機 → `needs_input`／失敗，**不自動 fallback 到未核准 provider** |
| 7 | 多使用者隔離 | Session ledger 測試（`session__attach_file` 只能附本 session、本人）、Shared Platform `entitled()` 測試 | 同機兩 session、兩 actor（測試替身）互相附檔／讀 ledger → 0 成功；跨機以 entitlement 測試代表 |

## 13. 開放問題（附預設）

1. **維持直推 main、不開 PR？** 預設：**是**（AGENTS.md:77；計畫 §9 的 PR 欄位改寫進 commit message 與 TASKS）。
2. **先做 G5 與 P0-2？** 預設：**是**。
3. **擴充 `AgentProfile` 而不是新建 AgentDefinition？** 預設：**是**。
4. **V1 允許 CLI 後端的父委派？** 預設：**否**。
5. **子代理數上限＋token 記錄，baseline 前不設硬成本上限？** 預設：**是**（每回合子代理上限預設 3）。
6. **子代理是否允許非 read 能力？** 預設：**V1 只允許 profile allowlist 內、且父 actor 已授權者；寫入照常要本人確認**（不另開例外）。
7. **Hermes 的 4 個 profile（emailagent、instrumentagent、reportagent、teamopsagent）要不要成為第一批 AEP profiles？** 預設：**不在 V1**；V1 只用 `engineering` + 一個 `knowledge` 或 `coding` 專家 profile 驗證機制。
8. **子代理 run 是否新增遙測 run kind（如 `agent_delegation`）？** 預設：**是，Phase 2 一起提契約變更**；否則只用 `conversation_turn` + `parent_span_id`。
9. **`agents/engineering.json` 由 draft 改 published 並加上 `may_delegate_to`？** 預設：**Phase 1 以新版本發佈，舊版不動**。
10. **結果是否要在 Gate 0 時把 ADR 寫入 `docs/DECISIONS.md`？** 預設：**owner 核准後才寫**。

## 14. 審查限制

- 三個平行探查都已回報並整合；引用的行號已抽查（AGENTS.md:77、DECISIONS.md:3571、profiles.py:73、routing.py:46-47、gateway.py:1012、engine.py:1047-1056、approved.py:13-29、telegram.py:560-567、host.py:2253-2261）。
- 未執行任何測試或 benchmark（文件變更，不需要）；未讀 Hermes profile 內容；未建立 issue。
