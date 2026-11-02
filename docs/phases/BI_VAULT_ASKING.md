# Asking a knowledge vault from the general AI chat

Status: owner goal 2026-11-02 (relayed by the BI orchestrator); design by Claude Code the same day. Decision
record: `docs/DECISIONS.md` 2026-11-02 "Asking a vault from the general chat". Builds on
`docs/phases/KNOWLEDGE_REPO.md` (§7 the Agent reads the published version, §11 migration, §12 R6),
`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` (C1b) and `docs/phases/AI_PROPOSED_CHANGES.md`.

**Goal.** A knowledge vault can be imported into AEP so a general AI chat session can ask questions over it,
with cited answers. Both BI vaults and wiki knowledge repositories are covered.

## 1. What the code does today (read at `a7629341`)

| Audit point | Verified | Detail |
|---|---|---|
| BI needs Skill, capability, grant | yes | `bi_cards_tools.bi_cards_tools` offers `bi__query` only when a version of `engineering/bi-knowledge` is switched on and `bi-cards/query` is installed; the Bridge refuses without a grant (`permission_denied`). |
| BI reads published or pushed head | yes | `vault.reads`, `vault.reading_store`: this PC's local commits and uncommitted changes never reach it. |
| Wiki reaches the Agent only through `host.json` | yes | `KnowledgeHostBinding(asset, repo)`. Also needs a `KnowledgeManifest` under `assets/knowledge`: a binding without one is `knowledge_invalid`, which **stops the host from starting** once a model is configured (`host.build_runtime`). |
| Harness needs exactly one Skill and one vault | **partly** | True only of the deterministic route (`web._skill_intended_knowledge`) and `/wiki-query`. The conversation's **tool route** offers each catalog vault as its own tool (`gateway._vault_tools`, `knowledge__<name>`), so a second vault does not make the first unaskable; it moves questions to the model's choice of tool. |
| `aep_knowledge_ask`, researcher are wiki-only | yes | And `assistant_tools.knowledge_ask` / `_vault` serve **only the first** binding. |
| No whole-chain test | yes | Pieces exist: `test_bi_chat_*`, `test_knowledge_repo_agent`. |

Gaps the audit did not list, found while verifying:

- **G1. A vault's answer has no host-written citation.** `with_bi_sources` adds the source line only for a
  *subscribed* dataset (`QueryResult.source`); a vault's version is in `scope_note`, which reaches only the model.
  Whether the person sees the vault and version depends on what the model wrote.
- **G2. A wiki repository's answer does not name the repository's version.** Source lines name pages; the asset
  version in the binding is fixed ("publishing never changes the binding") and says nothing about the tag.
- **G3. A new binding takes effect at restart.** The catalog and the query capability are built at start-up, and
  the capability is not registered at all when there were no bindings at start. The page must say so.
- **G4. "`/api/chat`" does not exist**; the route is `POST /api/conversations/turn`. V1 uses it.

Never-published vaults stay as decided (`KNOWLEDGE_REPO.md` §7, decision 8): the pushed head is read, and the
answer says so. "Refuse unpublished data" in V1 therefore means: local commits, uncommitted changes, and anything
pushed after the published tag are never answered.

## 2. Tasks

| ID | Task | Depends on |
|---|---|---|
| V1a | Host-written citation for a vault answer (G1, G2): one line naming the vault and version, added only when the answer does not already name them | — |
| V1b | Whole-chain test with scripted models for a BI vault and a wiki repository: create or join or import a copy → push → publish → `POST /api/conversations/turn` → the answer cites vault and version; unpublished data is not answered | V1a |
| V2a | `GET /api/knowledge/askable`: for each vault and repository, whether the chat can ask it and each reason why not | — |
| V2b | `propose_change` kind `knowledge_binding` (bind or unbind a wiki repository; web only) | V2a |
| V2c | Knowledge page: state, reasons and a button that opens the proposal card | V2a, V2b |
| V3 | `aep_bi_query` (owner chose option B, §5), behind a host-level switch, off by default | — |
| V4 | `docs/runbooks/R6_MARKET_BI.md` and `scripts/r6_precheck.py` (read only) | — |
| V5 | Live acceptance with real models in a temp workspace, after the orchestrator's go | V1–V2 |

Order: V1a, V1b, V2a, V2b, V2c, V4, V5. Each slice: tests first, `ruff format --check .`, `ruff check .`,
`mypy src tests`, targeted tests, one commit, a row in `docs/TASKS.md`.

## 3. V1: citation and the whole chain

**V1a.**
- BI: `QueryResult` gains an additive `vault: {dataset, tag, commit, published: bool}` for a vault's answer.
  `with_bi_sources` adds `資料來源：知識庫 <dataset> 發佈版本 <tag>` (never published: `… 尚未發佈，已 push 的最新版本
  <short commit>`) when no line of the answer already names the dataset and the version, as it already does for
  subscribed datasets. The model's text is not changed.
- Wiki: the Knowledge tool route and `_knowledge_reply` add `資料來源：知識庫 <asset name> 發佈版本 <tag>` under the
  answer for a `repo` binding, read from the version the catalog answered from (`version.json`, the marker the
  live entry already keeps). A `vault_root` binding is unchanged: its asset version already identifies it.

**V1b.** `tests/test_vault_asking_e2e.py`, real `AgentWeb.conversation_turn` on a real runtime, scripted model
(`test_chat_workflow_forms_telegram._Scripted`), all data fictional. For each type: the published fact is answered
and cited; a fact in a local commit, an uncommitted change, and a push after the tag is not in the tool's answer;
a never-published vault says so; the Skill off, or no grant, gives no answer from the vault.

## 4. V2: binding from the Knowledge page, and why a vault is not askable

**The pattern is `propose_change`**, as for C3. A person's press on the proposal card is the approval (fingerprint,
30-minute expiry, a Task per proposal, `/api/cards/decide`); web only, not in `TELEGRAM_KINDS`. Two ways to the same
card: the page's button and the chat's model. Rejected: a Settings-style direct write from the button (it would skip
the before/after card and the stale check); hand-editing `host.json` (the failure this task removes).

**Kind `knowledge_binding`**, BI-free side module `host_runtime/knowledge_binding.py` (`now`, `plan`, `apply`), as
`bi_chat_save.py` is for `bi_analysis`:

- Values: `action: bind|unbind`, `repo` (a wiki repository registered on this PC), optional `purpose`, `boundaries`.
- Plan refuses a repository that is unknown, unreachable with no copy, or already bound. Fingerprint: `host.json`'s
  `knowledge` list plus the manifest file's presence.
- Card rows: repository, what the Agent will read (tag or pushed head), asset identity. Effects state the
  consequences in words: takes effect after a restart of Agent Web; **with a second vault the deterministic route
  stops and the model picks the vault's tool, `/wiki-query` asks for an exact asset, and `aep_knowledge_ask` keeps
  serving the first binding**. It is not a permission: the capability grant stays where it is.
- Apply, bind: back up `host.json` (`host.json.bak-<stamp>-before-knowledge-binding`, as `refresh_from_project`),
  write the manifest **first** (so a crash cannot leave a binding without a manifest, which would stop the host), then
  append the binding with `write_atomically`. Asset `<host namespace>/<repo id>@1.0.0`, `domain` the namespace,
  `lifecycle: published`, `business_approval` approved by the person who pressed Apply, evidence
  `bound-by-<actor>-<day>`, the way `refresh_from_project` stamps it. Digests are placeholders the live entry
  recomputes at first read (as in `test_knowledge_repo_agent`). `purpose` defaults to the repository's own.
- Apply, unbind: removes the binding; the manifest stays, inert. Bound repositories append, so the first binding, and
  so `aep_knowledge_ask`, does not move. The apply never restarts Agent Web (AGENTS rule 19).

**`GET /api/knowledge/askable`** → `{"repos": [...], "vaults": [...], "notes": [...]}`; each entry `{id, title,
askable, reads: {tag, commit}, reasons: [{code, message, fix}]}`. Computed, read only (no sync of a shared folder
beyond what status already does):

| Code | For | Blocks | Meaning |
|---|---|---|---|
| `not_bound` | wiki | yes | No binding: use the button |
| `restart_pending` | wiki | yes | Bound in `host.json`, not in the running catalog |
| `no_model` | wiki | yes | The query capability needs a configured model |
| `capability_missing` | both | yes | `knowledge-query/ask` or `bi-cards/query` not installed |
| `skill_off` | both | yes | No eligible Knowledge Skill, or `engineering/bi-knowledge` off |
| `not_granted` | both | yes | The actor has no grant for the capability (Capabilities) |
| `profile_excludes` | wiki | yes | The active Agent profile does not list this Knowledge |
| `nothing_pushed` | both | yes | No pushed commit with content: commit and push first |
| `unreachable` | both | yes | Shared folder unreachable and no copy built on this PC |
| `unreadable_format` | BI | yes | Folder without `repo.json` (a V4 vault); rebuild, R6 |
| `never_published` | both | no | The pushed head is answered; publish a tag to pin it |
| `several_vaults` | wiki | no | The note of §1 about the direct route and `aep_knowledge_ask` |

**Skill namespace (found in V1b).** The conversation offers a Skill's tools only when the Skill's namespace is the host's (`SkillRegistry.discover`), so `skill_off` looks there, not at every installed Skill.

**Page.** Inside the 知識庫 card (`kp-repos`) and the BI 「知識庫」 section only. Each entry shows 「可以在對話裡問」 or
its reasons with their fixes; a wiki repository not bound has 「讓 Agent 可以問這個知識庫」, which opens the proposal
through `renderActionCard`. Page changes stay in these sections (other workers edit the chat and the build flow).

## 5. V3: should `aep_knowledge_ask` cover BI vaults?

**Decided (owner, 2026-11-02): option B, a separate MCP tool `aep_bi_query`.** Defaults set by the orchestrator:

- **Published version only**: a vault's published version, or its pushed head, labelled, when never published. A local
  dataset or a subscribed one is refused (`not_a_vault`); this tool reads vaults only.
- **Saved analyses and built-in queries only** (a slug, `all`, `quality`, or a card search). **No ad-hoc SQL over MCP**
  in this version: an argument named `sql` is refused (`sql_not_allowed`), and only `BI_QUERY_FIELDS` are passed on.
- **The assistant-MCP token and the grant**: the call goes through `LocalAgent.execute_capability` to `bi-cards/query`,
  so `permission_denied` without the grant; `bi_unavailable` while the BI Skill is off.
- **The same host-written source line** in `source`, plus `reads: {tag, commit}`.

**A host-level switch, off by default** (orchestrator's choice, since the pattern had no per-tool switch): the token
opened every tool, and Settings > Coding agents registers or removes the whole `aep-assistant` server.
`host.json` `assistant_bi_query: bool = false`, set by a checkbox in Settings > Coding agents through `POST
/api/coding-agents/bi-query` (the session token only: the token external agents hold is refused; not a
`propose_change` kind, so the chat cannot turn it on). It takes effect at once, with no restart. While off,
`/mcp` does not list the tool and a call answers `bi_query_off`.

The checkbox's words: 「讓外部 coding agent 讀取 BI 知識卡片（aep_bi_query）」, 「開啟後，這台電腦上連到 AEP 的 Claude
Code、Codex 和 GitHub Copilot 可以讀取 BI 知識庫已發佈版本的卡片與已存的分析，內容會送到這些 agent 使用的模型服務。沒有發佈過的知識庫讀的是已 push 的最新版本，結果會標明。它們不能寫入，也不能自己下 SQL。預設關閉；關閉後立刻停止。」

**Known limit (accepted by the orchestrator).** The stdio bridge (`assistant_bridge`) answers `tools/list` from the
`TOOLS` constant without reaching Agent Web, so a stdio client lists the tool while it is off; its description says it
may be off, and the call is refused. Making the list accurate means forwarding `tools/list`; not done in this version.

The options as they stood before the owner's choice:

The architecture does not answer this. `ARCHITECTURE.md` says only that MCP exposes capabilities and that Knowledge
queries go through the Bridge. `COPILOT_INTEGRATION.md` §2 defines the tool as "the AEP Knowledge Harness's answer",
and DECISIONS 2026-10-12 and the later extension approve sending "company content" through "Knowledge search/read/ask"
to external agents, written before BI vaults existed. They neither include nor exclude BI cards (market and competitor
data with named customers), and BI has no harness validating an answer the way that tool promises (`validated`).

| Option | What | For | Against |
|---|---|---|---|
| A | Leave as is: the assistant tools stay wiki-only | No new data boundary; `validated` keeps its meaning | External agents cannot ask BI |
| B | A separate read-only tool `aep_bi_query` over the same capability | Clear name; grant and audit as `bi__query`; external agents can chart nothing, read rows | Widens the 2026-10-12 data decision to BI; the answer is not validated |
| C | `aep_knowledge_ask` routes BI questions too | One tool | Breaks `validated` unless BI gets a harness check; routing guess inside a tool |

Independent of the choice: `aep_knowledge_ask` serving only the first binding is existing behaviour,
now stated on the proposal card.

## 6. V4: the R6 runbook

`docs/runbooks/R6_MARKET_BI.md`: raw sources from the committed record (`docs/TASKS.md` 2026-10-29,
`KNOWLEDGE_REPO.md` §11), order through the build flow, checkpoints, the `rs-k` copy import, rollback (the old folder
is renamed, never deleted). `scripts/r6_precheck.py` only checks existence and format and opens nothing for writing;
its tests use fictional folders. This worker never runs it on the real OneDrive folder. **No V4 migration tool.**
Worker `bi-build-flow` is changing the build flow in parallel, so the runbook names steps by purpose and says to read
the current page labels at the session.

## 7. V5: live acceptance

Only under `%TEMP%`, with its own Agent Web on a free loopback port (never 53583), using the existing model
configuration mechanism; secrets are referenced by environment-variable name, never printed, copied or committed. No
key reachable: stop and say what is needed. Never the owner's workspace, the real Agent Web, or OneDrive/SharePoint.
The orchestrator's go comes first.

**Result (2026-11-02, go from the orchestrator).** Real `gpt-5.5` at `http://127.0.0.1:4000/v1`, alias `company`, key by
the variable name `LITELLM_MASTER_KEY` through `deploy/windows-preview/gateway-default.json`. The deployed Knowledge
Skill 1.12.0's procedure, with its namespace set to the host's. Script `.scratch/v5_live.py` (not committed); transcript
in `%TEMP%\aep-d-v5-ad3x60xl\transcript.json`. A repository was bound through the card, then Agent Web restarted on the
saved file.

| Turn | Model calls | Answer (fictional data) | Check |
|---|---|---|---|
| Wiki, published | 4 | 「Tester X 支援 K42X 選件，出貨時程為 2027 年第一季。[1]」, 來源 `[1] Wiki：tester-x（缺來源連結）`, `資料來源：知識庫 tester-wiki-b6aa00 發佈版本 v1` | Fact and version cited |
| BI, published | 2 | 「TSN 的 standard_body 是 FICTION-802。」 through `bi__query`, `資料來源：知識庫 vault-market-signals-4a4eb0 發佈版本 v1` | Fact and version cited |
| Wiki, after a local commit, an uncommitted edit and a push after v1 | 4 | Only K42X, `發佈版本 v1` | K77X, K88X, K99X absent |
| BI, after an uncommitted edit and a push after v1 | 2 | Only FICTION-802, `發佈版本 v1` | ZZPUSHED, ZZDRAFT absent |

The script looked for the unpublished facts in every model request and reply as well as the answers: none. `aep_bi_query`
through `/mcp`, no model: `bi_query_off`, then on with `發佈版本 v1` and no unpublished fact, `sql_not_allowed`,
`bi_query_off` again. `askable` said `not_bound`, then `restart_pending`, then 可以問, each as a turn then behaved.

Seen in the run: `缺來源連結` is the wiki answer's own honest note, since the fictional page links no source for the
edited line. In one BI answer the model also named the version itself, in other words, so the host's line followed it:
harmless repetition. A first run stopped after its first turn on a bug in the script (4 calls, wiki turn correct).

## 8. Risks

- A bad binding can stop the host at start: hence manifest first, atomic write, backup, and a test that a host builds
  after apply.
- Rebuilding a large repository at the first question after a restart is slow; existing behaviour of the live entry.
- `askable` must not contradict what a turn does: its tests ask a real turn in the same state.
