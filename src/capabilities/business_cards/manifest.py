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
    "READING A CARD: fill name, romanised_name, company, business_group (事業群), division "
    "(處), department (部/課), title, phone, ext, mobile, fax, email, address, website, notes. "
    "Local-language name and company in name/company, the romanised form in romanised_name; "
    "never join them in one field. phone is the desk number, ext its extension, mobile the "
    "cellphone; a lone unlabelled number goes in phone and phone goes in uncertain. "
    "uncertain is the point of the format: list every field you inferred, could not read "
    "clearly or guessed (a blurred digit, glare, a department you inferred). Never guess "
    "silently; omit a field rather than invent it. Pass image_path, the attached photo's "
    "path as listed. EVERY SCAN IS KEPT: a re-scan adds an observation and updates the "
    "person; values the person set themselves are never overwritten (they become proposals). "
    "REPORTING BACK: short (it is often read on a phone in Telegram; no tables, no field "
    "you did not read). Confirm company / name / department / title / numbers in one "
    "block. If uncertain is non-empty, ask about exactly those fields and nothing else, "
    "one per line. If "
    "the person was already on file (existed true), lead with the change: the result's "
    "summary, e.g. '上次是研發部經理, 現在是協理'. Mention kept values (user_set: their own "
    "value was kept). Corrections the person gives go to cards__edit_person. "
    "ORG CHART: cards__org_chart draws the PNG and returns a legend; include the legend "
    "Markdown in your answer. Say what the chart is every time: boxes group by business "
    "group / division / department and order by title seniority; only drawn lines are "
    "reporting lines (solid = evidenced, dashed = inferred). Without evidenced lines it is "
    "NOT a reporting chart. Record a reporting line only with evidence "
    "(cards__set_reporting_line: signature, email_content, user) or as an explicit "
    "title_inference, which is drawn dashed. "
    "DEPARTURES: only when the person says someone left: cards__set_status status left, "
    "reason, said_by = the person, effective_date if they gave one. Tell them it is recorded "
    "and can be undone (cards__undo with the change_id, or set_status active). Never infer "
    "a departure yourself. "
    "EMAIL SIGNATURES: cards__harvest_signatures reads mail from one company domain within "
    "the mail scope the person set in Settings and stores nothing; show the candidates and "
    "store the ones the person confirms with cards__add_from_signature. "
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
