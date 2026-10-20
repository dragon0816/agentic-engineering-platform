# Business cards and org chart (native capability)

Owner decision 2026-10-20 ("當然選a"): business cards become a native AEP capability, usable in
Gateway chat in Agent Web and in Telegram, switched on by default in the colleague bundle, with
no data leaving for an external model. Decision record: `docs/DECISIONS.md` 2026-10-20 "Business
cards are a native AEP capability".

## 1. Why

A live test (2026-10-20) showed AEP's Gateway chat reads a business-card photo well through the
internal gateway (a 90°-rotated card read correctly; the one wrong field, the email, was flagged
uncertain), but nothing could store it. The only implementation was the Hermes coding-agent Skill
`hermes/business-cards` (`SKILL.md` + `scripts/cards.py`), which needs agent mode and a shell.
`cards.py` also lacks what an org chart needs:

| Gap in `cards.py` | Native version |
|---|---|
| No source column | every observation records `card`, `email_signature`, `user` or `import` |
| No status / departure, no update or delete | `status` (`active` / `left`), `left_at`, `status_set_by`, `status_reason`; edits; undo |
| Duplicates only by exact name + company | the same card image; then email (case-insensitive); then name + company (a romanised name matches the local-language name), also with another email unless the department or division differs |
| No fax, no business group | `fax`, `ext`; `business_group` (事業群), `division` (處), `department` kept apart |
| No reporting lines | `reporting_lines` with evidence kind, reference, confidence and inferred flag |

## 2. Storage

A Host-local SQLite file per actor: `<workspace>/business-cards/<actor-key>/cards.db`. Never shared
across members; contacts are personal data. `<actor-key>` is the actor's name made file-safe plus a
short hash, so two actors never share a file.

- **people**: `person_id`, `name`, `romanised_name`, `company`, `company_tax_id` (統一編號),
  `business_group`, `division`, `department`, `title`, `honorific` (博士, Dr., PhD), `phone`, `ext`,
  `mobile`, `fax`, `email`, `address`, `website`, `notes`, `status` (`active` / `left`), `left_at`,
  `status_set_by`, `status_reason`, created / updated. A store opened by a newer version gains any
  missing field column (`ALTER TABLE ... ADD COLUMN`).
- **field_sources**: field-level provenance, one row per person and field: the source that set the
  current value (`card` / `email_signature` / `user` / `import`), its evidence date and observation.
- **observations**: every scan or sighting is kept ("every scan is kept"): source, source date,
  source ref (`sha256:<hex>` of the card image, the mail's message id, or `hermes-cards:<row>`),
  the raw extracted fields and `uncertain`. Never an email body, never an image.
- **reporting_lines**: person → manager, `evidence_kind` (`signature` / `email_content` /
  `title_inference` / `user`), `evidence_ref`, `confidence` (0–1), `inferred`; removal is a soft
  delete (`removed_at`, `removed_by`, `removed_reason`), so it can be restored.
- **history**: every change, grouped by `change_id`: who, when, why, kind, field, old and new
  value. Undo replays a change group backwards and is itself a new change.
- **proposals**: a conflict between an automatic source and a user-set or confirmed value, or
  another email for a person matched by image or name: stored value, read value, source,
  observation id, `state` (`open`, then `rejected` when the person keeps the stored value,
  `accepted` when they take the read one, `dismissed` when its scan is undone).
- **candidates**: a signature harvest's candidates for one conversation (`<channel>:<session
  id>`), with short ids (`s1`, ...), fields, uncertain, message id and date (never a body); kept
  one hour or until the conversation's next harvest (§5).

### Which person a reading is (2026-10-20 re-test; decision "How a re-scanned card finds its person")

1. the same card image (`sha256:` ref) as an earlier observation → the person it was stored as
   (`matched_by: image`);
2. the same email (case-insensitive);
3. the same name (local or romanised) at the same company. Another email does not make it
   someone else unless the place differs too: both have a department and they differ, or both a
   division and they differ.

When 1 or 3 brings another email, the stored email stays, the new one is a proposal, the email
needs confirmation (also when the person set or confirmed it: third live test 2026-10-20) and
the result carries `email_differs` {`stored`, `read`} with a sentence in `summary`.

Every `add-card` result carries `match` (third live test 2026-10-20: the reply began
「統一編號、電話、傳真也更新了。」 and never said the card matched a known contact): `by`
(`image` / `email` / `name_company` / `romanised_name` / `new`) and `by_label` (名片圖片, Email,
姓名與公司, 英文名與公司, 新聯絡人), `person_id`, `name`, `company`, the labels of what
`changed`, was `kept` and `needs_confirmation`, and `lead`: 「已對到既有聯絡人 王小明（範例科技），
依名片圖片比對。」 or 「已新增聯絡人 王小明（範例科技）。」. The reply opens with `lead`, then the
changes (`summary`; a summary of updated fields only says 「更新了統一編號、電話、傳真。」, never a
dangling 也), then the questions. Limit: namesakes at one company
with different emails and the same or an unread department and division are taken to be one
person; the flagged email lets the person correct it.

### Field-level provenance (in the spirit of ADR-K11)

When a card, signature or import brings a value for a field:

1. empty field → set; provenance = that source and date;
2. current value set (or confirmed) by the **user** → never overwritten; a differing value,
   sure or unsure, becomes an open proposal, the field needs confirmation and the result says so
   ("kept your value", with both values);
3. current value from an automatic source → replaced only when the new evidence is not older
   than the current value's evidence date; the change is in history;
4. a value the reading marked **uncertain** fills an empty field but never replaces a value;
5. a reading that is a strict prefix or substring of the stored value (spaces and case ignored)
   never replaces it (`less_complete`: "Connectivity & Solutions" does not replace
   "Connectivity & Solutions 事業群", 研展處 does not replace 研展處 I); not for `title`
   (副總經理 → 總經理 is a promotion), `notes` or `email`; such a reading is not proposed
   either, even against the person's own value;
6. phone, fax and mobile are compared by digits and extension (`names.phone_key`: spaces,
   hyphens, dots and parentheses ignored, +886 read as a leading 0): "(03) 666 7799" is
   "(03) 666-7799", so the stored value stays, nothing is recorded and nothing is reported
   (third live test 2026-10-20: each re-scan flipped the format and said 電話、傳真也更新了).

`edit_person` sets values with source `user`.

**Needs confirmation.** A field needs confirmation while any observation of the person listed it in
`uncertain` and its current value is not the person's own (source `user`), and while it has an
open proposal, whatever its source (decision 2026-10-20 "A reading that differs from the
person's own value needs confirmation"). A later scan that is sure does not clear it. The person
clears it by confirming the stored value (`edit-person` `confirm: ["email"]`: the field's open
proposals are rejected and a `confirm` history row is written, undoable, which opens them
again), by taking the value read (`accept: ["email"]`, 「用新的」, or that value in `fields`: the
proposal is accepted, a `field` history row) or by correcting it (`fields`); re-stating the
stored value in `fields` also confirms it. `accept` without an open proposal is refused
`proposal_unknown`. `edit-person` reports `confirmed`, `already_confirmed`, `accepted`,
`rejected` and the person's remaining `proposals`; `add-card` results carry the person's open
`proposals` [{`proposal_id`, `field`, `label`, `current` (stored now), `proposed`, `source`,
`source_label`, `observation_id`, `person_id`, `name`, `company`}]. A wrong value is emptied with `edit-person`
`clear: ["romanised_name"]`: the empty value is the person's own, so a later scan does not refill
it (it becomes a proposal). `add-card`, `edit-person` and every person view
report `needs_confirmation`, and the org chart marks those people with
「需確認：英文名、Email」 (field names in Chinese, `contracts.FIELD_LABELS`).

**Who.** Every write records who made it as the Host knows it: the request's actor and channel
(`alice via telegram`, `alice via local`), in history, `status_set_by`, reporting lines and undo.
Never a model argument: `set-status` has no `said_by`, and the `cards__*` tools drop identity
keys (`said_by`, `set_by`, `actor`, ...) from a model's arguments.

**Host checks on a reading** (`capabilities/business_cards/reading.py`):

- `romanised_name` is kept only when printed: `add-card` takes `romanised_name_printed` (where it
  is printed, copied as printed); without it, or when it is only an email address, the Host drops
  the romanised name (`dropped` [{`field`, `value`, `reason: not_on_card`}]) and marks the email
  uncertain when its local part repeats the dropped name. A signature candidate keeps a romanised
  name only when its block prints it.
- A degree or honorific in `title` (博士, Dr., PhD; not 博士後) moves to `honorific`.
- A unified business number in `notes` or `address` (統一編號 / 統編 / UBN / Tax ID + 8 digits)
  moves to `company_tax_id`; `add-card` also takes `other_text` (printed text the reading did
  not place in a field), which the Host scans for the number and does not store (re-test
  2026-10-20: card A's printed number was missed). When `company_tax_id` holds a number that
  the stored notes still mention (a note from before the field existed), the mention is taken
  out of the notes with a history row. Decision `docs/DECISIONS.md` 2026-10-20 "Degrees and the
  unified business number are contact fields".
- Division and department text is never normalised: 研展處 I and 研展處 II are two boxes.

## 3. Operations (Bridge capabilities, namespace `business-cards`, version 1.0.0)

| Capability | Side effect | What it does |
|---|---|---|
| `add-card` | write | Fields + `uncertain` read from a card photo; returns created / updated / unchanged, what changed, what was kept, and a "上次是…, 現在是…" line |
| `add-from-signature` | write | 1–50 entries with message id and date; source `email_signature` |
| `store-candidates` | write | This conversation's harvested candidates by id (`s1`, ...) or `all`; the Host supplies message id and date |
| `edit-person` | write | The person's own corrections, source `user` |
| `set-status` | write | `left` / `active`, with reason, who said it and the date |
| `set-reporting-line` | write | Person → manager with evidence; replaces the person's current line |
| `remove-reporting-line` | write | Soft-removes the current line, with a reason |
| `undo` | write | Reverts one change group by its `change_id` |
| `import-hermes` | write | One-time, idempotent import of `~/.business-cards/cards.db` (`BUSINESS_CARDS_HOME`) |
| `find` | read | People matching a text (name, romanised name, email, company, title); a company query returns all its people |
| `list` | read | People by company (resolved as below), source and status |
| `history` | read | One person's changes and observations, with change ids, labels and local times |
| `proposals` | read | Open proposals, one person's or everyone's, with a sentence (`note`) for the reply |
| `org-chart` | read | PNG and/or interactive HTML (`format`) + Markdown legend for a company (writes only the derived files) |
| `harvest-signatures` | read | Mail in the configured scope from one company domain → signature candidates |

**Company queries** (re-test 2026-10-20: "WNC" worked once and failed once). `org-chart`, `list`
and `find` resolve a company against the stored companies: the exact or legal-suffix-stripped
name; then an alias (a 2–6 letter word in capitals in the name such as `WNC`, or the company part
of an email or website domain, `wnc.com.tw` → `wnc`, never a public mail service); then a part of
exactly one company's name (啟碁 → 啟碁科技). Spellings sharing a name or an alias are one
company; the result names the canonical spelling (most people, then longest). Ambiguous or
unknown queries fall back to the plain name comparison. Decision "How a company query finds the
company".

Every capability is a typed contract (`capabilities/business_cards/contracts.py`); the dispatcher
validates inputs and outputs as for any capability. Nothing here sends mail or reaches the network
except the internal gateway model call in `harvest-signatures`.

### Writes without a confirmation every time

The write capabilities are `side_effect: write`, `risk: low`, with policy ref
`personal-contacts-policy`. In owner mode a write the conversation model chooses normally waits for
the person's approval button. For these capabilities only, the Host declares a **standing
confirmation** (`LocalPolicy.confirmed_writes`): host configuration, never asset content, limited to
the person's own contact store, which is local, never networked, recorded in history and undoable.
Grants still apply (`authorize`), so on a host governed by members' decisions the capability needs a
selection like any other. Switching the Skill off removes the tools.

## 4. Conversation tools and the Skill

The Skill `engineering/business-cards@1.0.0` (alias `cards`) is shipped switched on
(`host_runtime.assets.shipped()`). It carries the procedure; it has no commands, because a Skill
command to a capability gives the model no argument schema. The Host offers host tools
`cards__add_card`, `cards__store_candidates`, `cards__add_from_signature`, `cards__edit_person`,
`cards__find`, `cards__list`,
`cards__history`, `cards__proposals`, `cards__set_status`, `cards__set_reporting_line`,
`cards__remove_reporting_line`,
`cards__undo`, `cards__org_chart`, `cards__harvest_signatures`, `cards__import_hermes`, each with its
JSON schema, **only while some version of that Skill is switched on** and its capabilities are
installed. Every call is a `CapabilityInvocation` through the Bridge with `origin: model`.

Procedure (from the Hermes `SKILL.md`, adapted):

- reading rules and the JSON fields; local-language `name` / `company`, the romanised form in
  `romanised_name`; `phone` is the desk number, `mobile` the cellphone, `ext` the extension;
  `uncertain` names every field not read with confidence; omit rather than invent;
- after a scan, confirm the key fields in one block and ask only about the uncertain ones;
- lead with the change when the person was already on file;
- the org chart is not a reporting chart unless lines have evidence; say what it is every time;
- a departure only when the user says so, recorded with the date and the user as source, undoable;
- `romanised_name` only when printed on the card (with `romanised_name_printed`); never derived
  from the email, never the email changed to match a name;
- `title` is the job title only (degrees to `honorific`); division and department copied exactly,
  including suffixes such as I, II, 一處; 統一編號 in `company_tax_id`, never in notes;
- ask about `needs_confirmation` too; "email 正確" → `cards__edit_person` `confirm: ["email"]`;
  a result's `proposals`: say the stored and the read value and ask which is right; the other
  value or 「用新的」 → `accept: ["email"]`; `cards__proposals` lists the open ones (tell its
  `note`);
- start every card reply with `match.lead`, then the changes, then the questions;
- name statuses, sources and times with the results' labels (`status_label`, `source_label`,
  `kind_label`, `field_label`, `old_display` / `new_display`, `at_local`: Asia/Taipei, e.g.
  2026-10-20 14:03), never `active`, `left`, `email_signature` or UTC times; change ids stay in
  the results, shown only when the person asks to undo a specific change, otherwise
  「可以說『復原』撤回」 (`undo_hint` on `set-status`; `undo` returns a `note` without ids);
- when a tool fails, tell its failure message and code; mention Settings only when the message
  names it;
- name fields in Chinese with the result's `field_labels` (every succeeded `cards__*` result
  carries them; changed, kept and dropped items carry `label`), never raw names such as
  `romanised_name`; report only what changed; a question about a field states its stored value
  (`to_confirm` [{`field`, `label`, `stored`}]);
- `email_differs`: say the email read this time differs from the stored one, which was kept;
- look for the 統一編號 on every card and put unplaced printed text in `other_text`;
- a company is passed as the person says it (WNC, 啟碁); the result's `company` is its stored
  name;
- after a harvest list each candidate with its id and tell `scan_note`; on 「都存進去」 or
  「存 s1、s3」 call `cards__store_candidates`; never harvest again just to store.

## 5. Email signatures

`harvest-signatures(domain, days, limit, folder)` searches the Outlook scope set in Agent Web
Settings → Agent mode (folders, `max_days`, exclusions), never wider: `days` is capped at
`max_days`. Only messages whose sender address ends with `@<domain>` are read. For each, the last
lines before any quoted reply are cut as the signature block (≤ 1,200 characters), credential-shaped
text is redacted, and at most 10 blocks go to the internal gateway model per structured call
(`business-cards.signature.v1`), at most 40 messages per harvest. The result is candidates
(a short `candidate_id`, fields, message id, date, whether the person exists and what would
change). Nothing is stored in the contacts until the person confirms; the candidates are kept for
this conversation (`candidates` table, one hour, replaced by its next harvest; `expires_at`), and
`store-candidates` stores them by id or `all` with source `email_signature`, the message id and
the date, so the model never copies message ids (re-test 2026-10-20: on 「都存進去」 the model
re-ran the harvest because the ids were not in its context). An expired set is refused
`candidates_expired`. Only fields, the message id and the date are ever stored.

**COM on worker threads** (re-test 2026-10-20). Mail is read on `asyncio.to_thread` workers. COM
must be initialised on each thread that uses it; only the thread that first imported pywin32
was, so after a restart the first harvest worked and later mail calls failed with
CO_E_NOTINITIALIZED (unmapped, so `handler_error`). `integrations.com.apartment()` now wraps
every Outlook call (mailbox, draft, send: Outlook is asked for inside it on every call and no
COM object is kept) and each Excel run of the weekly and chipset reports; COM failures map to the
adapters' codes. The guarded live test lists the Inbox from two different worker threads.

**What was scanned** (third live test 2026-10-20: 5 scanned, 1 signature, `skipped` empty, and
nothing said about the other 4). The result counts `without_signature` (read, no signature
block), `same_sender` (older mail of a sender already read; not opened), `unreadable_signature`
(a block the model found no person in), apart from `skipped`, and `scan_note` says it:
「掃描 5 封，1 封有簽名檔，4 封沒有簽名檔。」 (the other counts are added when not zero).

A message that cannot be read is skipped and counted by its code (`skipped` [{`code`, `count`}]),
never the whole harvest; `skipped_note` says it for the person, e.g. 「讀信失敗：1 封信無法讀取
（message_unknown），已略過；其餘 3 封已處理。」.

**Folder names.** `OutlookComMailbox.get()` names a message's folder the way `list()` does:
relative to the default store's root, default folders by their canonical names (`Inbox` also
when Outlook calls it 收件匣), another store's folders with that store's name in front (so they
never match the scope). Before the fix `get()` returned `<mailbox>/Inbox` (the walk did not stop
at the store root, because the MAPI Namespace also has `Folders`), so `outlook_mail.read()`
refused every Inbox message with `message_unknown`: signature harvesting, `outlook.read` and agent
mode's mail read (live test 2026-10-20).

**Failures in the conversation.** A failed `cards__*` call reaches the model with a short Chinese
sentence naming the code instead of the Bridge's generic "Capability invocation did not complete"
(`business_cards_tools.FAILURE_TEXT`), with a specific Bridge message (where the input was wrong)
kept after it.

## 6. Org chart

`org-chart(company, include_left)` lays out business group → division → department as nested
boxes, people inside by title seniority, and draws reporting lines: solid for evidenced lines
(signature, email content, user), dashed for inferred ones (title inference or `inferred`). People
who left are omitted, or drawn grey with "已離職" when `include_left` is true. A person's box
reads: the name with the honorific (「王則閔 博士」), the title, the desk phone with its
extension, the mobile when there is one (「手機 …」), and 「需確認：…」 in the warning colour
(re-test 2026-10-20: the box showed only the mobile and no 博士). Rendered with Pillow
(shipped in the bundle with the `weekly-mail` extra and in CI with `office`), no Graphviz; a CJK
font is taken from Windows Fonts (Microsoft JhengHei, then others) when present. The Markdown
legend lists each line with its evidence and whether it is inferred, says plainly that without
evidenced lines the layout is a grouping by title, not a reporting chart, and lists each person
with fields still to confirm (「- 王則閔 博士：Email」). Files go to
`<workspace>/business-cards/<actor-key>/charts/`; the result names them in `attach`.

**Format** (owner 2026-10-20, 「請幫我全做」: a live test asked for the chart as interactive
HTML and the Agent tried a one-off `coding__run` script). `org-chart` takes `format`: `png`
(the default, unchanged), `html` or `both`. The Skill uses `html` when the person asks for an
interactive, HTML, searchable or tree view. The HTML (`capabilities/business_cards/chart_html.py`)
is one self-contained file beside the PNG in `charts/`, built from the same rows (grouping path,
title order, lines, fields to confirm), general (the title comes from the data, nothing about a
company is built in):

- **Tree view**: company → business group → division → department → people, collapsible
  (`<details>`). Where reporting lines exist, a reporting tree comes first (solid = evidence,
  dashed = inferred, each edge labelled with its evidence); the grouping follows, labelled as
  grouping only. Without evidenced lines the page shows the same warning as the legend.
- **Grouped view**: the nested boxes, like the PNG.
- **Search** by name, romanised name, title, business group, division, department or email;
  arrow keys and Enter, or a click, open the **person card**: name and honorific, company,
  business group / division / department, title, phone#ext, mobile, fax, email, 在職 / 已離職,
  需確認 fields, sources (名片 / 郵件簽名檔 / 使用者) with their latest dates (Asia/Taipei), and
  reporting lines with evidence. Esc closes it.
- **顯示已離職** toggle: the page always carries the people who left; they are hidden unless
  `include_left` was asked for, and drawn grey. The PNG and legend still follow `include_left`.
- Light and dark mode (`prefers-color-scheme`), responsive to 390 px with no horizontal page
  scroll, keyboard accessible, 44 px targets.
- **Safety**: inline CSS, script and data only; a `<meta>` CSP `default-src 'none'`; no network,
  no CDN. The data is JSON in `<script type="application/json">` with `<`, `>`, `&`, U+2028/9
  escaped, and the script builds every element with text nodes (no `innerHTML`), so a contact
  field holding `<script>` stays text.

**Showing it.** Agent Web: after a Gateway turn, files named by a `cards__org_chart` result are
kept on the answer (`ConversationMessage.attachments`; kinds `image`, `html`, `text`). Every file
on an answer, and every file the person attached, is a chip that opens the **file viewer** panel
(Preview / Code); the PNG shows inline, and the HTML shows inline in a sandboxed frame (480 px,
resizable, 放大, 在面板開啟, 在瀏覽器開啟). Files come only through `GET
/api/conversations/file` (token header; only files listed on that conversation's messages, under
the workspace; text, HTML included, served as plain text). The HTML is rendered only from
`/view/file?nonce=`, a short-lived address the page asks for with its token, served with a strict
CSP (`default-src 'none'`, inline script and style only, `sandbox allow-scripts`, `frame-ancestors
'self'`) inside `<iframe sandbox="allow-scripts">` without `allow-same-origin` (decision
2026-10-20 "In-chat HTML runs in an opaque-origin sandbox from a nonce address"). HTML a
`coding/run-python` step writes in a workspace is not attached to answers (attachments come only
from `cards__org_chart` today), so it is not shown inline yet. Telegram: the PNG is sent with
`sendPhoto` after the text reply, the HTML with `sendDocument` and a one-line caption to open it
in a browser (§7). The legend is in the answer text (appended by the Host when the model left it
out), carried by the first picture or page.

## 7. Telegram (the main way cards arrive)

Owner update 2026-10-20: most cards arrive as a photo sent to the Telegram bot.

- A compressed photo, or a photo sent as a file (JPEG / PNG / WebP / GIF / BMP; a file without a
  name is typed from its MIME type), is downloaded into the attachment store and reaches the model
  as an image (the same `for_model` path as Agent Web). A bare photo with no caption is a card to
  store; the card is stored in the same turn. HEIC files are refused with the usual "file type not
  supported" reply (send it as a photo, which Telegram converts to JPEG).
- An album (a media group in one poll batch) is one turn with every picture; the Skill stores one
  card per photo and answers one short line per card.
- The reply is short: the confirmed fields, the uncertain ones asked one per line, and the
  "上次是…, 現在是…" sentence for a known person who changed.
- The org chart goes back with `sendPhoto` (multipart, through the bot's own transport) captioned
  with the short note (only drawn lines are reporting lines), then the full Markdown legend with
  `sendDocument`; the text reply carries the legend's title and notes without the table. An
  interactive chart (`format` `html` or `both`) arrives as an `.html` document captioned
  「互動式組織圖：請下載後用瀏覽器開啟（可搜尋、切換樹狀／分組檢視）。」, before the legend.

## 8. Import from the Hermes store

`aep-host cards import [--from PATH] [--actor NAME]` or the `cards__import_hermes` tool reads
`cards.db` from `BUSINESS_CARDS_HOME` or `~/.business-cards` (the tool reads only that default
place). Every row becomes an observation with source `card`, its `captured_at` date and source ref
`hermes-cards:<id>`; rows are merged oldest first, so newer scans win. Running it again adds
nothing. The Hermes `business-cards` pack Skill stays switched off.

## 9. Not in this slice

- A "Contacts" page in Agent Web (the chat covers find / list / history; a page would be a large
  addition to `web_page.py`).
- Accepting a proposal from a button (the user says so in chat; `edit-person` `confirm` /
  `accept` records it).
- Graph layout of deep reporting trees beyond the grouped boxes and connecting lines (the HTML
  page shows the reporting tree as an indented list).
