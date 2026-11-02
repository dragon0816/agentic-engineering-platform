# Atlas embed goldens (vendored)

Producer: Atlas, `web/tests/fixtures/atlas_embed_golden/` at commit `4104c8d`
(`4104c8d775b0d307fb2fcd44c6d868fc76850656`, branch `atlas-embed`; the bytes are unchanged since `c7f9468`), contract `docs/AEP_EMBED_CONTRACT.md`.
Consumer: AEP's Atlas embeds in the chat (BI E1-E5, `docs/phases/BI_CHAT_EMBED_AND_PANEL_EDIT.md`).

`access-decisions.json`, `example-urls.json` and `response-headers.json` are copied byte for byte. Never edit them
here: a contract change starts in Atlas. Check for drift against an Atlas checkout:

    python scripts/check_atlas_dashboard_golden.py --atlas <Atlas repo>
