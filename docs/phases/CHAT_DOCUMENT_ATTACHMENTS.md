# Chat document attachments

Owner-approved 2026-11-09: use PDF, Excel (.xlsx) and Word (.docx) attachments
directly when discussing and creating Workflows; fix numbered reply headings.

## Contract and architecture

The existing session-owned AttachmentStore remains the entry point for Agent
Web and Telegram. Extraction is local, read-only and uses the installed Office
libraries. It does not ingest sources into Knowledge or change publication,
execution approval, model data policy or browser access. Originals remain
unchanged; the model receives bounded text, source locators, pictures and the
existing session-owned paths. DOCX reuses the existing Office extractor.

PDF text, hyperlinks and embedded pictures retain page numbers. DOCX paragraphs,
tables and pictures retain document order; document hyperlink targets are also
included. XLSX previews name sheets and row numbers,
retain formulas as formulas, and never execute macros or external links.
Parsing failures, absent dependencies and truncated previews are stated, rather
than silently implying the file was read completely. Legacy .doc/.xls are not
accepted. Existing text/image/zip behavior and session isolation remain intact.

Markdown ordered lists preserve their explicit starting number when interrupted
by paragraphs or bullet lists. Source text remains safely rendered without HTML.

## Acceptance and plan

- [x] Add failing tests in tests/test_attachments.py for PDF pictures/page labels,
  DOCX tables/pictures, XLSX formulas/sheets, corrupt files and bounded previews.
- [x] Implement document preview adapter and wire it into attachments.py; update
  the chat file picker in web_page.py. Existing for_model return shape is stable.
- [x] Add a failing DOM regression in tests/test_agent_web.py for separate lists
  starting at 1, 2, 3, 4; preserve start attributes in web_page.py.
- [x] Exercise actual owner PDF/XLSX through an isolated chat upload and authoring
  path; distinguish deterministic transport/authoring proof from live model/C4C
  acceptance. Never invent browser targets or claim C4C executed without evidence.
- [x] Run focused tests, full pytest, Ruff, Mypy, pip check and build; document
  exact results and limitations in TASKS/HANDOFF and commit verified changes.

Private owner files and extracted business data are not committed as fixtures.
Synthetic documents provide repeatable regression coverage. Runtime deployment
and restarting an active Agent are outside this change.
