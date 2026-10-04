"""Knowledge-first harness scenarios, with explicit evidence and gap expectations.

These are evaluation inputs, not model answers or assertions that a Vault
contains the facts. Live acceptance must inspect the resulting citations.
"""

from typing import Literal, Self

from pydantic import Field, model_validator

from common.base import Contract, Symbol, Text

KnowledgeFacet = Literal[
    "market_trend", "product_option_spec", "technical_knowledge", "competitor"
]
KnowledgeOutput = Literal["facts", "comparison", "strategy", "swot", "execution_actions"]


class KnowledgeHarnessCase(Contract):
    case_id: Symbol
    tier: Literal["standalone", "combined"]
    question: Text
    facets: tuple[KnowledgeFacet, ...] = Field(min_length=1, max_length=4)
    outputs: tuple[KnowledgeOutput, ...] = Field(min_length=1, max_length=5)
    evidence_rule: Literal["raw_citations_or_explicit_gap"] = "raw_citations_or_explicit_gap"

    @model_validator(mode="after")
    def scoped_case(self) -> Self:
        if len(self.facets) != len(set(self.facets)):
            raise ValueError("knowledge facets must be unique")
        if len(self.outputs) != len(set(self.outputs)):
            raise ValueError("knowledge outputs must be unique")
        if (self.tier == "standalone") != (len(self.facets) == 1):
            raise ValueError("standalone cases have one facet; combined cases have several")
        strategy_outputs = {"strategy", "swot", "execution_actions"}
        if strategy_outputs.intersection(self.outputs) and not {
            "market_trend", "product_option_spec", "technical_knowledge", "competitor"
        } <= set(self.facets):
            raise ValueError("strategy, SWOT and actions require all four evidence facets")
        return self


class KnowledgeHarnessSuite(Contract):
    version: Literal["1"] = "1"
    cases: tuple[KnowledgeHarnessCase, ...] = Field(min_length=5)

    @model_validator(mode="after")
    def covers_owner_scenarios(self) -> Self:
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("case IDs must be unique")
        singles = {
            case.facets[0] for case in self.cases if case.tier == "standalone"
        }
        if not {"market_trend", "product_option_spec", "technical_knowledge"} <= singles:
            raise ValueError("suite needs the three standalone information checks")
        if not any(
            case.tier == "combined" and {"strategy", "swot", "execution_actions"}
            <= set(case.outputs)
            for case in self.cases
        ):
            raise ValueError("suite needs a complete combined strategy case")
        return self
