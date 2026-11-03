# Telegram conversations in Agent Web

Status: design and tasks, 2026-11-02. Owner decisions relayed by the BI orchestrator; decision entry
`docs/DECISIONS.md` 2026-11-02, which amends the earlier "memory only" position (entry of 2026-10-25, "A session
remembers what it produced"). Contract: `docs/CONTRACTS.md` "Conversation source and search". Progress: `docs/TASKS.md`.

Generic: no BI logic and no BI types (ADR-K10).

## 1. Goal

The owner's own Telegram conversations are stored durably and can be read and searched in Agent Web. `/new` only
starts a new conversation. Deleting happens in Agent Web. A Telegram conversation is read-only there. No backfill.

**The model is not affected.** It keeps receiving the in-memory history, capped at `MAX_CHAT_HISTORY` (12), and
nothing is reloaded into it after a restart.

## 2. Whose messages: audited, no open question

The owner is the sender whose mapped actor equals `HostRuntime.actor` (`config.device.registered_by`), the person
Agent Web reads and writes conversations for.

- A company workstation refuses a request from any other actor (`delegation_not_allowed`), so a working owner's chat
  there always has this actor.
- On a shared test workstation the employees' senders map to their own actors, so none of them is stored.
- `_decide_card`'s 「Only the owner」 test is not used: with no active binding `_acting` calls every sender the owner.

The sender map's own rule (one actor to one sender) keeps this to one Telegram user. Other allowed senders are never
stored, in any chat. A group chat stores the owner's turns only, because history is keyed by chat **and** sender.
When the owner replies to somebody's message, the model still reads the quote, but the stored text leaves it out, so
another sender's words cannot enter a record that way.

## 3. What is stored

Exactly what the history keeps, written by one helper (`TelegramIngress._keep_history`), at all six places that write
`_histories` today, as a user and assistant pair (the page reads pairs):

| Where | Said | Answer | Status |
|---|---|---|---|
| `_decide` | 【核准】 or 【拒絕】 and the summary | approval text | answered |
| `_decide_card` | `[action] title` | the card as drawn | answered |
| `_converse`, refused | the person's words | `_unfinished` note | failed |
| `_converse`, not answered | the person's words | stop reply, or the `_unfinished` note | failed |
| `_converse`, answered | the person's words | the answer | answered |
| `_remember_turn` | `/run` or 【執行】 line | flow note or run entry | answered |

- The stored answer is the text. The `[工具紀錄]` part goes in `tool_summary`, as for an Agent Web answer. Ledger
  entries (`finished.entries`) stay in the text.
- Attachments: the stored question has the caption, and the file's `filename`, `kind` and `path` in `attachments`, the
  shape Agent Web stores. Never the content. The folder is a hash (`AttachmentStore._folder`), so a path shows no chat id.

**Not stored, by design:**

- Failure text kept out of history (`docs/DECISIONS.md` 2026-10-08 and `_unfinished`): a stored failed turn holds the
  same short note as the history, never the explanation sent to the person, an exception or a URL.
- Secrets. A message carrying a credential is refused by `_request` before any history write. Stored text passes the
  same redaction as every conversation message (`ConversationMessage.redact_credentials`), and a message that still
  fails the backstop check is not stored and is logged.
- Workflow question flow answers: the flow's values never enter the history, only the question note and run entry.
- One-time codes: no Telegram flow handles one. Personal Agent code sign-in is not a Telegram flow (checked in
  `channels/telegram.py` and `telegram_flow.py`). **Limit:** a code the owner simply types into a chat is ordinary
  text unless it looks like a credential, and it is stored; it can be deleted with the conversation.
- Replies that never reach the history: `/help`, `/status`, `/model`, `/why`, 「存成筆記」, refusals of an attachment.
- Other allowed senders (§2).

## 4. The record

`ConversationRecord` gets `source: Literal["agent_web", "telegram"] = "agent_web"`, so existing records read unchanged
and no schema migration is needed.

**Session id:** `tg-<id>-<yyyymmdd>-<8 hex>`. `<id>` is 16 hex of SHA-256 over a per-host random key and
`chat:sender`. It is stable across restarts, unlike `chat_hash`, whose salt is per process. The key is kept once in
`local_meta` of `state.sqlite`. A plain hash would not do: chat ids are few enough to try them all. A record validator
ties `source == "telegram"` to the `tg-` prefix in both directions. The raw chat id appears in no stored name and on
no page.

**The title** is the first message clipped to 72 characters, as for Agent Web.

## 5. The 100-message cap: roll over

`ConversationRecord` holds at most 100 messages, and a long-lived chat would silently lose old ones if it rolled the
way Agent Web does. So a Telegram record never drops anything: the next pair starts a **new record** when

1. the host's local day changed since the latest record began (one record per day is what you look for later); or
2. the record cannot take two more messages; or
3. `/new` was sent; or
4. no earlier record exists, or the one being written was deleted meanwhile.

The latest record is looked up in `state.sqlite` for each pair, so nothing but the `/new` mark is held in memory.

**Known limits, accepted:**

- A restart between `/new` and the next message loses the mark, so that message joins the previous record of the
  day. Nothing is lost, and the model's history starts empty either way.
- After a restart the record for the day continues although the model started fresh.
- Deleting the latest record of a day makes the next message continue the day's earlier record, if there is one.

## 6. `/new` and delete

**`/new`** for the owner, with history storage on: clears the in-memory history and the session ledger as today, marks
the next pair as a new record, and **no longer deletes the attached files**, because the stored records list them and
open them. For every other sender, and on a host without the store, `/new` works as it does today, files deleted.

**Deleting in Agent Web** uses the same route and the same button as any conversation, and **it does reach
attachments**, as Agent Web's delete does: the files the record lists are removed. They live in the chat's folder, not
the record's, so they are removed one by one (`AttachmentStore.delete_files`, only paths inside its own root). Other
records' files stay. If the same chat's in-memory history still names a deleted file, a tool reading it finds it
missing, as after a `/new` today. Delete does not clear the chat's in-memory history: the model's behaviour does not
depend on what is stored.

Files then live as long as the conversations that list them, the same rule as Agent Web, and `/new` no longer limits
them. Settled by owner decision 2 ("`/new` only starts a new conversation"); it amends `docs/DECISIONS.md` 2026-10-08
for the owner's chat only.

## 7. Read-only

One check, `conversation_read_only` for `source == "telegram"`, on every route that would change the record or act on
it: `/api/conversations/turn`, attachment upload, feedback, backend, model, contribution draft, voice transcribe,
agent session update, and the form-run record. Refusing feedback also keeps these records off the Shared Platform's
feedback upload. Reading, opening a listed file and delete stay available.

## 8. Memory and telemetry: which

`LocalState.conversations(actor, limit, source="agent_web")` returns Agent Web conversations **by default**, so every
existing reader is unchanged and takes no Telegram record:

| Reader | What it does with Agent Web chats | Telegram records |
|---|---|---|
| `experience_harvest` (`from_conversations`) | builds experience cases | not read |
| Skill suggestions and `_suggestions_due` | builds suggestions | not read |
| `memory_health._last_used` | last use of a preference | not read |
| `memory_page._conversations` | overview | not read |
| `feedback_sync` | uploads rated answers | none: rating is refused |

So in this version stored Telegram records feed no memory, telemetry, learning or platform path, although Agent Web
chats do feed the first four. This is the stricter side of the instruction, chosen so a stored chat changes nothing
else. It also stops daily records pushing chats out of those readers' "latest 100". What the live Telegram turn
already records (telemetry of the run, the ledger, task summaries) is unchanged.

## 9. The page

- **List:** `/api/conversations` returns the latest 50 of each source, merged by time, each row with `source`. A mark
  「Telegram」 in the row's detail line. Agent Web's own list shows what it showed.
- **Opening the page:** the default selection is the newest Agent Web conversation, never a Telegram one; with none,
  one is created as today.
- **Read-only view:** the composer is hidden, with the note 「這是 Telegram 對話，只能閱讀；要繼續請回到 Telegram。」.
  No rating or reply controls on a turn. Delete stays.
- **Search:** `GET /api/conversations/search?q=` in the existing session search box. The box still filters titles at
  once, and the server's hits for message text join the list with a snippet. `LIKE` over title and message text, for
  this actor, both sources, newest first, at most 30 conversations; `%`, `_` and `\` are matched literally. No FTS:
  it would need a migration and a tokenizer that handles Chinese, and `LIKE` matches any Chinese substring. It is
  case-insensitive for ASCII only. A query over 200 characters is refused. Searching scans the actor's records, which
  is acceptable at this size. Agent Web records are searched too, including what was outside the page's 50.

## 10. Wiring and failure

- `TelegramHistory` (new, `host_runtime/telegram_history.py`) holds the state, the actor and the roll-over. Created in
  `build_runtime`, kept on `HostRuntime.telegram_history` and passed through `build_telegram`, the one construction
  path, so it survives the ingress being rebuilt when the settings change.
- A storage failure never fails a Telegram turn. The reply and the in-memory history go on, and a warning names the
  error type, never text or chat id. So a record can have gaps; the log says so.
- The write is synchronous on the poll loop: one short local transaction per pair, like the offset write.

## 11. Tasks

Each slice is committed after format, lint, type check and targeted tests.

- [x] **T1 Record and state.** `source`, the validator, `conversations(source=)`, `latest_conversation`,
  `search_conversations`, the per-host key. Tests first.
- [x] **T2 Storage.** `TelegramHistory`, `_keep_history` at the six sites, `/new`, wiring. Tests with the existing
  stubs: pairs, roll-over, owner only, quote, failure text, credentials, restart, model input unchanged.
- [x] **T3 Read-only and delete.** The check on every route, delete reaching attachments, `/api/conversations` rows.
- [x] **T4 Search route.**
- [x] **T5 Page.** Mark, default selection, read-only view, search.
- [x] **T6 Docs.** CONTRACTS, TASKS, HANDOFF; the full suite only on the orchestrator's go.

## 12. Tests

Only the existing Telegram stubs (`FakeTransport`, stub models). No real Telegram message, no bot token, no real
model. The real Agent Web on 53583 and the owner's workspace are not touched.
