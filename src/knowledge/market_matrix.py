"""Read-only product/market evidence discovery over current Raw sections.

Lexical co-mentions are leads for investigation, never market-fit claims.
"""

import re
from typing import Literal, Self

from pydantic import Field, model_validator

from common.assets import AssetIdentity
from common.base import Contract, Text
from common.execution import TraceIdentifiers
from knowledge.contracts import KnowledgeSource
from knowledge.raw import RawIndex, load_document
from knowledge.vault import Vault, VaultError

ProductFamily = Literal[
    "nonsignaling_wireless",
    "signaling_wireless",
    "signal_generation_analysis",
    "vector_network_analysis",
    "oscilloscope",
]
TargetMarket = Literal[
    "wireless_communications", "aerospace_defense", "automotive", "ai_server", "semiconductor"
]
EvidenceFacet = Literal["same_section", "product", "market"]
EvidenceLevel = Literal["nearby_mention", "separate_passages", "no_raw_match"]
EvidenceNeedFacet = Literal["market_requirements", "product_options", "customer_use_case"]

PRODUCT_FAMILIES: tuple[tuple[ProductFamily, str, tuple[str, ...]], ...] = (
    ("nonsignaling_wireless", "Nonsignaling wireless testers", ("CMP180", "CMP200", "CMW100")),
    ("signaling_wireless", "Signaling wireless testers", ("CMX500", "CMW500")),
    ("signal_generation_analysis", "Signal generators / analyzers", ("FSW", "SMB")),
    ("vector_network_analysis", "Vector network analyzers", ("ZNA3000", "ZNB")),
    ("oscilloscope", "Oscilloscopes", ("MXO", "RTO5", "RTO6")),
)
TARGET_MARKETS: tuple[tuple[TargetMarket, str, tuple[str, ...]], ...] = (
    (
        "wireless_communications", "Wireless communications",
        ("wireless", "5G", "6G", "Wi-Fi", "WLAN", "Bluetooth", "cellular", "無線", "通訊"),
    ),
    (
        "aerospace_defense", "Aerospace / defense",
        ("aerospace", "defense", "defence", "radar", "satellite", "航太", "國防", "雷達"),
    ),
    (
        "automotive", "Automotive",
        ("automotive", "vehicle", "V2X", "ADAS", "汽車", "車用"),
    ),
    (
        "ai_server", "AI server",
        ("AI server", "AI data center", "AI datacenter", "GPU server", "AI伺服器", "AI資料中心"),
    ),
    (
        "semiconductor", "Semiconductor",
        ("semiconductor", "wafer", "foundry", "chiplet", "IC test", "半導體", "晶圓"),
    ),
)

PRODUCT_QUESTIONS: dict[ProductFamily, str] = {
    "nonsignaling_wireless": (
        "Which CMP/CMW variant, RF bands, channel paths and licensed test options are required?"
    ),
    "signaling_wireless": (
        "Which CMX/CMW variant, network-emulation releases, bands and option codes are required?"
    ),
    "signal_generation_analysis": (
        "Which generator/analyzer frequency, bandwidth, phase noise and modulation "
        "options are required?"
    ),
    "vector_network_analysis": (
        "Which VNA frequency range, port count, dynamic range, fixtures and "
        "analysis options are required?"
    ),
    "oscilloscope": (
        "Which oscilloscope bandwidth, sample rate, probes and protocol-analysis "
        "options are required?"
    ),
}
MARKET_QUESTIONS: dict[TargetMarket, str] = {
    "wireless_communications": (
        "Which radio standard, band, waveform, RF metric and production/validation stage matter?"
    ),
    "aerospace_defense": (
        "Which radar/satellite waveform, frequency, power and qualification requirements matter?"
    ),
    "automotive": (
        "Which connectivity, V2X, radar or in-vehicle standard and test stage matter?"
    ),
    "ai_server": (
        "Which AI-server interconnect, signal/power-integrity metric and data rate matter?"
    ),
    "semiconductor": (
        "Which device, wafer/package stage, RF/high-speed-I/O metric and probe interface matter?"
    ),
}


class MarketMatrixRequest(Contract):
    asset: AssetIdentity


class MatrixEvidence(Contract):
    facet: EvidenceFacet
    source: KnowledgeSource
    raw_ref: Text
    section: int = Field(ge=1, strict=True)
    page: int | None = Field(default=None, ge=1, strict=True)
    slide: int | None = Field(default=None, ge=1, strict=True)
    excerpt: Text


class MatrixCell(Contract):
    product_family: ProductFamily
    market: TargetMarket
    evidence_level: EvidenceLevel
    evidence: tuple[MatrixEvidence, ...] = Field(max_length=2)
    knowledge_gaps: tuple[Text, Text, Text]
    market_fit_verified: Literal[False] = False

    @model_validator(mode="after")
    def honest_evidence_level(self) -> Self:
        facets = tuple(item.facet for item in self.evidence)
        expected = {
            "nearby_mention": ("same_section",),
            "separate_passages": ("product", "market"),
            "no_raw_match": (),
        }[self.evidence_level]
        if facets != expected:
            raise ValueError("matrix evidence does not match its discovery level")
        return self


class MarketMatrixRecord(Contract):
    asset: AssetIdentity
    trace: TraceIdentifiers
    cells: tuple[MatrixCell, ...] = Field(min_length=25, max_length=25)

    @model_validator(mode="after")
    def complete_ordered_matrix(self) -> Self:
        expected = tuple(
            (row[0], market[0]) for row in PRODUCT_FAMILIES for market in TARGET_MARKETS
        )
        actual = tuple((cell.product_family, cell.market) for cell in self.cells)
        if actual != expected:
            raise ValueError("matrix must contain the canonical 5 by 5 grid")
        return self


class EvidenceNeed(Contract):
    facet: EvidenceNeedFacet
    question: Text


class MarketCellSufficiency(Contract):
    """A discovery cell is an explicit evidence gap, never a fit verdict.

    The matrix only finds nearby words or separate passages. Later retrieval
    and claim validation may produce stronger records, but cannot promote this
    discovery record by changing its status.
    """

    asset: AssetIdentity
    trace: TraceIdentifiers
    product_family: ProductFamily
    market: TargetMarket
    status: Literal["needs_evidence"] = "needs_evidence"
    discovery_level: EvidenceLevel
    discovery_evidence: tuple[MatrixEvidence, ...] = Field(max_length=2)
    missing_evidence: tuple[EvidenceNeed, EvidenceNeed, EvidenceNeed]

    @model_validator(mode="after")
    def discovery_never_completes_evidence(self) -> Self:
        expected_evidence = {
            "nearby_mention": ("same_section",),
            "separate_passages": ("product", "market"),
            "no_raw_match": (),
        }[self.discovery_level]
        if tuple(item.facet for item in self.discovery_evidence) != expected_evidence:
            raise ValueError("discovery evidence does not match its level")
        if tuple(item.facet for item in self.missing_evidence) != (
            "market_requirements", "product_options", "customer_use_case"
        ):
            raise ValueError("all three evidence needs must remain explicit")
        return self


def assess_market_cell(
    record: MarketMatrixRecord, product_family: ProductFamily, market: TargetMarket
) -> MarketCellSufficiency:
    """Return the exact unresolved evidence for a selected discovery cell."""
    cell = next(
        (
            item
            for item in record.cells
            if item.product_family == product_family and item.market == market
        ),
        None,
    )
    if cell is None:
        raise ValueError("selected market cell is not in the matrix")
    return MarketCellSufficiency(
        asset=record.asset,
        trace=record.trace,
        product_family=product_family,
        market=market,
        discovery_level=cell.evidence_level,
        discovery_evidence=cell.evidence,
        missing_evidence=(
            EvidenceNeed(facet="market_requirements", question=cell.knowledge_gaps[0]),
            EvidenceNeed(facet="product_options", question=cell.knowledge_gaps[1]),
            EvidenceNeed(facet="customer_use_case", question=cell.knowledge_gaps[2]),
        ),
    )


def _pattern(aliases: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(
        r"(?<![A-Za-z0-9])(?:"
        + "|".join(re.escape(alias) for alias in aliases)
        + r")(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


_PRODUCT_PATTERNS = (
    _pattern(PRODUCT_FAMILIES[0][2]),
    _pattern(PRODUCT_FAMILIES[1][2]),
    re.compile(
        r"(?<![A-Za-z0-9])(?:FSWP?\d{0,3}|SMB(?:V)?\d{0,4}[A-Z]?|SMW\d{2,4}[A-Z]?)(?![A-Za-z0-9])",
        re.IGNORECASE,
    ),
    re.compile(r"(?<![A-Za-z0-9])(?:ZNA|ZNB)\d{0,4}(?![A-Za-z0-9])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9])(?:MXO\s*[0-9]?|RTO[56])(?![A-Za-z0-9])", re.IGNORECASE),
)
_MARKET_PATTERNS = tuple(_pattern(market[2]) for market in TARGET_MARKETS)


def _excerpt(text: str, match: re.Match[str], other: re.Match[str] | None = None) -> str:
    start = max(0, min(match.start(), other.start() if other else match.start()) - 80)
    end = min(len(text), max(match.end(), other.end() if other else match.end()) + 120)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def _nearby(
    text: str, product: re.Pattern[str], market: re.Pattern[str]
) -> tuple[re.Match[str], re.Match[str]] | None:
    """Return the product mention in the closest bounded pair of mentions."""
    products = tuple(product.finditer(text))
    markets = tuple(market.finditer(text))
    candidates = (
        (abs(p.start() - m.start()), p, m)
        for p in products
        for m in markets
        if abs(p.start() - m.start()) <= 350
    )
    closest = min(candidates, key=lambda pair: pair[0], default=None)
    return None if closest is None else (closest[1], closest[2])


def _evidence(
    facet: EvidenceFacet,
    match: re.Match[str],
    source: KnowledgeSource,
    raw_ref: str,
    section_number: int,
    section_text: str,
    page: int | None,
    slide: int | None,
    other: re.Match[str] | None = None,
) -> MatrixEvidence:
    return MatrixEvidence(
        facet=facet,
        source=source,
        raw_ref=raw_ref,
        section=section_number,
        page=page,
        slide=slide,
        excerpt=_excerpt(section_text, match, other),
    )


def discover_market_matrix(
    asset: AssetIdentity, trace: TraceIdentifiers, vault: Vault
) -> MarketMatrixRecord:
    """Inspect each active Raw section once; never infer suitability from words."""
    joint: dict[tuple[int, int], MatrixEvidence] = {}
    product_only: dict[int, MatrixEvidence] = {}
    market_only: dict[int, MatrixEvidence] = {}
    index = RawIndex.scan(vault)
    superseded = {entry.supersedes for entry in index.entries if entry.supersedes is not None}
    for entry in index.entries:
        if entry.source.source_id in superseded:
            continue
        try:
            document = load_document(vault, entry)
        except (ValueError, UnicodeDecodeError, VaultError):
            continue
        for section_number, section in enumerate(document.sections, 1):
            if not section.text.strip():
                continue
            products = [pattern.search(section.text) for pattern in _PRODUCT_PATTERNS]
            markets = [pattern.search(section.text) for pattern in _MARKET_PATTERNS]

            for row, product_match in enumerate(products):
                if product_match is None:
                    continue
                product_only.setdefault(
                    row,
                    _evidence(
                        "product", product_match, document.source, entry.raw_ref,
                        section_number, section.text, section.page, section.slide,
                    ),
                )
                for column, market_match in enumerate(markets):
                    if market_match is not None and (
                        nearby := _nearby(
                            section.text, _PRODUCT_PATTERNS[row], _MARKET_PATTERNS[column]
                        )
                    ) is not None:
                        joint.setdefault(
                            (row, column),
                            _evidence(
                                "same_section", nearby[0], document.source, entry.raw_ref,
                                section_number, section.text, section.page,
                                section.slide, nearby[1],
                            ),
                        )
            for column, market_match in enumerate(markets):
                if market_match is not None:
                    market_only.setdefault(
                        column,
                        _evidence(
                            "market", market_match, document.source, entry.raw_ref,
                            section_number, section.text, section.page, section.slide,
                        ),
                    )
    cells: list[MatrixCell] = []
    for row, (family, _family_label, _products) in enumerate(PRODUCT_FAMILIES):
        for column, (market, _market_label, _aliases) in enumerate(TARGET_MARKETS):
            citations: tuple[MatrixEvidence, ...]
            if (row, column) in joint:
                level: EvidenceLevel = "nearby_mention"
                citations = (joint[(row, column)],)
            elif row in product_only and column in market_only:
                level = "separate_passages"
                citations = (product_only[row], market_only[column])
            else:
                level = "no_raw_match"
                citations = ()
            cells.append(
                MatrixCell(
                    product_family=family,
                    market=market,
                    evidence_level=level,
                    evidence=citations,
                    knowledge_gaps=(
                        MARKET_QUESTIONS[market],
                        PRODUCT_QUESTIONS[family],
                        "Which customer/use-case evidence independently validates this exact fit?",
                    ),
                )
            )
    return MarketMatrixRecord(asset=asset, trace=trace, cells=tuple(cells))
