# Voice input: speak instead of type (Telegram and Agent Web)

Status: design for the owner's review (2026-11-01). No `src/` change yet. Owner goal (2026-11-01): a person can
speak instead of type, through **Telegram** (voice messages) and **Agent Web** (microphone), to do the three things
AEP already does by text: **coding**, **asking** (knowledge questions) and **Workflow/task execution**. Voice becomes
text through speech-to-text (STT); the person sees the transcript; from there the request follows exactly the same
path, rules and confirmations as typed text. Integration-tested end to end.

Nothing here is built until the owner answers §7. Decisions, once taken, go to `docs/DECISIONS.md`; progress rows
go to `docs/TASKS.md`.

## 1. Requirements

### 1.1 Functional

- **F1 Telegram voice.** A mapped sender's Telegram `voice` message (and an `audio` message within the limits, see
  §7 d4) is downloaded, transcribed on the host that runs `TelegramIngress`, shown back to the person as text and
  then handled exactly as if the person had typed that text in the same chat (same session, same reply context).
- **F2 Agent Web microphone.** The chat composer gets a microphone button. The person records, the recording is
  uploaded to the local Agent Web, transcribed, and the transcript is placed in the message box. The person reads
  or edits it and presses Send; the turn is the ordinary text turn.
- **F3 Three uses, one path.** The transcript reaches coding, knowledge questions and Workflow runs only through
  the existing text entry points (§2.3). No voice-specific routing, prompt, intent model or shortcut.
- **F4 Transcript visible before action.** The person always sees what AEP heard before anything acts on it
  (Agent Web: in the box before sending; Telegram: as the first line of AEP's answer, before any card or result).
- **F5 Same confirmations.** Every confirmation, approval and question a typed request gets, a spoken request gets.
  In addition, a transcript is never accepted as a confirmation or approval tap (§2.4).
- **F6 Traceable.** Each transcription leaves a transcript record (§3.4) linking channel, person, session, audio
  hash, STT engine and model version, and the text that was used.
- **F7 Clear failures.** Too long, too large, unsupported format, silence, STT not enabled or failed: the person
  gets a short Traditional Chinese reply saying what happened and what to do; nothing is sent to the Agent.
- **F8 Local-first and off by default.** Voice is an opt-in host feature (`host.json` `voice` section, optional
  `voice` package extra). A host without it behaves exactly as today, including Telegram's current refusal of
  voice messages.
- **F9 Mixed language.** Taiwanese Mandarin with English product terms (e.g. "CMX500", "Wi-Fi 8") is the target;
  Chinese output is in Traditional characters (§7 d3).

### 1.2 Non-goals

- Spoken replies (text-to-speech), wake words, continuous dictation or hands-free conversation.
- Long recordings (meetings, customer visits) turned into Knowledge drafts: that is the separate
  voice-to-knowledge track (draft PR #240, issues #234/#236); this design only covers spoken *instructions*.
- Speaker identification or voice as authentication. The actor is the mapped Telegram sender or the Agent Web
  token holder, as today.
- Telegram `video_note`, video files, voice in group chats beyond what the ingress already admits.
- Any change to how typed text is routed, confirmed or approved; any n8n; any inbound route to the Bridge; a second
  consumer of the bot token.
- Speaking a confirmation or an approval (buttons stay the only way, §2.4).

## 2. Architecture

```text
Telegram voice/audio message                      Agent Web 🎤 (MediaRecorder, audio/webm;opus)
  | getUpdates (existing poll)                      | POST /api/voice/transcribe (loopback, bearer)
  v                                                 v
TelegramIngress._deliver                         AgentWebServer
  | mapped sender? limits? (before download)        | limits
  | getFile + download (existing _download)         |
  +----------------------+     +--------------------+
                         v     v
                 voice.VoiceService (host-local, one model, one job at a time)
                   decode (PyAV -> 16 kHz mono PCM) -> SttProvider.transcribe
                   -> post-process (Traditional, trim) -> TranscriptRecord (store)
                         |                     |
       Telegram: "🎤 你說：「…」"           Agent Web: transcript put in textarea,
       then update.text = transcript        person edits / presses Send ->
       -> unchanged text path in _deliver   POST /api/conversations/turn (unchanged path)
                         |                     |
                         v                     v
       existing routing: slash/flow/run_intent/converse/handle  |  form offer / knowledge / converse
       -> Workflow confirmation card, approvals, coding-change approval, knowledge answer
```

### 2.1 Where audio enters

- **Telegram.** `TelegramIngress._parse` (`src/channels/telegram.py`) today reads only text/caption, `document` and
  the largest `photo`; a voice message yields no text and no files and `_deliver` answers
  "Only text messages are accepted here." (`unsupported_content`). The change: `_parse` also reads `message.voice`
  and `message.audio` into a new `voice` field of the parsed update (file id, duration, MIME type, size). Polling,
  offset, sender mapping, transport and the token handling stay as they are; no second bot consumer.
- **Agent Web.** A new loopback route `POST /api/voice/transcribe` (§3.1) under the existing guards (loopback Host
  check, per-run bearer token, POST path allow-list, JSON body). The page records with `getUserMedia` +
  `MediaRecorder`; `http://127.0.0.1` is a secure context, so the browser allows the microphone after the
  person's permission prompt.

### 2.2 Where STT runs

On the Personal Agent host itself (the PC running Agent Web and the resident Telegram ingress), in-process behind a
`SttProvider` interface (§3.5), inside a new `src/voice/` package:

- `VoiceService` owns one lazily loaded model, a single-slot worker (one transcription at a time, a small bounded
  queue, a timeout) and runs the blocking STT call in a thread so the Telegram poll loop and the web server stay
  responsive. The model is unloaded after an idle period (configurable) to give memory back.
- Decoding uses PyAV (already a dependency of faster-whisper; its wheels bundle FFmpeg libraries, so no system
  `ffmpeg` install). OGG/Opus (Telegram voice), WebM/Opus (MediaRecorder), MP3/M4A/WAV are decoded to 16 kHz mono
  PCM before STT.
- Which engine runs is an owner decision (§7 a). The default proposal is local; a cloud or company-gateway
  provider plugs in behind the same interface only after the owner approves the data flow.

### 2.3 How the transcript joins the existing text path

**Telegram.** After a successful transcription, `_deliver` sends (or edits the existing `_Progress` status message
into) `🎤 你說：「<transcript>」`, then continues with `update.text = transcript` through the *unchanged* rest of
`_deliver`: summary-note/card taps, open question flow (`telegram_flow.answer`), `run_intent` → `_open_flow`,
`_converse` → `LocalAgent.converse`, or `LocalAgent.handle`. The `LocalAgentRequest` built by `_request` is the same
object a typed message with the same text would build (ingress `telegram`, same `session_id`, same reply context).
A caption on the voice message, if any, is placed before the transcript separated by a blank line.

**Agent Web.** The route returns the transcript; the page puts it in `textarea#message` with a note
「語音轉文字，請確認內容後送出」. Nothing is sent until the person presses Send, which posts the ordinary
`POST /api/conversations/turn`. The only addition to that request is an optional `voice_transcript` id (§3.2) so
the transcript record can note whether the text was edited; when absent (every typed turn) behaviour is unchanged.

Per use, after that point nothing is voice-specific:

| Use | Typed text today | Spoken text |
|---|---|---|
| Asking | Agent Web: `_conversation_turn` routes to `knowledge_direct`/`ask_knowledge` or `converse` with knowledge tools; Telegram: `_converse` (model tools) or `/wiki-query` | same |
| Workflow / task | Agent Web: `run_intent` → inline form (`_run_form_offer`) → person submits `POST /api/workflows/run`; Telegram: `run_intent`/`/run` → `telegram_flow` questions → confirmation card (「確認執行」/「修改」) → `execute_workflow`; model-initiated non-read runs become `ApprovalRequest`s | same; the card or form is the confirmation |
| Coding | Workflow `engineering/coding-change` (capability `coding.change`, `side_effect: write`, `approval_required: true`) chosen by the Agent, so it goes through the Workflow form/card and approval; coding-agent conversation backends (Claude Code/Codex over ACP) receive the turn text as today, with their existing PUBLIC-session rule | same |

The transcript is part of the model request exactly like typed text, so the existing data-trust rule applies to it
unchanged (UNCLASSIFIED to the approved Gateway; PUBLIC-only for the restricted external CLI text chat).

### 2.4 What the person sees and confirms

- **Agent Web:** the transcript in the box before sending (editable). Sending is the person's act, as with typing.
  Forms, approvals and cards follow as for text.
- **Telegram:** `🎤 你說：「…」` first, then the normal answer, question, form card or approval button. While the
  transcription runs, the status line shows 「🎤 轉文字中…」 (existing `_Progress`).
- **Voice never confirms.** `telegram_flow` accepts typed words such as 「好」「是」「確認」「執行」"yes" as
  「確認執行」 (`_RUN_WORDS`), and some cancel/edit words. A misheard or casual 「好」 must not start a run. Rule: when
  a transcript arrives while a confirmation card is open, a transcript that matches a run/approve word is not
  consumed as a confirmation; AEP answers 「請按「確認執行」按鈕確認，語音不能代替確認。」 and the card stays open.
  Transcripts never match callback-data patterns (`run:yes`, `approve:`, `edit:N`, card taps) because those are
  only accepted from button callbacks. A spoken answer to an open *question* (a missing value) is accepted, since the
  final confirmation card lists it with its origin before anything runs. Typed text keeps today's behaviour. Whether
  spoken *cancel* is allowed is §7 d2.

## 3. Contracts

### 3.1 Agent Web: `POST /api/voice/transcribe`

Guards: the existing loopback Host check (403), bearer token (401), path allow-list; JSON body, base64 audio,
consistent with `/api/attachments`. Body limit `MAX_VOICE_REQUEST_BYTES = 14 MiB` (10 MB audio as base64 plus
fields). When the host has no `voice` section the route answers `{"ok": false, "code": "voice_disabled"}`.

Request (`VoiceTranscribeRequest`, a `Contract` with `reject_embedded_secrets`):

```json
{"session_id": "c-…", "mime_type": "audio/webm;codecs=opus", "duration_ms": 8400, "data": "<base64>"}
```

- `session_id`: the conversation the transcript belongs to (`Symbol`).
- `mime_type`: what `MediaRecorder` reports; one of the accepted types in §3.3.
- `duration_ms`: client-measured, advisory; the server measures the decoded length and enforces the limit.

Response:

```json
{"ok": true, "transcript": {"id": "vt-01J…", "text": "幫我查 CMX500 的 Wi-Fi 8 選項", "language": "zh",
 "duration_seconds": 8.4, "engine": "faster-whisper", "model": "small-int8", "elapsed_seconds": 2.1}}
```

or `{"ok": false, "code": "<error code §3.6>", "message": "<zh-TW text>"}` with HTTP 200 for user errors (as the
other Agent Web routes do), 413 for an over-limit body, 503 `stt_busy` when the queue is full.

### 3.2 Agent Web: `ConversationTurnRequest` (additive)

`voice_transcript: Symbol | None = None`. When set, the server looks up the record for this session and person,
stores `used_as = {turn, edited, sent_text_sha256}`; an unknown or foreign id is ignored (logged), never an error
that blocks the turn. The text of the turn is always `message`, never the stored transcript.

### 3.3 Telegram handling

- **Read:** `message.voice` `{file_id, file_unique_id, duration, mime_type, file_size}` and `message.audio`
  `{file_id, duration, mime_type, file_size, file_name}`. `video_note` and `video` keep today's refusal.
- **Order in `_deliver`:** unmapped sender → as today (no reply, no download). Voice present and voice disabled
  → today's reply "Only text messages are accepted here." unchanged. Voice present and enabled → limits, download,
  transcribe, show, continue as text (§2.3). A message with both files and voice does not occur in Telegram.
- **Limits checked before download** from the update's own `duration`/`file_size`: `max_seconds` (proposed 180),
  `max_bytes` (proposed 10 MB; Bot API `getFile` itself is limited to 20 MB, `TELEGRAM_DOWNLOAD_BYTES`). Checked
  again after decoding (the measured length wins).
- **Download:** the existing `_download(file_id)` (`getFile`, `file_path` validation, streamed GET from
  `{api_base}/file/bot<token>/<path>` with a byte cap, `AttachmentError` codes). The audio is written to a
  per-session temporary file under the workspace voice store, never to `attachments/`, so a voice message is not
  an attachment the Agent can read.
- **Accepted formats** (both channels): `audio/ogg` (Opus), `audio/webm` (Opus), `audio/mpeg`, `audio/mp4`/`m4a`,
  `audio/wav`, `audio/x-wav`. Anything else, or a file PyAV cannot decode → `audio_unsupported_format` /
  `audio_decode_failed`.
- **Ordering:** `_deliver` is awaited per update, so a chat's messages stay in order; the poll loop is not
  blocked because STT runs in a worker thread.

### 3.4 Transcript record (`aep.voice.transcript/v1`)

Stored per person under `<workspace>/voice/<sha256(session)[:24]>/<id>.json` (same hashing idea as
`AttachmentStore`), written atomically; listed only for that person and session.

```json
{
  "schema": "aep.voice.transcript/v1",
  "id": "vt-01J…",
  "channel": "telegram | web",
  "actor": "<mapped actor>",
  "session_id": "<chat or conversation session>",
  "created_at": "2026-11-01T12:00:00+08:00",
  "audio": {"sha256": "…", "mime_type": "audio/ogg", "bytes": 48213, "duration_seconds": 7.9,
            "retained": false, "path": null},
  "stt": {"provider": "faster-whisper", "model": "whisper-small", "model_revision": "<sha256 of model files>",
          "compute": "cpu-int8", "language_requested": "zh", "language_detected": "zh",
          "settings": {"beam_size": 5, "vad_filter": true, "initial_prompt_sha256": "…"},
          "elapsed_seconds": 2.1},
  "text_raw": "…", "text": "…", "post_processing": ["opencc:s2twp", "strip"],
  "segments": [{"start": 0.0, "end": 3.2, "text": "…"}],
  "status": "ok | empty | failed", "error_code": null,
  "used_as": {"turn": "<turn or update id>", "edited": false, "sent_text_sha256": "…"}
}
```

No credential, token or Telegram file URL is ever stored (the file URL contains the bot token). `text_raw`/`text`
are kept or removed according to §7 c.

### 3.5 STT provider interface (`src/voice/stt.py`)

Ported and extended from `benchmarks/voice_to_knowledge/provider.py` on `origin/feature/voice-to-knowledge`:

```python
@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str

@dataclass(frozen=True)
class SttResult:
    segments: tuple[Segment, ...]
    language: str | None          # detected
    duration_seconds: float       # audio length
    elapsed_seconds: float
    engine: str                   # "faster-whisper", "fake", …
    model: str
    model_revision: str
    @property
    def text(self) -> str: ...

class SttProvider(Protocol):
    def transcribe(self, pcm: Pcm16k, *, language: str | None, hints: tuple[str, ...]) -> SttResult: ...

class SttError(Exception):
    code: str                     # one of §3.6
```

- `Pcm16k` is decoded mono 16 kHz PCM produced by `voice.audio.decode(path, limits)`, so providers never see
  container formats (the branch's provider accepted WAV only).
- `hints`: product terms (e.g. from an owner-editable glossary in the host data directory) passed to Whisper as
  `initial_prompt`/hotwords to bias spelling of terms such as CMX500; empty by default.
- Implementations: `FakeSttProvider` (tests: maps audio sha256 or a fixture name to a fixed result; can raise any
  code), `FasterWhisperProvider` (default local engine, §7 a), and later a gateway provider only if §7 a approves.
- Host configuration (`host.json`, no secrets): `voice: {enabled, provider, model_path, model_sha256, language,
  max_seconds, max_bytes, timeout_seconds, idle_unload_seconds, retention}`. A cloud provider's key would be a
  `SecretRef`, never a value.

### 3.6 Error cases

| Code | When | Person sees (zh-TW, short) | Agent called? |
|---|---|---|---|
| `voice_disabled` | host has no `voice` section | Telegram: today's text-only reply; Web: mic button hidden | no |
| `audio_too_long` | duration > `max_seconds` (declared or measured) | 語音超過 3 分鐘，請分段或改用文字。 | no |
| `audio_too_large` | bytes > `max_bytes` | 檔案太大… | no |
| `audio_unsupported_format` | MIME/container not accepted | 不支援這種音訊格式… | no |
| `audio_decode_failed` | corrupt or truncated | 無法讀取這段音訊… | no |
| `download_failed` | existing `AttachmentError` from `_download` | existing `attachment_reply` text | no |
| `transcript_empty` | silence/no speech, or only filler | 沒有聽到內容，請再說一次。 | no |
| `stt_unavailable` | model missing or hash mismatch | 語音轉文字目前無法使用（模型未安裝）。 | no |
| `stt_busy` | queue full | 語音處理忙碌中，請稍後再試。 | no |
| `stt_timeout` / `stt_failed` | engine timeout or exception | 語音轉文字失敗，請再試一次或改用文字。 | no |
| `voice_not_confirmation` | transcript matches a run/approve word while a card is open | 請按「確認執行」按鈕… | no (card stays) |

Every failure writes a transcript record with `status: failed` and the code; nothing reaches `LocalAgent`.

## 4. Test plan

All automated tests are CI-inert: no real microphone, no Telegram, no network, no model download.

### 4.1 Fixtures without real people's recordings

`scripts/voice_fixtures.py` (dev-only, deterministic, committed output under `tests/fixtures/voice/` with a
`manifest.json` of text, generator, voice name, format and sha256):

- **Synthetic speech** from text-to-speech (default: Windows' built-in offline SAPI voices via `System.Speech`;
  zh-TW and en-US sentences such as 「幫我查 CMX500 的 Wi-Fi 8 選項」, 「執行週報 Workflow」,
  「把 parser 的 CSV 欄位改成 UTF-8」). The reference transcript is the TTS input text. Licence of committing TTS
  output is §7 d6.
- **Non-speech** from the standard library `wave` module: 2 s silence, a 1 kHz tone, seeded white noise.
- **Format variants** encoded from the same PCM with PyAV: OGG/Opus (Telegram voice), WebM/Opus (MediaRecorder),
  MP3, WAV; plus a truncated file, a zero-byte file, a text file renamed `.ogg`, and an over-limit duration file
  generated on the fly in tests (not committed).
- Fixtures stay small (each under ~100 KB). No recording of any real person, no company or customer content.

### 4.2 Unit (always run)

- `voice.audio`: decode each format to 16 kHz mono; limits by declared and measured length; decode failures.
- `VoiceService`: single slot, queue full → `stt_busy`, timeout, idle unload, model hash mismatch →
  `stt_unavailable`, post-processing (Traditional conversion, trimming), empty transcript.
- Transcript store: schema, per-person/session isolation, retention purge, no token/URL in any record.
- Contracts: `VoiceTranscribeRequest` validation, secrets rejected, `ConversationTurnRequest` without
  `voice_transcript` serialises exactly as today.

### 4.3 Integration with fixture audio (always run, `FakeSttProvider`; opt-in real engine)

- With `FakeSttProvider` keyed by fixture sha256, the full channel path runs: decode → record → text path.
- **Parity tests (the core claim):** for each of the three uses, the request produced by a voice fixture equals the
  request produced by typing the same text — same `LocalAgentRequest`/`ConversationTurnRequest`, same route
  decision (`RequestRouter` trace), same Workflow form/card, same `ApprovalRequest` for `coding.change` — using the
  existing fake model/Gateway fixtures. Asking: knowledge answer with the same citations; Workflow: the card lists
  the same values and nothing runs before 「確認執行」; coding: the approval request appears and nothing writes
  before approval.
- **Negative cases:** a transcript 「好」 while a card is open does not run; a voice message from an unmapped sender
  is never downloaded; an over-limit voice message is refused before download; silence → `transcript_empty` and no
  Agent call; voice disabled → today's reply byte-for-byte.
- **Real engine (opt-in):** marked tests that run `FasterWhisperProvider` on the TTS fixtures when
  `AEP_VOICE_MODEL_DIR` points at an installed model; assert CER below a threshold set in V0 and that product terms
  appear; skipped otherwise, like the existing environment-extra skips.

### 4.4 Headless Agent Web with fake audio

The existing `integrations.browser.Browser` (headless Chromium/Edge over CDP) gains optional extra launch flags
(additive) so the test can pass `--use-fake-ui-for-media-stream --use-fake-device-for-media-stream
--use-file-for-fake-audio-capture=<fixture.wav>`. The test serves Agent Web with `FakeSttProvider` (returns a fixed
transcript for any decodable audio, since the browser re-encodes), clicks 🎤, waits, stops, asserts the transcript
is in `textarea#message` and nothing was sent, edits it, presses Send and asserts the turn equals a typed turn. Also:
permission denied (no fake-UI flag) shows a message and leaves the box untouched; `voice_disabled` hides the button.
Skips when no browser is found, like the other browser tests.

### 4.5 Telegram with a fake Bot API server

Two layers:

- The existing in-process `FakeTransport`/`FileTransport` pattern (`tests/test_telegram_ingress.py`,
  `tests/test_telegram_attachments.py`) extended with `voice`/`audio` updates and `getFile` + download of fixture
  audio.
- A real local HTTP fake Bot API (`tests/fake_bot_api.py`, `http.server` in a thread) implementing `getUpdates`,
  `getFile`, file download, `sendMessage`, `editMessageText`, `answerCallbackQuery`. Because
  `TelegramIngressConfig.api_base` only accepts `https://` (and must stay that way for production), the ingress keeps
  the default `https://api.telegram.org` and the test injects a `Transport` that forwards that origin to the fake
  server's `http://127.0.0.1:<port>`. No production config change (§7 d5). The test drives a full conversation: voice
  → 「🎤 你說」 → card → callback 「確認執行」 → run result.

### 4.6 Live checks (owner-run, not CI, after hours per the GUI-test rule)

1. Telegram, owner's phone, zh-TW voice: a knowledge question about a product option; the transcript and a cited
   answer appear.
2. Telegram voice: "run <installed read-only Workflow> for …"; questions, card, tap 「確認執行」, result. Then say
   「好」 at the card and see that it does not run.
3. Agent Web on the company laptop, real microphone in Edge: a coding request that reaches the `coding-change`
   approval; nothing changes before approval.
4. Mixed Chinese/English with product terms, in a normal office noise level; note misheard terms for the glossary.
5. Latency on the company laptop for 5 s, 30 s and 120 s messages with the chosen model (feeds §7 a).
6. Retention: after the retention period the audio/transcript are gone as decided in §7 c.

## 5. Reuse from `origin/feature/voice-to-knowledge` (not merged)

The branch is a Phase 0 prototype: no real STT inference was ever run (model downloads were blocked), nothing under
`src/`, 180 commits behind `main`. Port by copying and adapting, not merging:

| Piece | Port? | How |
|---|---|---|
| `provider.py` `Segment`/`Transcript`/`Provider`/`consume`, `FasterWhisperProvider`, fixed decode settings | yes | becomes `src/voice/stt.py`; add duration, engine, model, revision; take decoded PCM instead of WAV-only |
| `validate_audio` (size/duration/truncation checks, error codes) | yes, adapted | becomes `voice.audio` limits; the WAV-only rule is replaced by PyAV decoding |
| `metrics.py` (CER/WER/MER, NFKC normalisation, term recall) | yes | for the opt-in real-engine tests and the V0 measurement |
| `runner.py`/`worker.py` (process-isolated CPU benchmark: latency, RTF, peak RSS) | yes, as a script | `benchmarks/voice_input/` for the V0 laptop measurement; corpus = §4.1 fixtures instead of FLEURS |
| `requirements.lock` (faster-whisper 1.2.1, ctranslate2 4.8.3, av) | reference | versions as a starting point for the `voice` extra; re-lock on Windows |
| `docs/voice-to-knowledge/VOICE_NETWORK_REQUIREMENTS.md` | reference | Hugging Face downloads were blocked (403 through the proxy) → model delivery is §7 d7 |
| `extraction.py`, `submission.py`, schemas, demo | no | voice-to-knowledge drafts are out of scope (§1.2); #234 stays open for that track |
| `HANDOFF.md`/`TASKS.md` edits, unrelated test file | no | stale |

## 6. Tasks (ordered slices, each testable)

| # | Slice | Done when |
|---|---|---|
| V0 | Owner decisions §7; owner-run engine measurement on the company laptop with the ported benchmark and §4.1 fixtures | decisions in `DECISIONS.md`; CER/latency table recorded; CER threshold chosen |
| V1 | `src/voice/` contracts: `SttProvider`, `SttResult`, `SttError` codes, `FakeSttProvider`, transcript record + store + retention; fixtures script and committed fixtures | unit tests §4.2 (store, contracts); ruff/mypy |
| V2 | Decoding (PyAV) and `VoiceService` (single slot, timeout, idle unload); `voice` optional extra; `host.json` `voice` section | unit tests §4.2; host without `voice` unchanged (existing suite) |
| V3 | `FasterWhisperProvider` (or the engine chosen in V0), model path + sha256 check, glossary hints, Traditional post-processing | opt-in real-engine tests pass on the owner's laptop; skipped in CI |
| V4 | Telegram: parse `voice`/`audio`, limits before download, download, transcribe, 「🎤 你說」, continue as text; voice-not-confirmation guard | Telegram unit/integration tests, parity tests for the three uses, negatives §4.3; all existing Telegram tests unchanged |
| V5 | Telegram fake Bot API server test (§4.5) | end-to-end voice → card → callback → result passes |
| V6 | Agent Web: `POST /api/voice/transcribe`, `voice_transcript` on turns | route tests (guards, limits, errors), parity tests |
| V7 | Agent Web UI: 🎤 button, recording timer and limit, transcript into the box, errors; `Browser` extra flags | headless browser test §4.4 |
| V8 | Contracts into `docs/CONTRACTS.md`, user guide section (zh-TW), `ARCHITECTURE.md` channel note; full suite | full suite, ruff, mypy clean; owner live checks §4.6 listed in `HANDOFF.md` |

V1–V3 can be built and tested before any channel work; V4–V5 and V6–V7 are independent of each other.

## 7. Open owner decisions

### a. STT engine: local or cloud

Local candidates (CPU only; sizes are approximate for int8 weights; speeds must be measured in V0 on the company
laptop, the branch never measured any):

| Engine / model | Licence (code / model) | Size | CPU cost (estimate) | Mixed zh/en |
|---|---|---|---|---|
| faster-whisper + Whisper **small** | MIT / MIT | ~250 MB int8, ~1 GB RAM | faster-whisper's published CPU figure: small int8, 8 threads, 13 min audio in ~1 min 42 s (≈0.13× real time); a 4-core laptop likely 0.2–0.4×, i.e. a 15 s message in ~3–6 s | good, some term errors |
| faster-whisper + Whisper **large-v3-turbo** | MIT / MIT | ~800 MB int8, ~2 GB RAM | roughly 3–4× small on CPU; 15 s in ~10–20 s | better |
| faster-whisper + Whisper **medium** | MIT / MIT | ~800 MB int8 | similar to or slower than turbo | better than small |
| sherpa-onnx + SenseVoice-Small | Apache-2.0 / FunASR model licence (needs review) | ~230 MB int8 | non-autoregressive, much faster than Whisper small | strong Mandarin; English terms weaker; outputs Simplified |
| Vosk (small-cn / en) | Apache-2.0 / Apache-2.0 | 40–50 MB per language | very low | weak: one language per model, no punctuation |
| Breeze-ASR-25 (Whisper large-v2 fine-tuned for Taiwanese Mandarin + code-switching) | Apache-2.0 (verify) | ~1.5 GB int8 | too slow for interactive use on a laptop CPU | best fit for zh-TW, but heavy |

New third-party packages need the owner's OK: `faster-whisper` (MIT), `ctranslate2` (MIT), `av` (BSD-3; wheels
bundle FFmpeg under LGPL), and their transitive `tokenizers`/`huggingface-hub` (Apache-2.0) and `onnxruntime` (MIT,
for the built-in VAD); optionally `opencc` (Apache-2.0, d3). All would sit in an optional `voice` extra, so hosts
without voice install nothing new.

Cloud options:
- **Company LLM Gateway** (the approved LiteLLM route) if company IT exposes a transcription model at
  `/v1/audio/transcriptions`: audio leaves the PC but stays on the company's governed route (through Zscaler, which
  is company IT's legitimate proxy); needs a gateway deployment and an explicit `models.data_approval`-style
  approval that covers audio, which the current approval (model text requests) does not.
- **Public cloud STT** (OpenAI, Azure Speech, Google): best accuracy and no local CPU cost, but company speech
  leaves the company; conflicts with the 2026-10-02 rule that UNCLASSIFIED data uses only an approved internal
  Gateway, and needs a credential (`SecretRef`) and egress approval.

**Recommended default:** local faster-whisper with Whisper **small** int8 as the default and large-v3-turbo as a
configurable upgrade, chosen after the V0 laptop measurement; keep the provider interface so a company-Gateway
provider can be added later under its own approval. No public cloud STT.

### b. May a voice instruction start coding or a Workflow directly after the transcript is shown?

- **Option 1 (recommended default):** the same confirmations as text, plus the transcript shown first; voice is
  never accepted as a confirmation or approval (§2.4). Telegram: read-only asks answer immediately after
  「🎤 你說」; anything that runs goes through its card/form/approval exactly like text. Agent Web: the person
  always presses Send.
  Trade-off: one tap more than speaking 「好」, no new risk.
- Option 2: an extra transcript confirmation for every Telegram voice message (「送出」/「修改」/「取消」 before
  routing). Safer against misheard asks, but slower and redundant for side-effecting requests that already get a card.
- Option 3: allow spoken confirmation. Hands-free, but a misheard 「好」 can start a run; not recommended.

### c. Audio retention

- Option 1: keep audio and transcript for the session-memory retention (default 30 days). Lets the owner re-check
  a misheard command; stores company speech on disk.
- **Option 2 (recommended default):** delete the audio as soon as transcription ends (success or failure); keep
  the transcript record (text, hashes, engine, model) for the same retention as task result summaries (default 30
  days, set on the memory page), then purge.
- Option 3: keep nothing beyond the turn (audio and transcript deleted; only the turn text remains in the
  conversation as for typed text). Smallest footprint, but no record of what STT heard versus what was sent.

### d. Other decisions this document cannot settle

1. **Which Telegram media count as instructions.** Recommended: `voice` always; `audio` files only within the same
   limits (a longer audio file is refused with a pointer to the voice-to-knowledge track); `video_note` refused.
   Alternative: `voice` only.
2. **Spoken cancel / edit at a confirmation card.** Recommended: spoken 「取消」 cancels (it removes a side effect,
   never adds one) and spoken 「修改」 opens editing; spoken confirm is refused (§2.4). Alternative: voice is
   ignored entirely while a card is open.
3. **Traditional Chinese output.** Whisper often writes Mandarin in Simplified characters. Recommended: convert with
   OpenCC `s2twp` (new package, Apache-2.0) plus a Traditional initial prompt; alternative: initial prompt only (no
   package, less reliable).
4. **Limits.** Recommended 180 s and 10 MB per message on both channels; the Agent Web recorder stops itself at
   the limit.
5. **Fake Bot API test seam.** Recommended: keep `api_base` HTTPS-only and redirect in an injected test
   `Transport` (§4.5). Alternative: allow `http://127.0.0.1` in `api_base` for tests, which relaxes a production
   validator and is not recommended.
6. **Committed TTS fixtures.** Whether committing audio generated by Windows' built-in voices is acceptable in this
   public repository; alternative: an open TTS with a clear licence for its output (for example eSpeak NG, whose
   output is not covered by its GPL, at lower naturalness), or fixtures generated at test time and not committed.
7. **Model delivery.** Hugging Face downloads were blocked through the proxy on the earlier branch. Options: ask IT
   to allow the exact model URLs, or install an owner-approved model package (files plus sha256) into the host data
   directory. Recommended: the approved package with the sha256 pinned in `host.json`; the host never downloads a
   model by itself.
8. **Which hosts enable voice.** Recommended: off by default; the owner enables it per host (the Personal Agent PC
   running the resident Telegram ingress). Bridges without a person-facing channel never need it.
