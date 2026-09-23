"""The chipset report's rules as data, typed.

The source kept this as an unvalidated dictionary read straight from
`config/chipset-map.json`, with every lookup carrying its own inline default.
A misspelt key therefore reverted to a code default silently, and five keys
in the shipped example were read by nothing at all.

Here the same file loads into a closed contract. What it declares is what the
rules read; a key it does not declare is a refusal, except for the two kinds
this loader forgives by name: documentation keys, which the source's own file
uses for its comments, and the keys that source read nowhere, which are named
in `IGNORED` so that ignoring them is a decision somebody wrote down rather
than a silence.

The file's own spelling is kept, because the file this loads is the one the
team already has on the company machine.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError, field_validator

from common.base import Contract

#: Keys the source file carries that its own code read nowhere. Ignored by
#: name rather than silently, so that a key which starts being read is a
#: change to this list and not a surprise.
IGNORED: frozenset[str] = frozenset(
    {"version", "keepCompositionTogether", "lineSeparator", "sharedPrefixExpansion"}
)

#: Where the shipped ruleset lives. It is the source's example file, which is
#: also the file the source actually ran with, since the real one is not in
#: the pinned tree. A host points at its own.
DEFAULT_RULESET = Path(__file__).with_name("chipset_map.json")


class RulesetError(Exception):
    """The ruleset could not be read.

    The code says what went wrong and `where` says which key, because the
    file is hundreds of lines long and bisecting it by hand is the failure
    this class exists to prevent. No value is ever carried: the names are
    the team's own vendors, brands and chipsets.
    """

    def __init__(self, code: str, where: str = "") -> None:
        self.code = code
        self.where = where
        super().__init__(f"{code} at {where}" if where else code)


class SplitRules(Contract):
    """How a free-text `Chipset models` cell is cut apart."""

    #: Competing options for the same technology: each becomes its own row.
    alternative_separators: tuple[str, ...] = ("/", ",")
    #: Dies of one solution: kept together in one chipset string.
    composition_separators: tuple[str, ...] = ("+",)
    #: A different technology: its own row, and never composed back together.
    group_separators: tuple[str, ...] = (",",)
    compose_same_vendor_lines: bool = True
    noise_tokens: tuple[str, ...] = ()
    filler_words: tuple[str, ...] = ()
    role_words: tuple[str, ...] = ()
    multiplicity_suffix: str = r"\s*[*x]\s*\d+\s*$"
    drop_placeholders: bool = True
    drop_vendor_only: bool = True


class PrefixRule(Contract):
    pattern: str
    vendor: str


class VendorRules(Contract):
    #: Output row order. A vendor not named here sorts last.
    canonical_order: tuple[str, ...] = ()
    #: Literal vendor words: they set the vendor, are dropped from the match
    #: key, and stay in the displayed name.
    name_tokens: dict[str, str] = {}
    #: Model-number prefixes, tried in order, first match winning.
    prefix_rules: tuple[PrefixRule, ...] = ()


class ChipsetAlias(Contract):
    pattern: str
    replace: str


class ChipsetTechRule(Contract):
    pattern: str
    technologies: tuple[str, ...]


class TechnologyRules(Contract):
    #: The only values the Technology column may hold, and the order they are
    #: emitted in.
    canonical: tuple[str, ...] = ()
    unresolved: str = "TBD"
    keywords: dict[str, tuple[str, ...]] = {}
    #: Generation labels for the audit column; never the Technology column.
    detail_keywords: dict[str, tuple[str, ...]] = {}
    chipset_rules: tuple[ChipsetTechRule, ...] = ()


class CompanyRules(Contract):
    """One of `brand` or `mfg`."""

    #: Whole-cell overrides, for cells where a newline is part of one name.
    line_joins: dict[str, tuple[str, ...]] = {}
    aliases: dict[str, str] = {}
    drop_tokens: tuple[str, ...] = ()


class PriorityRules(Contract):
    map: dict[str, str] = {}
    rank: dict[str, int] = {}
    unknown: str = ""


class StatusRules(Contract):
    exclude_by_default: tuple[str, ...] = ("lost",)
    new_row_status: str = "Not Start"


class DriRules(Contract):
    by_technology: dict[str, str] = {}
    by_vendor: dict[str, str] = {}
    fallback: str = "TBD"


class Colours(Contract):
    header: str = "#D9D9D9"
    new: str = "#FFF2CC"
    tracked: str = "#E2EFDA"
    partial: str = "#DDEBF7"
    unresolved: str = "#FCE4D6"
    changed: str = "#FFC7CE"


#: What is watched when a ruleset says nothing, or says it with an empty
#: list. The two columns sales edit by hand.
DEFAULT_WATCH_FIELDS: tuple[str, ...] = ("Purchased Schedule", "Protential Biz")


class OutputRules(Contract):
    vendor_display: str = "every"
    unknown_biz_marker: str = "?"
    schedule_format: str = "%b. %Y"
    company_join: str = "\n"
    trace_prefix: str = "[W1-TRACE"
    colors: Colours = Colours()
    #: The columns whose change is worth pointing at on a row already
    #: tracked. A statement about how the team works, not about the code.
    #: An empty list means the usual two rather than none of them: the
    #: source read it that way, and a watch list that silently covers
    #: nothing is the failure `watched_but_missing` exists to make audible.
    watch_fields: tuple[str, ...] = DEFAULT_WATCH_FIELDS

    @field_validator("watch_fields")
    @classmethod
    def _at_least_the_usual_two(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return value or DEFAULT_WATCH_FIELDS


class ChipsetRuleset(Contract):
    """Everything the chipset report knows that is not code."""

    split: SplitRules = SplitRules()
    vendors: VendorRules = VendorRules()
    chipset_aliases: tuple[ChipsetAlias, ...] = ()
    technology: TechnologyRules = TechnologyRules()
    brand: CompanyRules = CompanyRules()
    mfg: CompanyRules = CompanyRules()
    priority: PriorityRules = PriorityRules()
    status: StatusRules = StatusRules()
    dri: DriRules = DriRules()
    output: OutputRules = OutputRules()


# ---------------------------------------------------------------------------
# Reading the file the team already has
# ---------------------------------------------------------------------------

_SPLIT_KEYS = {
    "alternativeSeparators": "alternative_separators",
    "compositionSeparators": "composition_separators",
    "groupSeparators": "group_separators",
    "composeSameVendorLines": "compose_same_vendor_lines",
    "noiseTokens": "noise_tokens",
    "fillerWords": "filler_words",
    "roleWords": "role_words",
    "multiplicitySuffix": "multiplicity_suffix",
    "dropPlaceholders": "drop_placeholders",
    "dropVendorOnly": "drop_vendor_only",
}
_VENDOR_KEYS = {
    "canonicalOrder": "canonical_order",
    "nameTokens": "name_tokens",
    "prefixRules": "prefix_rules",
}
_TECH_KEYS = {
    "canonical": "canonical",
    "unresolved": "unresolved",
    "keywords": "keywords",
    "detailKeywords": "detail_keywords",
    "chipsetRules": "chipset_rules",
}
_COMPANY_KEYS = {
    "lineJoins": "line_joins",
    "aliases": "aliases",
    "dropTokens": "drop_tokens",
}
_PRIORITY_KEYS = {"map": "map", "rank": "rank", "unknown": "unknown"}
_STATUS_KEYS = {"excludeByDefault": "exclude_by_default", "newRowStatus": "new_row_status"}
_DRI_KEYS = {"byTechnology": "by_technology", "byVendor": "by_vendor", "fallback": "fallback"}
_OUTPUT_KEYS = {
    "vendorDisplay": "vendor_display",
    "unknownBizMarker": "unknown_biz_marker",
    "scheduleFormat": "schedule_format",
    "companyJoin": "company_join",
    "tracePrefix": "trace_prefix",
    "colors": "colors",
    "watchFields": "watch_fields",
}
_TOP_KEYS = {
    "split": ("split", _SPLIT_KEYS),
    "vendors": ("vendors", _VENDOR_KEYS),
    "technology": ("technology", _TECH_KEYS),
    "brand": ("brand", _COMPANY_KEYS),
    "mfg": ("mfg", _COMPANY_KEYS),
    "priority": ("priority", _PRIORITY_KEYS),
    "status": ("status", _STATUS_KEYS),
    "dri": ("dri", _DRI_KEYS),
    "output": ("output", _OUTPUT_KEYS),
}


def _documentation(key: str) -> bool:
    """The source's file carries its reasoning in keys beginning with an
    underscore. They are prose, and prose is not a rule."""
    return key.startswith("_")


def _section(name: str, value: Any, keys: Mapping[str, str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RulesetError("section_not_an_object", name)
    out: dict[str, Any] = {}
    for key, item in value.items():
        if _documentation(key) or key in IGNORED:
            continue
        if key not in keys:
            raise RulesetError("unknown_key", f"{name}.{key}")
        out[keys[key]] = item
    return out


def _entries(value: Any) -> list[dict[str, Any]]:
    """A list of rule objects, with each object's own documentation keys
    dropped. The source skipped an entry with no `pattern`; a typed ruleset
    refuses it instead, because an entry that does nothing is a rule somebody
    believes is in force."""
    if not isinstance(value, list):
        raise RulesetError("rules_not_a_list")
    entries: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            # The source skipped these. A stray `null` among the aliases
            # would stop `MTK7925` becoming `MT7925`, and every row that used
            # to match would arrive as new, with nothing anywhere saying why.
            raise RulesetError("rule_not_an_object")
        entries.append({k: v for k, v in item.items() if not _documentation(k)})
    return entries


def ruleset_from_mapping(data: Mapping[str, Any]) -> ChipsetRuleset:
    """Read the source's own `chipset-map.json` shape."""
    if not isinstance(data, dict):
        raise RulesetError("ruleset_not_an_object")
    fields: dict[str, Any] = {}
    for key, value in data.items():
        if _documentation(key) or key in IGNORED:
            continue
        if key == "chipsetAliases":
            fields["chipset_aliases"] = _entries(value)
            continue
        if key not in _TOP_KEYS:
            raise RulesetError("unknown_key", key)
        name, keys = _TOP_KEYS[key]
        section = _section(key, value, keys)
        if key == "vendors" and "prefix_rules" in section:
            section["prefix_rules"] = _entries(section["prefix_rules"])
        if key == "technology" and "chipset_rules" in section:
            section["chipset_rules"] = _entries(section["chipset_rules"])
        if key == "output" and isinstance(section.get("colors"), dict):
            section["colors"] = {
                k: v for k, v in section["colors"].items() if not _documentation(k)
            }
        fields[name] = section
    try:
        return ChipsetRuleset.model_validate(fields)
    except ValidationError as invalid:
        # The field path, never the value: the contract already hides inputs
        # and these are the team's own vendors and brands.
        first = invalid.errors()[0]
        where = ".".join(str(part) for part in first.get("loc", ()))
        raise RulesetError("ruleset_invalid", where) from None


def load_ruleset(path: str | Path | None = None) -> ChipsetRuleset:
    """The ruleset at `path`, or the one this package ships."""
    target = Path(path) if path else DEFAULT_RULESET
    try:
        # `utf-8-sig` because a ruleset edited in Excel or Notepad on a
        # Windows machine arrives with a byte order mark, and refusing it as
        # unreadable would be a puzzle rather than a message.
        text = target.read_text(encoding="utf-8-sig")
    except OSError:
        raise RulesetError("ruleset_missing") from None
    except UnicodeDecodeError:
        raise RulesetError("ruleset_unreadable") from None
    try:
        data = json.loads(text)
    except ValueError:
        raise RulesetError("ruleset_unreadable") from None
    return ruleset_from_mapping(data)


# ---------------------------------------------------------------------------
# Compiled once, read many times
# ---------------------------------------------------------------------------


def keyword_pattern(word: str) -> re.Pattern[str]:
    """A keyword that may be written with a space or a hyphen, or neither.

    One entry `wi-fi` therefore matches `wifi`, `wi fi` and `wi-fi`. The
    boundary is "not next to an alphanumeric" rather than `\\b`, so `5g` does
    not match inside `5gnr`.

    The source built this with two chained replacements, the second of which
    rewrote what the first had just inserted, leaving a character class that
    also matched `wi[fi` and `wi]fi`. Fixed here: it only ever removed
    matches that should not have happened.
    """
    escaped = re.escape(word)
    flexible = re.sub(r"\\[ -]", r"[\\s\\-]?", escaped)
    return re.compile(rf"(?<![0-9a-z]){flexible}(?![0-9a-z])", re.IGNORECASE)


@dataclass(frozen=True)
class Rules:
    """A ruleset with its patterns compiled. The rules take this, never the
    contract, so nothing recompiles a regular expression per cell."""

    ruleset: ChipsetRuleset
    noise: frozenset[str] = frozenset()
    fillers: frozenset[str] = frozenset()
    roles: frozenset[str] = frozenset()
    vendor_tokens: Mapping[str, str] = field(default_factory=dict)
    vendor_prefixes: Sequence[tuple[re.Pattern[str], str]] = ()
    chipset_aliases: Sequence[tuple[re.Pattern[str], str]] = ()
    tech_keywords: Sequence[tuple[re.Pattern[str], str]] = ()
    tech_details: Sequence[tuple[re.Pattern[str], str]] = ()
    tech_chipsets: Sequence[tuple[re.Pattern[str], tuple[str, ...]]] = ()
    multiplicity: re.Pattern[str] = re.compile(r"\s*[*x]\s*\d+\s*$", re.IGNORECASE)

    # -- the parts read straight off the ruleset ------------------------

    @property
    def canonical_techs(self) -> tuple[str, ...]:
        return self.ruleset.technology.canonical

    @property
    def unresolved(self) -> str:
        return self.ruleset.technology.unresolved

    @property
    def vendor_order(self) -> tuple[str, ...]:
        return self.ruleset.vendors.canonical_order

    @property
    def output(self) -> OutputRules:
        return self.ruleset.output

    @property
    def colours(self) -> Colours:
        return self.ruleset.output.colors

    @property
    def watch_fields(self) -> tuple[str, ...]:
        return self.ruleset.output.watch_fields


def compile_rules(ruleset: ChipsetRuleset) -> Rules:
    """Compile a ruleset once.

    Longest keyword first within a group, as the source did, so that `wi-fi 7`
    is tried before `wi-fi`. Everything else keeps the file's own order,
    because order is how several of these rules decide.
    """
    keywords: list[tuple[re.Pattern[str], str]] = []
    for canon, words in ruleset.technology.keywords.items():
        for word in sorted(words, key=len, reverse=True):
            keywords.append((keyword_pattern(word), canon))
    details: list[tuple[re.Pattern[str], str]] = []
    for detail, words in ruleset.technology.detail_keywords.items():
        for word in sorted(words, key=len, reverse=True):
            details.append((keyword_pattern(word), detail))
    try:
        return Rules(
            ruleset=ruleset,
            noise=frozenset(t.strip().lower() for t in ruleset.split.noise_tokens),
            fillers=frozenset(t.strip().lower() for t in ruleset.split.filler_words),
            roles=frozenset(t.strip().lower() for t in ruleset.split.role_words),
            vendor_tokens={k.lower(): v for k, v in ruleset.vendors.name_tokens.items()},
            vendor_prefixes=tuple(
                (re.compile(rule.pattern, re.IGNORECASE), rule.vendor)
                for rule in ruleset.vendors.prefix_rules
            ),
            chipset_aliases=tuple(
                (re.compile(alias.pattern, re.IGNORECASE), alias.replace)
                for alias in ruleset.chipset_aliases
            ),
            tech_keywords=tuple(keywords),
            tech_details=tuple(details),
            tech_chipsets=tuple(
                (re.compile(rule.pattern, re.IGNORECASE), rule.technologies)
                for rule in ruleset.technology.chipset_rules
            ),
            multiplicity=re.compile(ruleset.split.multiplicity_suffix, re.IGNORECASE),
        )
    except re.error:
        raise RulesetError("pattern_invalid") from None


def default_rules() -> Rules:
    """The shipped ruleset, compiled."""
    return compile_rules(load_ruleset())
