"""The business-cards Skill: the procedure the conversation follows.

It has no commands: a Skill command to a capability gives the model no
argument schema, so the Host offers the `cards__*` tools itself, each with
its schema, while some version of this Skill is switched on
(`host_runtime.business_cards_tools`). The procedure comes from the Hermes
`business-cards` Skill, adapted to the native tools. Shipped switched on
(`host_runtime.assets.shipped`).
"""

from __future__ import annotations

from agent.skills import SkillManifest
from common.assets import AssetIdentity

CARDS_SKILL = AssetIdentity(namespace="engineering", name="business-cards", version="1.0.0")

PROCEDURE = (
    "Business cards and org chart 名片與組織圖. The person photographs cards and sends them "
    "(Agent Web or, most often, Telegram); you read the card and store it with "
    "cards__add_card in the same turn. A photo of a business card is a card to store even "
    "when no request comes with it. SEVERAL PHOTOS (an album): one card per photo, one "
    "cards__add_card call each with that photo's image_path, then one short line per card. "
    "READING A CARD: fill name, romanised_name, company, company_tax_id, business_group "
    "(事業群), division (處), department (部/課), title, honorific, phone, ext, mobile, fax, "
    "email, address, website, notes. title is the job title only: an academic or honorific "
    "title (博士, Dr., PhD) goes in honorific, never in title. Keep division and department "
    "text exactly as printed, including suffixes such as I, II, 一處 (研展處 I is not "
    "研展處). The unified business number (統一編號 / 統編 / Tax ID, 8 digits) always goes "
    "in company_tax_id, never in notes: look for it on every card (often near the company "
    "name or the address) and fill it whenever it is printed. Put any other printed text "
    "you did not place in a field in other_text, one line each. "
    "Local-language name and company in name/company, the romanised form in romanised_name; "
    "never join them in one field. romanised_name ONLY when an English / romanised name is "
    "printed on the card, with romanised_name_printed saying where (copied as printed); "
    "never derive it from the email or romanise the Chinese name yourself; no printed "
    "English name means romanised_name stays empty. Copy the email exactly as printed and "
    "never change the email to match a name; if a character is unclear, list email in "
    "uncertain. A result's dropped lists what the Host did not store; say so. "
    "phone is the desk number, ext its extension, mobile the "
    "cellphone; a lone unlabelled number goes in phone and phone goes in uncertain. "
    "uncertain is the point of the format: list every field you inferred, could not read "
    "clearly or guessed (a blurred digit, glare, a department you inferred). Never guess "
    "silently; omit a field rather than invent it. Pass image_path, the attached photo's "
    "path as listed. EVERY SCAN IS KEPT: a re-scan adds an observation and updates the "
    "person; values the person set themselves are never overwritten (they become proposals). "
    "REPORTING BACK: short (it is often read on a phone in Telegram; no tables, no field "
    "you did not read). Name fields in Chinese with the result's field_labels (英文名, "
    "統一編號, 事業群); never show raw field names such as romanised_name. Report only "
    "what the result says changed: never say something changed when the old and new "
    "values are the same. When you ask about a field, say its stored value from "
    "to_confirm (e.g. 「英文名目前是 Clark Wang，正確嗎？」), never ask as if it were empty. "
    "START every card reply with the result's match.lead (「已對到既有聯絡人 王小明（範例"
    "科技），依名片圖片比對。」 or 「已新增聯絡人 …」), then the changes (summary), then any "
    "questions; never open with a bare list of updated fields. "
    "Confirm company / name / department / title / numbers in one "
    "block. If uncertain is non-empty, ask about exactly those fields and nothing else, "
    "one per line. If "
    "the person was already on file (existed true), follow match.lead with the change: "
    "the result's summary, e.g. '上次是研發部經理, 現在是協理'. Mention kept values "
    "(user_set: their own value was kept). If a result has email_differs, say that the "
    "email read this time "
    "differs from the stored one, that the stored one was kept, and ask which is right. "
    "PROPOSALS: a result's proposals lists readings that differ from the person's own "
    "(set or confirmed) value, or another email: each field there needs confirmation "
    "(需確認 on the org chart). Say the stored value (current) and the value read "
    "(proposed) and ask which is right. When the person says the stored one is right "
    "(「X 的 email 正確」), call cards__edit_person with confirm ['email']: the stored value "
    "stays and the proposal is closed. When they say the other value, or 「用新的」, call "
    "cards__edit_person with accept ['email'] (or fields with that value). "
    "cards__proposals lists the open ones (one person's or everyone's); tell its note. "
    "Corrections the person gives go to cards__edit_person. "
    "NEEDS CONFIRMATION: a result's needs_confirmation lists fields some reading flagged "
    "that the person has not confirmed yet; ask about them too, even when this scan was "
    "sure. When the person says a stored value is right (e.g. 'email 正確'), call "
    "cards__edit_person with confirm ['email']; a correction goes in fields; a value "
    "that is wrong and should be empty (e.g. an English name not on the card) goes in "
    "clear. All are "
    "recorded in history and clear the warning on the org chart. "
    "COMPANIES: pass the company as the person says it (WNC, 啟碁, a mail domain): the Host "
    "finds the stored company by name, short name or domain, and the result's company is "
    "its stored name; use that name in the reply. "
    "ORG CHART: cards__org_chart draws the PNG and returns a legend; include the legend "
    "Markdown in your answer. Say what the chart is every time: boxes group by business "
    "group / division / department and order by title seniority; only drawn lines are "
    "reporting lines (solid = evidenced, dashed = inferred). Without evidenced lines it is "
    "NOT a reporting chart. Record a reporting line only with evidence "
    "(cards__set_reporting_line: signature, email_content, user) or as an explicit "
    "title_inference, which is drawn dashed. "
    "DEPARTURES: only when the person says someone left: cards__set_status status left, "
    "the reason, effective_date if they gave one (the Host records who said it). Tell them "
    "it is recorded "
    "and can be undone (cards__undo with the change_id, or set_status active). Never infer "
    "a departure yourself. "
    "EMAIL SIGNATURES: cards__harvest_signatures reads mail from one company domain within "
    "the mail scope the person set in Settings and stores nothing; list each candidate with "
    "its candidate_id (s1 王小明 協理, ...). When the person confirms (e.g. 都存進去, or "
    "'存 s1 和 s3'), call cards__store_candidates with those candidate_ids or [\"all\"]: the "
    "Host keeps each message id and date, so never harvest again just to store, and never "
    "copy message ids. Candidates expire after an hour; if store_candidates says they "
    "expired, harvest again. "
    "IF A TOOL FAILS: tell the person in one short line what the failure message says, "
    "with its code (e.g. 讀信失敗（message_unknown）); never guess another cause, and "
    "mention Settings only when the message names Settings. A harvest that skipped "
    "messages still succeeded: tell its skipped_note as written. "
    "PRIVACY: contacts stay on this computer. Answer the question asked; never dump the "
    "whole store into a reply. Old Hermes cards: cards__import_hermes imports "
    "~/.business-cards/cards.db once (safe to repeat). The switched-off hermes/business-cards "
    "Skill is the old coding-agent version these tools replace: never suggest switching it on."
)


def business_cards_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": CARDS_SKILL.model_dump(),
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "organization",
                "lifecycle": "published",
            },
            "alias": "cards",
            "selector_hint": (
                "Business cards 名片: store a card photo, find contacts, org chart 組織圖, "
                "departures 離職, email signatures 簽名檔"
            ),
            "instructions": PROCEDURE,
        }
    )
