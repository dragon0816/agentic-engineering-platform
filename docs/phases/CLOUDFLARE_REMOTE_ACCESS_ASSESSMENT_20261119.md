# Cloudflare 遠端存取 AEP Agent Web 評估（2026-11-19，唯讀評估，未改程式）

Owner 問題：能否整合 Cloudflare，讓其他電腦的 browser 也能用放在公司 PC 的 AEP（Agent Web，`http://127.0.0.1:53583`）。
本文件只評估，不構成決策；任何程式改動都屬 harness（web 認證/路由/權限閘），須依 AGENTS.md 第 22 條取得 owner 範圍明確的同意。

## 0. 結論

- **技術上可行**：Cloudflare Tunnel（`cloudflared`）是由 PC 主動向外連線的 connector，PC 不需開任何入站埠；
  Cloudflare Access 在邊緣先驗證身分，再把請求轉到 PC 上的 `127.0.0.1:53583`。
- **但 AEP 現況「零程式改動」無法直接用**：Agent Web 刻意拒絕非 loopback 的 `Host`，且頁面以「首次 URL 帶 token」開啟。
  `cloudflared` 可以把 `Host` 改寫成 `127.0.0.1`（`httpHostHeader`）繞過，但這等於讓 AEP 的第 3 道防線失效，需配套。
- **最大的問題不是技術，是公司 IT/資安**：把公司 PC 上會執行工具、讀公司資料、持有公司 model token 的服務接到網際網路，
  不屬於 AEP「工具不需 IT 核准」的範圍（那是工具安裝/執行，不是網路暴露）。2026-10-28 的 BI vault 決策已明確寫過：
  「Tailscale 或 Cloudflare Tunnel… 會在公司 LAN 旁開一條路，需要 IT/資安先同意」。本評估維持此立場。
- **建議**：先問 IT 是否已有公司 VPN / 公司核可的 ZTNA（Zscaler 本身就有 ZPA 類產品，需確認公司是否採用）；
  若 IT 同意使用 Cloudflare，走方案 B（Access + AEP 小幅「遠端模式」改動），不要走裸露的 quick tunnel。

## 1. Agent Web 現況（從程式碼確認）

`src/host_runtime/web.py` 模組說明與 `_Handler`：
1. `AgentWebServer` 綁 `("127.0.0.1", port)`（L7323），預設埠 53583（`launcher.py` `DEFAULT_PORT`）；owner 2026-09-24 決策「只聽 loopback」。
2. `do_GET` / `do_POST` 第一步 `_host_is_loopback()`（L6353）：`Host` 不是 `127.0.0.1/localhost/::1` 一律 403。
3. `/` 以 `?token=` 開啟（每次啟動新產生，印出一次），頁面把 token 放進 `sessionStorage`，之後每個 API 帶
   `Authorization: Bearer`（`_authorized`，constant-time 比對）。刻意不用 cookie（避免 CSRF）。重新整理走 `RELOAD_PAGE`。
4. Origin 檢查只在部分路由：排程 `schedule_web.origin_allowed`、telemetry `_LOCAL_ORIGIN`、BI feed 皆只接受 loopback Origin；
   其他 API 靠「Bearer header + 不回應 preflight」防跨站。
5. **不需 token 的公開路由**（在 token 檢查之前）：
   - `/api/v1/telemetry/*`（Atlas 讀遙測，owner 2026-10-08），含 `/api/v1/telemetry/stream` **WebSocket**；
   - `/api/v1/bi/*`（BI 分析 feed，Atlas 讀，owner 2026-11-01，`feature_plugins/bi_knowledge/.../bi_feed_api.py`）；
   - `/view/file?nonce=`（沙箱 HTML viewer，nonce 15 分鐘有效，由已授權頁面取得）。
   這些今天只靠「只有本機到得了」保護；一旦透過 tunnel 改寫 Host，就會變成網際網路可讀（若前面沒有 Access）。
6. `/mcp`、`/mcp/authoring`、`/mcp/agent`：MCP over HTTP，靠 assistant token / turn token。
7. 上傳上限：一般 256 KB，SOP 28 MB，附件 36 MB，語音 14 MB（`MAX_*_BYTES`）。
8. 頁面 API 呼叫皆為相對路徑（可走任何 origin）；但部分功能寫死 loopback：
   Atlas 嵌入只接受 loopback Atlas（`web_page.py` `atlasEmbedAddress`）、`/api/assistant/mcp-config` 回 `http://127.0.0.1:port`、
   Gateway/Shared Platform 設定顯示 `127.0.0.1:...`。遠端 browser 上這些會失效或顯示不可用的位址。
9. **「Laya tunnel」不是遠端存取路徑**：`host_runtime/laya.py` 的 `SshTunnel` 是 PC 向外 `ssh -N` 到 Laya 主機做 decision
   acceleration（本機埠轉到 Laya），方向相反，不能讓外部 browser 連進 Agent Web。
10. 現有真正的遠端通道只有 **Telegram**（`telegram_loop.py`，同一個 Agent、ingress 不同、無 Web UI）。
11. Shared Platform（172.25.228.141:8775-8776）只在辦公室 LAN 可達（公司 VPN 也到不了，見 DECISIONS 2026-10-28），不是解法。

## 2. 可行性逐項

| 項目 | 經 Cloudflare Tunnel 的情況 | 是否需改 AEP |
|---|---|---|
| HTTP 轉送到 127.0.0.1:53583 | `cloudflared` ingress `service: http://127.0.0.1:53583` 即可 | 否 |
| `Host` loopback 檢查 | 外部 Host 是 `aep.<你的網域>` → 403。可用 `originRequest.httpHostHeader: 127.0.0.1` 改寫 | 不改也能動，但正確作法是加「允許的遠端主機名」清單 |
| Origin 檢查（排程/telemetry/BI feed） | browser 送 `Origin: https://aep.<網域>` → 排程頁 403 | **是**，至少排程頁要認得遠端 origin |
| 首次 token URL | 遠端使用者沒有 token；token 每次重啟都變；放在 URL 會進瀏覽紀錄 | 建議改為「Access 身分即登入」或一次性登入碼 |
| sessionStorage | 同一 origin 下照常運作（只是 origin 換成 https 網域） | 否 |
| cookie / CSRF | AEP 不用 cookie；Access 會設 `CF_Authorization` cookie（Cloudflare 自己的） | Bearer 設計保留即可 |
| 公開路由 | 若只靠 Access 擋，公開路由也在 Access 後面（OK）；若 Access 設錯就直接外洩 | **是**，遠端模式下應拒絕公開路由或要求 Access JWT |
| WebSocket（telemetry stream） | Cloudflare Tunnel 支援 WebSocket | 否（但遠端通常不需要此路由） |
| 長請求 | Cloudflare 代理對「等待回應」有逾時（一般方案約 100 秒回 524，需確認現行數值）；`/api/knowledge/ask`、`/ask` 等同步路由若超過會被切斷，背景工作本身不受影響 | 視路由而定；聊天若是輪詢 progress 則無礙（需逐路由確認） |
| 上傳大小 | Cloudflare 免費方案請求本文上限約 100 MB（需確認）；AEP 最大 36 MB，在範圍內 | 否 |
| Atlas 嵌入、MCP config、Gateway 位址 | 寫死 loopback，遠端失效（顯示 fallback） | 可接受；或遠端模式下隱藏 |
| `ThreadingHTTPServer` 無 TLS | TLS 在 Cloudflare 邊緣終結，edge→cloudflared→本機為加密隧道 + 本機明文 loopback | 否 |

## 3. 安全

**為何 Cloudflare Access 是必要條件（絕不能裸 tunnel）**
- Agent Web 能執行 Workflow、工具、coding agent、讀公司 Knowledge/BI、使用公司 model token；等同遠端操作這台 PC。
- 裸 tunnel（含 `trycloudflare.com` quick tunnel，網址隨機但公開、無身分驗證）會讓任何拿到網址的人直接打到 AEP；
  公開路由（telemetry、BI feed、`/view/file`）完全不需 token。quick tunnel 也不適合長期使用（無 SLA、網址會變，需確認現行限制）。
- Access 在邊緣驗證身分（Email 一次性 PIN、或 Google/GitHub/Entra ID 等 SSO），只放行 policy 指定的帳號，未登入的請求根本到不了 PC。

**AEP 本身應補的防線（方案 B）**
1. 遠端模式設定旗標（`host.json`，預設關），關閉時行為與今天完全相同。
2. 允許的遠端主機名清單（取代「Host 必須是 loopback」的單一條件），Origin 檢查同步認得這些主機名。
3. 驗證 `Cf-Access-Jwt-Assertion` header：以 Access team 網域的公鑰（`/cdn-cgi/access/certs`）驗簽、驗 `aud`（Application AUD tag）、
   驗 email 在允許名單；遠端主機名下沒有有效 JWT 一律 401。防止有人繞過 Access 直接打到 tunnel（或 Access 設定錯誤）。
   需注意：標準庫無 RS256 驗簽，可能需要 `cryptography`/`PyJWT` 類套件（公司 PC 以 `--no-index` 安裝，需評估打包，需確認）。
4. 遠端主機名下關閉公開路由（telemetry、BI feed、`/mcp*`），`/view/file` 也要求 JWT。
5. 以 Access 身分取代 token URL：遠端首次進入時，伺服器在驗過 JWT 後發 page token（或另一把遠端 session token，
   可撤銷、有效期短），不把 token 放進網址。
6. 稽核紀錄：記錄遠端請求的 Access email、時間、路由與狀態（不記內容，延續「不記使用者文字」原則）。
7. 遠端可停用高風險頁（例如 coding agent 全權模式、Settings 中的憑證/Gateway 設定），由 owner 決定。

**暴露公司 PC 的風險（owner 需自行與 IT 衡量）**
- 資料：BI、Knowledge、對話、附件都會經過 Cloudflare 邊緣（TLS 在 Cloudflare 終結，Cloudflare 可見明文）；公司資料離開公司網路。
  owner 11-17 表示 BI/Wiki 無敏感資料，但對話、上傳附件、model token 使用不在此範圍。
- 公司政策：`cloudflared` 是常駐對外連線，可能違反公司遠端存取/影子 IT 政策；Zscaler 可能攔截或解密（TLS inspection）
  `cloudflared` 的連線（QUIC/7844 埠被擋時會退回 HTTP2/443，需確認在 Zscaler 下能否連線）。這是公司 IT 的合法控管，不應繞過。
- PC 上的憑證：AEP 使用的公司 model token、SSH key（laya）、Shared Platform 憑證都在這台 PC；遠端被冒用等於全部外洩。
- PC 需一直開機且 Agent Web 在跑；重開機後 token 變動（方案 B 的 Access 登入可解決）。

**與既有通道比較**
| 通道 | 方向 | 身分 | 資料經第三方 | 備註 |
|---|---|---|---|---|
| Laya SSH tunnel | PC→Laya 外連 | SSH key | 否（公司內） | 不提供遠端 UI |
| Telegram | PC 外連輪詢 Telegram | Telegram 帳號/chat 允許清單 | 是（Telegram） | 已核可在用，無完整 Web UI |
| Cloudflare Tunnel + Access | PC 外連 Cloudflare | Access 身分（OTP/SSO） | 是（Cloudflare 終結 TLS） | 完整 Web UI，暴露面最大 |
| 公司 VPN | 使用者連進公司網路 | 公司帳號 | 否 | 但 Agent Web 只聽 loopback，仍需改綁定或本機轉送 |

## 4. 方案（依工作量）

**A. 不改程式：`cloudflared` + Access（約半天設定；不建議長期使用）**
- Owner 需要：Cloudflare 帳號、一個託管在 Cloudflare DNS 的網域（具名 tunnel 必須要網域；約每年 10 USD 起，需確認）、
  Zero Trust 組織（免費方案目前上限 50 位使用者，需確認）、建立 Access application + policy（只允許自己的 email，OTP 或 SSO）、
  在 PC 上以 `cloudflared service install <token>` 安裝成 Windows 服務（需本機管理員權限）。
- ingress 設 `httpHostHeader: 127.0.0.1` 讓 AEP 的 Host 檢查通過。
- 仍需 token：在遠端打開 `https://aep.<網域>/?token=<本次 token>`，token 要從 PC 取得（例如透過 Telegram 傳給自己）；每次重啟改變。
- 缺點：排程頁 Origin 檢查會 403；公開路由完全靠 Access 保護，設錯即外洩；AEP 不知道請求來自遠端；`Host` 防線被刻意抵消。
- 費用：Tunnel 與 Access 免費方案即可（需確認）；網域費用另計。

**B. 小幅 AEP 改動：「安全遠端模式」（建議；約 2–4 天含測試）**
- 內容即第 3 節 1–7 項。改動集中在 `web.py` 的 guards（`_host_is_loopback`、`_authorized`、公開路由順序）、
  `schedule_web.origin_allowed`、`telemetry_api` / `bi_feed_api` 的 origin 判斷、`host.json` 設定契約、設定頁一張「遠端存取」卡片
  （顯示狀態與檢查結果，依 AGENTS 23 每個等待顯示進度）。綁定位址仍維持 127.0.0.1（cloudflared 在本機轉送），不改 2026-09-24 決策。
- Owner 需要：同 A 的 Cloudflare 設定，再把 Access team 網域與 AUD tag 填入 AEP 設定。

**C. 替代方案**
- **公司 VPN / 公司 ZTNA**：最符合公司治理；若 IT 提供，Agent Web 只需一個「允許的主機名/介面」設定（或 VPN 內以 SSH port-forward
  到 127.0.0.1:53583，零改動）。但 DECISIONS 2026-10-28 記載 141 無法經公司 VPN 到達，個人 PC 是否可達需確認。
- **Tailscale / WireGuard**：P2P 加密、不經第三方終結 TLS、免費個人方案；使用端電腦也要裝 client，同樣屬未核可的網路通道，需 IT 同意。
  搭配 `tailscale serve` 轉 127.0.0.1 同樣會遇到 Host 檢查（需 B 的允許主機名）。
- **SSH port-forward**：若外部電腦能 SSH 到這台 PC（通常不能，需入站），`ssh -L 53583:127.0.0.1:53583` 可零改動使用（Host 仍是 127.0.0.1）。
- **Shared Platform relay**：141 只在辦公室 LAN；要把 Agent Web 轉經 141 需要新的 relay 服務，工作量大且同樣有對外暴露問題，不建議。
- **只用 Telegram**：零新增暴露，但不是完整 UI。若遠端需求主要是「問問題、跑 Workflow」，可先評估補強 Telegram。

## 5. Harness / AGENTS 22

- 方案 B 修改 Agent Web 的認證、路由與權限閘，屬 AGENTS.md 第 22 條所列 harness（permission gates、routing）。
  動工前須：說明為何不能用 Skill 解決（本案是網路入口與認證，不是 Skill 能改的行為，理由明確）、提出最小範圍與回歸測試、
  取得 owner 範圍明確的同意，並記錄到 `docs/DECISIONS.md` 與任務紀錄。一般「幫我做遠端存取」的請求不等於 harness 同意。
- 這也會修改 owner 2026-09-24「只聽 loopback」決策的精神（綁定不變，但接受經 tunnel 的遠端請求），需在 DECISIONS 新增一條明確決策。
- 方案 A 不改程式，但同樣需要 owner 明確決定（以及 IT 的意見），且不應由 agent 代為安裝 `cloudflared` 或建立 tunnel。

## 6. 分階段計畫（若 owner 決定進行）

0. **決策關卡**：owner 與 IT 確認是否允許（Cloudflare / VPN / ZTNA / Tailscale 擇一），並決定允許的使用者 email 與遠端可用頁面範圍。
1. **契約**：`host.json` 新增 `remote_access`（`enabled`、`hostnames`、`access_team_domain`、`access_aud`、`allowed_emails`、`disabled_routes`），預設關。
2. **測試先行**（`tests/test_agent_web.py` 等，用假 JWT 簽章金鑰）：
   - 預設關閉時：非 loopback Host 仍 403、所有現有測試不變（回歸）；
   - 開啟時：允許主機名 + 有效 JWT → 200；無 JWT / 過期 / 錯 `aud` / 錯簽章 / email 不在名單 → 401；
   - 非允許主機名 → 403；遠端主機名下 telemetry、BI feed、`/mcp*` → 403/404，`/view/file` 無 JWT → 401；
   - 遠端 Origin 能通過排程頁 Origin 檢查，其他 Origin 仍拒絕；
   - 遠端首次進入以 JWT 換取 page token，網址中不出現 token；稽核紀錄有 email 無內容。
3. **實作** guards 與設定卡片；`ruff format --check`、`ruff`、`mypy src tests`、`pytest --basetemp=<自己的目錄>`（比照 CI）。
4. **實機驗證**（owner 設定 Cloudflare 後）：從另一台電腦經 Access 登入、聊天、上傳附件、跑 Workflow、確認長請求行為與 Zscaler 下的連線。
   GUI/實機測試依 owner 規則在下班時間進行。
5. **文件**：DECISIONS 新增決策、TASKS 加一列、使用說明（含如何撤銷：停用 Access application 或停止 `cloudflared` 服務）。

## 7. 需確認清單

- 公司 IT 對 Cloudflare Tunnel / Tailscale 等對外通道的政策；Zscaler 是否允許 `cloudflared` 連線（QUIC 或 HTTP2/443）。
- Cloudflare 免費方案現行限制：Zero Trust 使用者上限、代理回應逾時、請求本文上限、quick tunnel 限制。
- 公司是否已有 VPN/ZTNA 可到達 owner 的個人 PC。
- Access JWT 驗簽需要的第三方套件能否進入公司 `--no-index` 安裝包。
- 各聊天/Workflow 路由是同步等待還是背景執行加輪詢（決定 100 秒逾時是否影響）。
