# Atlas embed goldens (vendored)

Producer: Atlas, `web/tests/fixtures/atlas_embed_golden/` at commit `c7f9468`
(`c7f9468cf32337053a295a90f029ccde25832503`, branch `atlas-embed`), contract `docs/AEP_EMBED_CONTRACT.md`.
Consumer: AEP's Atlas embeds in the chat (BI E1-E5, `docs/phases/BI_CHAT_EMBED_AND_PANEL_EDIT.md`).

`access-decisions.json`, `example-urls.json` and `response-headers.json` are copied byte for byte. Never edit them
here: a contract change starts in Atlas. Check for drift against an Atlas checkout:

    python scripts/check_atlas_dashboard_golden.py --atlas <Atlas repo>
