# RS Knowledge market-fit evaluation

`rs-market-v1.json` pins three Raw files from the owner-classified public
RS_Knowledge staging Vault by SHA-256 and exact text anchor. The market note
states an 800G/1.6T networking need. The product specifications state a
CMX-B200A digital I/Q interface and SMBV100B RF wireless capabilities. These
three excerpts do **not** themselves establish that either product or option
is qualified for 800G/1.6T data-center testing.

Run the read-only source/retrieval check against the staged platform Vault:

```powershell
& .venv/Scripts/python.exe -m evaluation.knowledge_market --vault "$env:LOCALAPPDATA/AEP/rs-k"
```

Pass `--answer-record path/to/record.json` to inspect a saved
`KnowledgeAnswerRecord`. The narrow checker flags affirmative claims that join
a reviewed product to 800G/1.6T without one cited reviewed Raw passage naming
both. The report deliberately says `review_required` and
`semantic_entailment_proven: false` even when this check finds no problem.
Review each claim and cited Raw passage manually before accepting market fit.
The checker does not call a model or TypeSafe, and does not alter the Vault.
If the staged Raw bytes change, re-review the evidence and update the pinned
case deliberately; do not silently accept source drift.

The 2026-10-03 live Agent Web answer cited the three reviewed Raw files but
presented a product-to-800G/1.6T link that the cited excerpts do not prove.
The diagnostic correctly marks that saved local answer `failed`. Knowledge
Query now adds a market-fit instruction and retries/refuses an affirmative
product-to-rate assertion when only separate product and market sources were
cited. This is a narrow safeguard; it cannot prove every semantic claim.
