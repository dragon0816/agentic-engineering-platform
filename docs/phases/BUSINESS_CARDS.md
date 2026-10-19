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
| Duplicates only by exact name + company | email first (case-insensitive); then name + company, where a romanised name matches the local-language name |
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
- **proposals**: a conflict between an automatic source and a user-set value.

### Field-level provenance (in the spirit of ADR-K11)

When a card, signature or import brings a value for a field:

1. empty field → set; provenance = that source and date;
2. current value set by the **user** → never overwritten; a differing value becomes a proposal
   and the result says so ("kept your value");
3. current value from an automatic source → replaced only when the new evidence is not older
   than the current value's evidence date; the change is in history;
4. a value the reading marked **uncertain** fills an empty field but never replaces a value.

`edit_person` sets values with source `user`.

**Needs confirmation.** A field needs confirmation while any observation of the person listed it in
`uncertain` and its current value is not the person's own (source `user`). A later scan that is
sure does not clear it. The person clears it by confirming the stored value (`edit-person`
`confirm: ["email"]`, history kind `confirm`, undoable) or by correcting it (`fields`); re-stating
the stored value in `fields` also confirms it. A wrong value is emptied with `edit-person`
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
- A unified business number in `notes` (統一編號 / 統編 / UBN / Tax ID + 8 digits) moves to
  `company_tax_id`. Decision `docs/DECISIONS.md` 2026-10-20 "Degrees and the unified business
  number are contact fields".
- Division and department text is never normalised: 研展處 I and 研展處 II are two boxes.

## 3. Operations (Bridge capabilities, namespace `business-cards`, version 1.0.0)

| Capability | Side effect | What it does |
|---|---|---|
| `add-card` | write | Fields + `uncertain` read from a card photo; returns created / updated / unchanged, what changed, what was kept, and a "上次是…, 現在是…" line |
| `add-from-signature` | write | 1–50 entries with message id and date; source `email_signature` |
| `edit-person` | write | The person's own corrections, source `user` |
| `set-status` | write | `left` / `active`, with reason, who said it and the date |
| `set-reporting-line` | write | Person → manager with evidence; replaces the person's current line |
| `remove-reporting-line` | write | Soft-removes the current line, with a reason |
| `undo` | write | Reverts one change group by its `change_id` |
| `import-hermes` | write | One-time, idempotent import of `~/.business-cards/cards.db` (`BUSINESS_CARDS_HOME`) |
| `find` | read | People matching a text (name, romanised name, email, company, title) |
| `list` | read | People by company, source and status |
| `history` | read | One person's changes and observations, with change ids |
| `org-chart` | read | PNG + Markdown legend for a company (writes only the derived files) |
| `harvest-signatures` | read | Mail in the configured scope from one company domain → signature candidates |

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
`cards__add_card`, `cards__add_from_signature`, `cards__edit_person`, `cards__find`, `cards__list`,
`cards__history`, `cards__set_status`, `cards__set_reporting_line`, `cards__remove_reporting_line`,
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
- when a tool fails, tell its failure message and code; mention Settings only when the message
  names it.

## 5. Email signatures

`harvest-signatures(domain, days, limit, folder)` searches the Outlook scope set in Agent Web
Settings → Agent mode (folders, `max_days`, exclusions), never wider: `days` is capped at
`max_days`. Only messages whose sender address ends with `@<domain>` are read. For each, the last
lines before any quoted reply are cut as the signature block (≤ 1,200 characters), credential-shaped
text is redacted, and at most 10 blocks go to the internal gateway model per structured call
(`business-cards.signature.v1`), at most 40 messages per harvest. The result is candidates
(fields, message id, date, whether the person exists and what would change). Nothing is stored
until `add-from-signature`; only fields, the message id and the date are ever stored.

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
who left are omitted, or drawn grey with "已離職" when `include_left` is true. Rendered with Pillow
(shipped in the bundle with the `weekly-mail` extra and in CI with `office`), no Graphviz; a CJK
font is taken from Windows Fonts (Microsoft JhengHei, then others) when present. The Markdown
legend lists each line with its evidence and whether it is inferred, and says plainly that without
evidenced lines the layout is a grouping by title, not a reporting chart. Files go to
`<workspace>/business-cards/<actor-key>/charts/`; the result names them in `attach`.

**Showing it.** Agent Web: after a Gateway turn, files named by a `cards__org_chart` result are
kept on the answer (`ConversationMessage.attachments`) and the page shows the PNG inline, fetched
through `GET /api/conversations/file` (token header; only files recorded on that conversation's
answers, under the workspace). Telegram: the PNG is sent with `sendPhoto` after the text reply (§7).
The legend is in the answer text (appended by the Host when the model left it out).

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
  `sendDocument`; the text reply carries the legend's title and notes without the table.

## 8. Import from the Hermes store

`aep-host cards import [--from PATH] [--actor NAME]` or the `cards__import_hermes` tool reads
`cards.db` from `BUSINESS_CARDS_HOME` or `~/.business-cards` (the tool reads only that default
place). Every row becomes an observation with source `card`, its `captured_at` date and source ref
`hermes-cards:<id>`; rows are merged oldest first, so newer scans win. Running it again adds
nothing. The Hermes `business-cards` pack Skill stays switched off.

## 9. Not in this slice

- A "Contacts" page in Agent Web (the chat covers find / list / history; a page would be a large
  addition to `web_page.py`).
- Accepting a proposal from a button (the user says so in chat; `edit-person` records it).
- Graph layout of deep reporting trees beyond the grouped boxes and connecting lines.
