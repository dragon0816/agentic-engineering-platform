"""The `engineering/bi-knowledge` Skill: how the chat answers from BI cards.

No commands: the Host offers the `bi__query` tool with its schema while some
version of this Skill is switched on (`host_runtime.bi_cards_tools`).
Shipped switched on (`host_runtime.assets.shipped`), like business cards.
"""

from __future__ import annotations

from agent.skills import SkillManifest
from common.assets import AssetIdentity

BI_SKILL = AssetIdentity(namespace="engineering", name="bi-knowledge", version="1.0.0")

#: The scoped gap rule (Case A §4.7 item 9), quoted by the tests.
GAP_RULE = "在這份資料集中沒有"

PROCEDURE = (
    "BI 知識卡片 BI knowledge cards (Trend, Technology, Node, Ecosystem, Account, "
    "CustomerProduct, Application, TestSolution, Competitor, Opportunity, Signal, Concept; "
    "domains wireless / AIDC / robotics). When the person asks about markets, trends, "
    "applications, our or competitors' test solutions, customers, opportunities or gaps, "
    "call bi__query (by entity_type, text, field / value, domain; follow_links true) and "
    "answer ONLY from the cards it returns. "
    "CITE every statement with the card it came from as [卡片 <type>:<key>], using the "
    "result's `card` value, e.g. [卡片 Application:AMR 電池包 BMS 與充電驗證]. Never cite a "
    "card the result did not return, and never add facts from your own knowledge. "
    "CLAIM MODALITY: say which parts are facts on a card (事實：…) and which are your "
    "inference from several cards (推論：…). A link between cards is a fact only when the "
    "card's field holds it; never infer a link from body text. "
    "TRUST: every card has trusted false unless a person verified it; synthetic cards are "
    "example data (範例資料). When trusted is false say the data is 待驗證 / 範例資料; "
    "never present it as verified. "
    "GAPS: a gap answer is scoped to the dataset: say 「在這份資料集中沒有…」 (e.g. "
    "「在這份資料集中沒有我方的 BMS 測試方案」), never that something does not exist in "
    "the world or in the market. Our own solution = a TestSolution whose vendor is empty; "
    "a competitor's has vendor set. "
    "WHOLE-DATASET QUESTIONS (which applications lack our solution, trends with no "
    "solution, demand with no opportunity, our solutions with no active opportunity, the "
    "funnel, technologies without a Concept, incomplete customer products): call bi__query "
    "with `analysis` (gaps, trend_coverage, demand_without_opportunity, "
    "solutions_vs_opportunities, funnel, technologies_without_concept, "
    "product_completeness) and the domain, and list EVERY flagged row it returns, citing "
    "each row's card `cite` value as [卡片 <cite>]; a search alone can miss cards. "
    "PRIORITY: priority is never stored (owner decision #222). When asked which "
    "application, trend or opportunity matters most, judge it yourself from the facts on "
    "the cards (Trend measurement_impact × our_fit, time_to_demand and stage; customer "
    "products and their launch dates; opportunities and their deal_stage; whether we "
    "have an available solution and whether competitors do) and say plainly that this "
    "ranking is your judgement from those facts (優先度是我依卡片事實判斷的，不是資料欄位). "
    "Keep answers short; name fields in Chinese; quote the result's scope_note when "
    "nothing matched. BI data is internal: answer the person, never paste the whole "
    "dataset."
)


def bi_knowledge_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": BI_SKILL.model_dump(),
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "organization",
                "lifecycle": "published",
            },
            "alias": "bi",
            "selector_hint": (
                "BI 知識卡片: trends 趨勢, applications 應用, test solutions 測試方案, "
                "competitors 競品, customers 客戶, opportunities 商機, gaps 缺口"
            ),
            "instructions": PROCEDURE,
        }
    )
