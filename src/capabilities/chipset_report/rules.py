"""The chipset report's transformation, pure.

Ported from the pinned source's `_chipset_rules.py` with its own tests as the
oracle. The specification is the source's `docs/W1_MAPPING.md`, which every
rule here answers to; where this module and that document disagree, the
document is right.

Nothing here reads a file, a clock or the environment. The ruleset arrives
compiled and the date arrives as an argument, so the same inputs always
produce the same output — which is what makes a plan worth comparing against
the old job's.

`docs/PHASE_7_MIGRATION.md`, "Workflow 10" lists the defects found in the
source and says, for each, whether this port keeps it or fixes it. The ones
kept are marked **preserved** where they live, so that nobody fixes one by
accident and makes a failed comparison unattributable.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from capabilities.chipset_report.ruleset import Rules

#: The headers used only when the target sheet cannot be read at all. The
#: real ones are read from the workbook every run, so the written sheet
#: mirrors it, including the two spellings the workbook itself has wrong.
FALLBACK_TARGET_HEADERS: tuple[str, ...] = (
    "Chipset Vendor",
    "chipset",
    "Technology",
    "Brand",
    "MFG",
    "Protential Biz",
    "Purchased Schedule",
    "Piority ",
    "DRI",
    "Status",
    "Comments",
)

#: Audit columns appended after the managed ones.
TRACE_HEADERS: tuple[str, ...] = (
    "_Match",
    "_Changed",
    "_MatchedRow",
    "_SourceFY",
    "_SourceProjects",
    "_SourceOPPIDs",
    "_SourceRows",
    "_RawChipsetText",
    "_TechDetail",
    "_Warnings",
)

#: The warning that decides a row's colour. Written once and read in both
#: places, because the source repeated the literal in two files.
UNRESOLVED_TECHNOLOGY = "technology could not be resolved"
INFERRED_TECHNOLOGY = "technology inferred from End-Products/Purpose/Project Name"

MATCH_LEVELS: tuple[str, ...] = ("tracked", "tracked-other-tech", "partial", "new")

_MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_MONTHS = {name.lower(): number for number, name in enumerate(_MONTH_NAMES, start=1)}

_MONTH_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*[,\-/]?\s*(\d{2,4})\b",
    re.IGNORECASE,
)
_QUARTER_RE = re.compile(r"\bQ([1-4])\s*[-/,]?\s*(\d{2,4})\b", re.IGNORECASE)
_YEARMON_RE = re.compile(r"\b(20\d{2})\s*[/\-.]\s*(\d{1,2})\b")


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------


def clean_text(value: Any) -> str:
    """Any cell value as the trimmed text it means.

    Newlines survive, because in these columns a newline carries meaning:
    several companies, or several dies of one solution. Runs of spaces, tabs
    and non-breaking spaces do not.
    """
    if value is None:
        return ""
    if isinstance(value, _dt.datetime | _dt.date):
        return value.strftime("%Y/%m/%d")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def is_noise(text: str, rules: Rules) -> bool:
    """Whether this text means "not decided" rather than a chipset."""
    stripped = text.strip().lower().strip(".:;,")
    if not stripped:
        return True
    return stripped in rules.noise


def header_key(name: Any) -> str:
    """The comparison key for a column name: case, spacing and punctuation
    folded, **spelling not**. The workbook says `Protential Biz`, so a rule
    that says `Potential Biz` names no column at all, which is why
    `watched_but_missing` exists."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def one_line(text: str) -> str:
    """Newlines collapsed, so one trace record occupies one line."""
    return re.sub(r"\s*\n+\s*", " / ", text).strip()


# ---------------------------------------------------------------------------
# Technology
# ---------------------------------------------------------------------------


def find_technologies(text: str, rules: Rules) -> list[str]:
    """Every canonical technology named anywhere in the text, in canonical
    order. A keyword group whose name is not canonical can never reach the
    output, which is the ruleset's whitelist doing its job."""
    if not text:
        return []
    found: set[str] = set()
    for pattern, canon in rules.tech_keywords:
        if pattern.search(text):
            found.add(canon)
    return [tech for tech in rules.canonical_techs if tech in found]


def find_tech_details(text: str, rules: Rules) -> list[str]:
    """Generation labels for the audit column: `wifi7`, `bt6`, `5g`. Never
    the Technology column, which holds kinds and not generations."""
    if not text:
        return []
    out: list[str] = []
    for pattern, detail in rules.tech_details:
        if pattern.search(text) and detail not in out:
            out.append(detail)
    return out


def technologies_from_chipset(name: str, rules: Rules) -> list[str]:
    """What the model number itself says. The whole string is tried first,
    then each die of a composition, first rule winning in both passes."""
    for pattern, techs in rules.tech_chipsets:
        if pattern.search(name):
            return list(techs)
    found: list[str] = []
    for token in re.split(r"[\s+/,]+", name):
        token = token.strip("()[],.;:")
        if not token:
            continue
        for pattern, techs in rules.tech_chipsets:
            if pattern.search(token):
                for tech in techs:
                    if tech not in found:
                        found.append(tech)
                break
    return found


def order_technologies(techs: Iterable[str], rules: Rules) -> list[str]:
    """Canonical order first, then anything else in the order it was seen.

    The source iterated a set for the second half, so its output varied
    between processes. Nothing in the shipped ruleset reaches that half, and
    a plan that differs run to run is not evidence.
    """
    seen: list[str] = []
    for tech in techs:
        if tech not in seen:
            seen.append(tech)
    canonical = [tech for tech in rules.canonical_techs if tech in seen]
    return canonical + [tech for tech in seen if tech not in rules.canonical_techs]


# ---------------------------------------------------------------------------
# The chipset cell
# ---------------------------------------------------------------------------


@dataclass
class ChipsetToken:
    """One chipset read out of a `Chipset models` cell."""

    display: str
    raw_line: str = ""
    #: Set by an explicit `<tech>:` label or a technology parenthesis.
    tech_hint: list[str] = field(default_factory=list)
    vendor_hint: str = ""
    unresolved: bool = False
    warnings: list[str] = field(default_factory=list)
    #: Which prepared line produced this token, and whether a blank or
    #: unparseable line precedes it. Both exist only to decide composition.
    slot: int = -1
    barrier_before: bool = False


def _strip_multiplicity(text: str, rules: Rules) -> str:
    return rules.multiplicity.sub("", text).strip()


def _apply_aliases_once(name: str, rules: Rules) -> str:
    out = name.strip()
    for pattern, replacement in rules.chipset_aliases:
        out = pattern.sub(replacement, out)
    return out


def apply_chipset_aliases(name: str, rules: Rules) -> str:
    """Normalise a chipset name, every die of it.

    `mtk7921+mtk7922` is one chipset of two dies, and aliasing only the whole
    string leaves the tail as written, which then matches no existing row.
    The separators and the spacing around them are kept exactly, because the
    existing sheet holds both `MT7977+MT7996` and `IPQ5322 SoC + QCN6412`.
    """
    separators = [sep for sep in rules.ruleset.split.composition_separators if sep]
    out = _apply_aliases_once(name, rules)
    if not separators or not any(sep in out for sep in separators):
        return out
    pattern = "(" + "|".join(re.escape(sep) for sep in separators) + ")"
    pieces = re.split(pattern, out)
    rebuilt: list[str] = []
    for index, piece in enumerate(pieces):
        if index % 2:
            rebuilt.append(piece)
            continue
        lead = piece[: len(piece) - len(piece.lstrip())]
        trail = piece[len(piece.rstrip()) :]
        rebuilt.append(f"{lead}{_apply_aliases_once(piece, rules)}{trail}")
    return "".join(rebuilt)


def split_top_level(text: str, separators: Sequence[str]) -> list[str]:
    """Split on separators outside parentheses, so `Cellular(LTE, NR)` stays
    whole. Separators are tried in order and matched without case."""
    parts: list[str] = []
    buffer: list[str] = []
    depth = 0
    index = 0
    lowered = text.lower()
    while index < len(text):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if depth == 0:
            hit = next((sep for sep in separators if lowered.startswith(sep.lower(), index)), None)
            if hit:
                parts.append("".join(buffer))
                buffer = []
                index += len(hit)
                continue
        buffer.append(char)
        index += 1
    parts.append("".join(buffer))
    return [part.strip() for part in parts if part.strip()]


def expand_shared_prefix(parts: list[str]) -> list[str]:
    """`MTK7921/7925` is two models sharing a prefix; `BCM 6726/67263` is not.

    The tail expands only when the previous part's trailing digits are at
    least as long as it is. A longer number is a whole model of its own.
    """
    out: list[str] = []
    for part in parts:
        match = re.fullmatch(r"(\d+)([A-Za-z\-]*)", part.strip())
        if match and out:
            previous = out[-1]
            prior = re.search(r"(\d+)([A-Za-z\-]*)$", previous)
            if prior and len(prior.group(1)) >= len(match.group(1)):
                head = previous[: prior.start(1) + len(prior.group(1)) - len(match.group(1))]
                out.append(head + match.group(1) + match.group(2))
                continue
        out.append(part.strip())
    return out


def _peel_leading(line: str, rules: Rules) -> tuple[str, list[str], str]:
    """Take the technology words off the front of a line and keep the vendor
    words. `Wi-Fi 7 QFW7114` is the chipset `QFW7114` with the technology
    `wifi`; `Qualcomm SDX35` keeps its vendor word, as the sheet does."""
    tokens = line.split()
    techs: list[str] = []
    vendor = ""
    kept: list[str] = []
    index = 0
    last_was_tech = False
    while index < len(tokens):
        token = tokens[index]
        bare = token.strip("()[],.;:").lower()
        if bare in rules.vendor_tokens:
            vendor = vendor or rules.vendor_tokens[bare]
            kept.append(token)
            index += 1
            last_was_tech = False
            continue
        hits = find_technologies(bare, rules)
        if hits and not re.search(r"[a-z]\d|\d[a-z]", bare):
            for hit in hits:
                if hit not in techs:
                    techs.append(hit)
            index += 1
            last_was_tech = True
            continue
        if last_was_tech and (re.fullmatch(r"\d+(\.\d+)?[a-z]?", bare) or bare in rules.fillers):
            index += 1
            continue
        break
    kept.extend(tokens[index:])
    return " ".join(kept).strip(), techs, vendor


def _strip_trailing_fillers(name: str, rules: Rules) -> str:
    tokens = name.split()
    while tokens and tokens[-1].strip("()[],.;:").lower() in rules.fillers:
        tokens.pop()
    return " ".join(tokens)


def _paren_is_tech(content: str, rules: Rules) -> bool:
    """Whether a parenthesis lists technologies or annotates a die's role.

    **Preserved defect.** The role test is a substring test, so a
    parenthesis containing `pa`, `ic`, `end`, `lna` or `fem` anywhere is read
    as a role note and stays in the displayed name. `(Japan)` contains `pa`.
    Changing it changes what the chipset column says, which the parity gate
    compares.
    """
    low = content.lower()
    if any(role in low for role in rules.roles):
        return False
    if re.search(r"\d\s*[x*]\s*\d", low):
        return False
    return bool(find_technologies(content, rules))


def _prepare_lines(text: str, rules: Rules) -> list[tuple[str, bool]]:
    """Cut a cell into the lines a chipset may be read from.

    The cell's intended shape is a list of technology groups, so a newline
    and a top-level comma both start a new one. `+` composes one solution out
    of several dies and therefore stays on its line, and a line that begins
    with `+`, or follows one that ends with it, folds into the line above.

    A comma says "different technology", so the groups it makes carry a
    barrier: the same-vendor composition below must never put them back
    together, which is what keeps `QCN-6515,QCN-6563` as two rows.
    """
    composition = list(rules.ruleset.split.composition_separators)
    groups_by = list(rules.ruleset.split.group_separators)
    out: list[tuple[str, bool]] = []
    barrier = False
    for raw in text.split("\n"):
        if not raw.strip():
            barrier = True
            continue
        groups = split_top_level(raw, groups_by) if groups_by else [raw]
        for index, group in enumerate(groups):
            line = group.strip()
            if not line:
                continue
            if out and (
                any(line.startswith(sep) for sep in composition)
                or any(out[-1][0].endswith(sep) for sep in composition)
            ):
                previous, previous_barrier = out[-1]
                out[-1] = (f"{previous} {line}".strip(), previous_barrier)
                continue
            out.append((line, barrier or index > 0))
            barrier = False
    return out


def _compose_same_vendor_lines(tokens: list[ChipsetToken], rules: Rules) -> list[ChipsetToken]:
    """Merge adjacent one-chipset lines of the same vendor into one solution.

    The existing sheet records `MT7987A(SoC) + MT7992B(BBIC) + ...` as a
    single row although the source lists the dies on separate lines. The
    discriminator is all of: adjacent lines, no blank line between them, one
    chipset on each, no explicit technology label on either, neither
    unresolved, and the same inferred vendor.
    """
    if not rules.ruleset.split.compose_same_vendor_lines:
        return tokens
    per_slot: dict[int, int] = {}
    for token in tokens:
        per_slot[token.slot] = per_slot.get(token.slot, 0) + 1

    out: list[ChipsetToken] = []
    for token in tokens:
        vendor = infer_vendor(token.display, rules, token.vendor_hint)
        previous = out[-1] if out else None
        can_merge = (
            previous is not None
            and not token.barrier_before
            and token.slot == previous.slot + 1
            and per_slot.get(token.slot) == 1
            and per_slot.get(previous.slot) == 1
            and not token.tech_hint
            and not previous.tech_hint
            and not token.unresolved
            and not previous.unresolved
            and vendor != ""
            and vendor == infer_vendor(previous.display, rules, previous.vendor_hint)
        )
        if can_merge and previous is not None:
            previous.display = f"{previous.display} + {token.display}"
            previous.raw_line = f"{previous.raw_line}\n{token.raw_line}"
            previous.slot = token.slot
            continue
        out.append(token)
    return out


def split_chipsets(raw_cell: Any, rules: Rules) -> list[ChipsetToken]:
    """Every chipset in a free-text `Chipset models` cell, never none.

    `/ ; & or` separate alternatives; `,` and a newline separate technology
    groups; `+` composes one chipset; parentheses protect their contents. A
    `<tech>:` label carries a technology, a line that is only a vendor name
    is context for the lines below it, and a line that is only a parenthesis
    annotates the chipset above it. Noise never disappears quietly: an
    unresolved placeholder is emitted with the reason.
    """
    text = clean_text(raw_cell)
    if not text:
        return [
            ChipsetToken(
                display=rules.unresolved,
                raw_line="",
                unresolved=True,
                warnings=["empty 'Chipset models' cell"],
            )
        ]

    tokens: list[ChipsetToken] = []
    pending_tech: list[str] = []
    vendor_ctx = ""
    prepared = _prepare_lines(text, rules)

    for position, (line, barrier) in enumerate(prepared):
        produced_before = len(tokens)

        standalone = re.fullmatch(r"\((.*)\)", line, re.DOTALL)
        if standalone:
            content = standalone.group(1)
            if tokens:
                if _paren_is_tech(content, rules):
                    for tech in find_technologies(content, rules):
                        if tech not in tokens[-1].tech_hint:
                            tokens[-1].tech_hint.append(tech)
                else:
                    tokens[-1].display = f"{tokens[-1].display} ({content})"
            continue

        label_tech: list[str] = []
        labelled = re.match(r"^([A-Za-z0-9 /\-\.&+]{1,32}?)\s*:\s*(.+)$", line, re.DOTALL)
        if labelled:
            label, payload = labelled.group(1), labelled.group(2).strip()
            bare_label = label.strip().lower()
            if bare_label in rules.vendor_tokens:
                vendor_ctx = rules.vendor_tokens[bare_label]
                line = payload
            else:
                hits = find_technologies(label, rules)
                if hits:
                    label_tech = hits
                    line = payload

        line, lead_tech, lead_vendor = _peel_leading(line, rules)
        techs = label_tech or lead_tech

        if not line.strip():
            if techs:
                pending_tech = techs
            if lead_vendor:
                vendor_ctx = lead_vendor
            continue

        if is_noise(line, rules):
            if len(prepared) == 1:
                tokens.append(
                    ChipsetToken(
                        display=rules.unresolved,
                        raw_line=line,
                        unresolved=True,
                        slot=position,
                        barrier_before=barrier,
                        warnings=[f"chipset text is a placeholder: {line!r}"],
                    )
                )
            continue

        bare = line.strip().lower()
        if bare in rules.vendor_tokens and position < len(prepared) - 1:
            vendor_ctx = rules.vendor_tokens[bare]
            continue

        vendor_hint = lead_vendor or vendor_ctx
        use_tech = techs or pending_tech
        pending_tech = []

        alternatives = expand_shared_prefix(
            split_top_level(line, rules.ruleset.split.alternative_separators)
        )
        for candidate in alternatives:
            part = _strip_multiplicity(candidate, rules)
            part = _strip_trailing_fillers(part, rules).strip(" ,;.-")
            if not part or is_noise(part, rules):
                continue
            part_tech = list(use_tech)
            for found in re.finditer(r"\(([^)]*)\)", part):
                if _paren_is_tech(found.group(1), rules):
                    for tech in find_technologies(found.group(1), rules):
                        if tech not in part_tech:
                            part_tech.append(tech)
                    part = part.replace(found.group(0), "").strip()
            part = re.sub(r"\s{2,}", " ", part).strip(" ,;.-")
            if not part:
                continue
            display = apply_chipset_aliases(part, rules)
            token = ChipsetToken(
                display=display,
                raw_line=line,
                tech_hint=part_tech,
                vendor_hint=vendor_hint,
                slot=position,
                barrier_before=barrier,
            )
            if not match_key(display, rules):
                vendor = infer_vendor(display, rules, vendor_hint) or display
                token.display = f"{vendor} (model TBD)"
                token.vendor_hint = vendor
                token.unresolved = True
                token.warnings.append(f"only a vendor name was given: {display!r}")
            tokens.append(token)

        if len(tokens) == produced_before and position + 1 < len(prepared):
            prepared[position + 1] = (prepared[position + 1][0], True)

    if not tokens:
        if vendor_ctx or pending_tech:
            tokens.append(
                ChipsetToken(
                    display=f"{vendor_ctx or rules.unresolved} (model TBD)",
                    raw_line=text,
                    vendor_hint=vendor_ctx,
                    tech_hint=list(pending_tech),
                    unresolved=True,
                    slot=0,
                    warnings=[f"only a vendor name was given: {text!r}"],
                )
            )
        else:
            tokens.append(
                ChipsetToken(
                    display=rules.unresolved,
                    raw_line=text,
                    unresolved=True,
                    slot=0,
                    warnings=[f"no chipset could be parsed from {text!r}"],
                )
            )
    return _compose_same_vendor_lines(tokens, rules)


# ---------------------------------------------------------------------------
# Vendor and identity
# ---------------------------------------------------------------------------


def infer_vendor(chipset: str, rules: Rules, hint: str = "") -> str:
    """The vendor of a chipset string, or nothing.

    A vendor word written in the string beats everything; then the context a
    previous line gave; then the model-number prefixes, tried whole and then
    per token.
    """
    for token in re.split(r"[\s:/,+]+", chipset):
        bare = token.strip("()[],.;:").lower()
        if bare in rules.vendor_tokens:
            return rules.vendor_tokens[bare]
    if hint:
        return hint
    probe = chipset.strip().lstrip("(")
    for pattern, vendor in rules.vendor_prefixes:
        if pattern.search(probe):
            return vendor
    for token in re.split(r"[\s+/]+", probe):
        for pattern, vendor in rules.vendor_prefixes:
            if pattern.search(token.strip("()[],.;:")):
                return vendor
    return ""


def match_key(chipset: str, rules: Rules) -> str:
    """The identity two spellings of one chipset share.

    Aliases applied, parentheticals and quantities dropped, then every
    vendor, role and filler word removed and what is left joined lowercase.
    `Qualcomm SDX35` and `SDX35` are the same chipset; `MT7921` and `MT7925`
    are not.

    An empty result means the text held nothing but vendor and role words,
    which is how a cell naming only a vendor is recognised.

    **Preserved defect.** The join has no separator and the order matters, so
    `MT79 77` and `MT7977` collide and `A+B` never matches `B+A`. This is the
    identity the whole match evidence in the source's specification was
    validated against; changing it would change which rows are reported as
    already tracked.
    """
    text = apply_chipset_aliases(clean_text(chipset), rules)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"(?:\s+x|\s*\*)\s*\d+\b", " ", text, flags=re.IGNORECASE)
    keep: list[str] = []
    for token in re.split(r"[^0-9A-Za-z]+", text):
        low = token.lower()
        if not low:
            continue
        if low in rules.vendor_tokens or low in rules.roles or low in rules.fillers:
            continue
        keep.append(low)
    return "".join(keep)


# ---------------------------------------------------------------------------
# The scalar columns
# ---------------------------------------------------------------------------


def parse_units(value: Any) -> float | None:
    """The number of units a cell means, or nothing.

    **Preserved defect.** A comma becomes a space rather than being removed,
    so a text cell reading `1,200` parses as nothing and its value moves from
    the total to the notes beside it. And `200K x 2` reports 2, because the
    multiplier is read as the quantity. Both change a number the parity gate
    compares.
    """
    text = clean_text(value)
    if not text:
        return None
    text = text.replace(",", " ").strip()
    whole = re.fullmatch(r"(\d+(?:\.\d+)?)", text)
    if whole:
        return float(whole.group(1))
    multiplied = re.search(r"\bx\s*(\d+)\b", text, re.IGNORECASE)
    if multiplied:
        return float(multiplied.group(1))
    return None


def parse_schedule(value: Any) -> tuple[_dt.date | None, str]:
    """`(the first of the month, the text as written)`.

    Every schedule in the source workbook is a month, however it is spelled:
    `July. 2026`, `Dec,2026`, `May-2027`, `Q4-26`, `2026/4`, or a real date.
    A quarter becomes its first month. Text that means nothing datelike comes
    back as text, so the caller can show it rather than drop it.

    An out-of-range month in a `YYYY/M` cell is such text. The source handed
    it to `date()` and crashed, which on this platform would be a step that
    failed with nothing to say.
    """
    if isinstance(value, _dt.datetime | _dt.date):
        point = value.date() if isinstance(value, _dt.datetime) else value
        return _dt.date(point.year, point.month, 1), clean_text(value)
    text = clean_text(value)
    if not text:
        return None, ""
    named = _MONTH_RE.search(text)
    if named:
        month = _MONTHS[named.group(1).lower()[:3]]
        year = int(named.group(2))
        year += 2000 if year < 100 else 0
        return _dt.date(year, month, 1), text
    numeric = _YEARMON_RE.search(text)
    if numeric:
        month = int(numeric.group(2))
        if 1 <= month <= 12:
            return _dt.date(int(numeric.group(1)), month, 1), text
        return None, text
    quarter = _QUARTER_RE.search(text)
    if quarter:
        year = int(quarter.group(2))
        year += 2000 if year < 100 else 0
        return _dt.date(year, int(quarter.group(1)) * 3 - 2, 1), text
    return None, text


def format_schedule(when: _dt.date | None, rules: Rules) -> str:
    """The month as the sheet writes it, `Jul. 2026`.

    The month name is this module's own, not the host's. `%b` follows the
    machine's locale, so on a non-English Windows the whole column would
    silently change language and stop matching what is already in the sheet.
    """
    if not when:
        return ""
    pattern = rules.output.schedule_format
    parts = pattern.split("%%")
    rendered = "%%".join(part.replace("%b", _MONTH_NAMES[when.month - 1]) for part in parts)
    return when.strftime(rendered)


def map_priority(value: Any, rules: Rules) -> str:
    """`H`, `M` and `L` as the sheet spells them out. An exact match after
    lowering, so `high priority` is not a priority."""
    text = clean_text(value).lower()
    return rules.ruleset.priority.map.get(text, rules.ruleset.priority.unknown)


def merge_priority(first: str, second: str, rules: Rules) -> str:
    """The higher of two priorities; a tie keeps the one already there. A
    value the ranking does not name scores nothing and loses to `Low`."""
    rank = rules.ruleset.priority.rank
    if not first:
        return second
    if not second:
        return first
    return first if rank.get(first, 0) >= rank.get(second, 0) else second


def split_companies(value: Any, rules: Rules, kind: str = "brand") -> list[str]:
    """The companies a `Brand` or `MFG` cell names.

    A whole cell may be listed as one name, because a newline is sometimes
    part of a company's name and sometimes a second company, and nothing in
    the text says which. A line that is entirely a dropped token goes before
    it can be split, which is why `N/A` does not become `N` and `A`.
    """
    company = rules.ruleset.brand if kind == "brand" else rules.ruleset.mfg
    raw = clean_text(value)
    if not raw:
        return []
    if raw in company.line_joins:
        return list(company.line_joins[raw])
    aliases = {key.lower(): value for key, value in company.aliases.items()}
    drops = {token.lower() for token in company.drop_tokens}
    out: list[str] = []
    for part in re.split(r"[\n]+", raw):
        if part.strip(" .;").lower() in drops:
            continue
        for piece in re.split(r"\s*[/,]\s*", part):
            name = piece.strip(" .;")
            if not name or name.lower() in drops:
                continue
            name = aliases.get(name.lower(), name)
            if name not in out:
                out.append(name)
    return out


def join_companies(names: Iterable[str], rules: Rules) -> str:
    """Companies in one cell, joined as the sheet joins them."""
    seen: list[str] = []
    for name in names:
        if name and name not in seen:
            seen.append(name)
    return rules.output.company_join.join(seen)


# ---------------------------------------------------------------------------
# A source row
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRow:
    """One row of a project list sheet, read by column name."""

    fiscal_year: str
    sheet: str
    row_number: int
    brand: str = ""
    mfg: str = ""
    project_name: str = ""
    chipset_models: str = ""
    end_products: str = ""
    purpose: str = ""
    units: Any = None
    schedule: Any = None
    opp_id: str = ""
    priority: str = ""
    status: str = ""

    @classmethod
    def from_record(
        cls, record: Mapping[str, Any], fiscal_year: str, sheet: str, row_number: int
    ) -> SourceRow:
        """Read one record, whatever this workbook calls its columns.

        The two fiscal years spell several headers differently and wrap some
        of them over two lines, so every lookup folds case, spacing and
        punctuation. `units` and `schedule` are kept as the cell had them,
        because a real number and a real date carry more than their text.
        """

        def get(*names: str) -> Any:
            for name in names:
                for key in record:
                    if header_key(key) == header_key(name):
                        return record[key]
            return None

        return cls(
            fiscal_year=fiscal_year,
            sheet=sheet,
            row_number=row_number,
            brand=clean_text(get("Brand")),
            mfg=clean_text(get("MFG")),
            project_name=clean_text(get("Project Name")),
            chipset_models=clean_text(get("Chipset models")),
            end_products=clean_text(get("End-Products", "End Products")),
            purpose=clean_text(get("Purpose")),
            units=get("Potential Biz (Units)", "Potential Biz"),
            schedule=get("Purchased Schedule (M/Y)", "Purchased Schedule"),
            opp_id=clean_text(get("OPP ID")),
            priority=clean_text(get("Prority", "Priority")),
            status=clean_text(get("Status (Won/On-going/Lost)", "Status")),
        )

    @property
    def project_uid(self) -> str:
        """What makes this the same opportunity in another fiscal year.

        Both lists carry the same projects, so units must be counted once.
        The first file that carries a project decides, which is why the
        newest fiscal year is listed first.
        """
        parts = [self.opp_id, self.project_name, self.brand, self.mfg]
        return "|".join(re.sub(r"\s+", " ", part).strip().lower() for part in parts)


def row_is_included(row: SourceRow, include: Sequence[str] | None, exclude: Sequence[str]) -> bool:
    """Whether this project belongs in the report. A whitelist beats the
    exclusions; a blank status is included, because several live projects
    have one."""
    status = row.status.strip().lower()
    if include:
        return status in {item.strip().lower() for item in include}
    return status not in {item.strip().lower() for item in exclude}


def resolve_technologies(
    token: ChipsetToken, row: SourceRow, rules: Rules
) -> tuple[list[str], list[str], list[str]]:
    """`(technologies, generation details, warnings)`.

    Strictly one source, first that answers: an explicit label or technology
    parenthesis, then what the model number itself says, then the project's
    own words. One source rather than the union of all three, so the answer
    is explainable and a product word cannot pollute a model rule that was
    already right.
    """
    warnings: list[str] = []
    context = " ".join([row.end_products, row.purpose, row.project_name])
    details = find_tech_details(" ".join([token.display, token.raw_line, context]), rules)

    if token.tech_hint:
        return order_technologies(token.tech_hint, rules), details, warnings
    from_chipset = technologies_from_chipset(token.display, rules)
    if from_chipset:
        return order_technologies(from_chipset, rules), details, warnings
    from_context = find_technologies(context, rules)
    if from_context:
        warnings.append(INFERRED_TECHNOLOGY)
        return order_technologies(from_context, rules), details, warnings
    warnings.append(UNRESOLVED_TECHNOLOGY)
    return [rules.unresolved], details, warnings


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass
class Aggregate:
    """One chipset and technology, with every project that asked for it."""

    key: tuple[str, str]
    chipset: str
    technology: str
    vendor: str = ""
    brands: list[str] = field(default_factory=list)
    mfgs: list[str] = field(default_factory=list)
    units_total: float = 0.0
    units_texts: list[str] = field(default_factory=list)
    schedule_date: _dt.date | None = None
    schedule_texts: list[str] = field(default_factory=list)
    priority: str = ""
    projects: list[str] = field(default_factory=list)
    opp_ids: list[str] = field(default_factory=list)
    fiscal_years: list[str] = field(default_factory=list)
    source_rows: list[str] = field(default_factory=list)
    #: `(tag, project name, opportunity id)`, index-parallel to `source_rows`.
    source_refs: list[tuple[str, str, str]] = field(default_factory=list)
    raw_texts: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unresolved: bool = False
    counted_uids: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class DroppedChipset:
    """A chipset left out of the report, and why. Dropping is deliberate and
    never silent: a project that is absent has to be explainable."""

    project: str
    fiscal_year: str
    row_number: int
    raw: str
    parsed: str
    reason: str


PLACEHOLDER_REASON = "placeholder (TBD/TBC/N/A)"
VENDOR_ONLY_REASON = "vendor named but no model"


def drop_unresolved(
    tokens: Sequence[ChipsetToken], row: SourceRow, rules: Rules
) -> tuple[list[ChipsetToken], list[DroppedChipset]]:
    """Remove the chipsets nobody has chosen yet.

    A cell reading `TBC`, `N/A` or just a vendor name means the chipset is
    not decided, and a chipset *requirement* report is not the place for it.
    Both halves are switchable, because "vendor named, model pending" is a
    judgement rather than a fact.
    """
    drop_placeholder = rules.ruleset.split.drop_placeholders
    drop_vendor_only = rules.ruleset.split.drop_vendor_only

    kept: list[ChipsetToken] = []
    dropped: list[DroppedChipset] = []
    for token in tokens:
        if not token.unresolved:
            kept.append(token)
            continue
        vendor_only = bool(token.vendor_hint) or "(model TBD)" in token.display
        reason = VENDOR_ONLY_REASON if vendor_only else PLACEHOLDER_REASON
        if (vendor_only and drop_vendor_only) or (not vendor_only and drop_placeholder):
            dropped.append(
                DroppedChipset(
                    project=row.project_name or row.brand or row.mfg,
                    fiscal_year=row.fiscal_year,
                    row_number=row.row_number,
                    raw=clean_text(row.chipset_models),
                    parsed=token.display,
                    reason=reason,
                )
            )
            continue
        kept.append(token)
    return kept, dropped


def aggregate(
    rows: Iterable[SourceRow], rules: Rules
) -> tuple[list[Aggregate], list[DroppedChipset]]:
    """Explode every project into chipset and technology rows and merge them.

    The source returned the dropped rows by writing them onto the function
    object, which two runs in one process would have shared. They are
    returned here.
    """
    accumulated: dict[tuple[str, str], Aggregate] = {}
    dropped_all: list[DroppedChipset] = []
    for row in rows:
        tokens, dropped = drop_unresolved(split_chipsets(row.chipset_models, rules), row, rules)
        dropped_all.extend(dropped)
        for token in tokens:
            techs, details, warnings = resolve_technologies(token, row, rules)
            vendor = infer_vendor(token.display, rules, token.vendor_hint)
            identity = match_key(token.display, rules)
            if token.unresolved or not identity:
                # A placeholder is not the same undecided chipset as another
                # project's placeholder, so it carries the project with it.
                identity = f"?{row.project_uid}|{token.display.lower()}"
            for tech in techs:
                key = (identity, tech)
                agg = accumulated.get(key)
                if agg is None:
                    agg = Aggregate(key=key, chipset=token.display, technology=tech, vendor=vendor)
                    accumulated[key] = agg
                if len(token.display) > len(agg.chipset):
                    agg.chipset = token.display
                if vendor and not agg.vendor:
                    agg.vendor = vendor
                agg.unresolved = agg.unresolved or token.unresolved or tech == rules.unresolved
                for brand in split_companies(row.brand, rules, "brand"):
                    if brand not in agg.brands:
                        agg.brands.append(brand)
                for maker in split_companies(row.mfg, rules, "mfg"):
                    if maker not in agg.mfgs:
                        agg.mfgs.append(maker)
                first_time = row.project_uid not in agg.counted_uids
                agg.counted_uids.add(row.project_uid)
                if first_time:
                    units = parse_units(row.units)
                    if units is not None:
                        agg.units_total += units
                    else:
                        text = clean_text(row.units)
                        if text and text not in agg.units_texts:
                            agg.units_texts.append(text)
                when, schedule_text = parse_schedule(row.schedule)
                if when and (agg.schedule_date is None or when < agg.schedule_date):
                    agg.schedule_date = when
                if schedule_text and not when and schedule_text not in agg.schedule_texts:
                    agg.schedule_texts.append(schedule_text)
                agg.priority = merge_priority(
                    agg.priority, map_priority(row.priority, rules), rules
                )
                project = row.project_name or "(unnamed project)"
                if project not in agg.projects:
                    agg.projects.append(project)
                if row.opp_id and row.opp_id not in agg.opp_ids:
                    agg.opp_ids.append(row.opp_id)
                if row.fiscal_year not in agg.fiscal_years:
                    agg.fiscal_years.append(row.fiscal_year)
                tag = f"{row.fiscal_year}!{row.sheet}!R{row.row_number}"
                if tag not in agg.source_rows:
                    agg.source_rows.append(tag)
                    agg.source_refs.append((tag, project, row.opp_id))
                raw = clean_text(row.chipset_models) or "(empty)"
                if raw not in agg.raw_texts:
                    agg.raw_texts.append(raw)
                for detail in details:
                    if detail not in agg.details:
                        agg.details.append(detail)
                for warning in list(warnings) + list(token.warnings):
                    if warning not in agg.warnings:
                        agg.warnings.append(warning)
    return list(accumulated.values()), dropped_all


# ---------------------------------------------------------------------------
# What the sheet already tracks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExistingRow:
    row_number: int
    chipset: str
    key: str
    technologies: tuple[str, ...]
    record: Mapping[str, Any]


def index_existing(
    records: Sequence[Mapping[str, Any]], rules: Rules, first_data_row: int = 2
) -> list[ExistingRow]:
    """The rows the target sheet already has, by identity.

    A combined technology cell is split, so `WiFi / BT` matches both of the
    rows this run would produce. A row with no chipset is skipped but still
    counted, so the row numbers stay the sheet's own.
    """
    out: list[ExistingRow] = []
    for index, record in enumerate(records):
        chipset = ""
        technology = ""
        for key, value in record.items():
            if header_key(key) == "chipset":
                chipset = clean_text(value)
            elif header_key(key) == "technology":
                technology = clean_text(value)
        if not chipset:
            continue
        found = find_technologies(technology, rules)
        out.append(
            ExistingRow(
                row_number=first_data_row + index,
                chipset=chipset,
                key=match_key(chipset, rules),
                technologies=tuple(found or ([technology.lower()] if technology else [])),
                record=record,
            )
        )
    return out


def match_against_existing(
    agg: Aggregate, existing: Sequence[ExistingRow], rules: Rules
) -> tuple[str, ExistingRow | None]:
    """How this row relates to what the sheet already tracks.

    `tracked` is the same chipset with this technology listed;
    `tracked-other-tech` is the same chipset with it missing; `partial` is a
    chipset that is part of a composed one already there; `new` is neither.

    **Preserved defect.** `partial` is an unanchored substring test in both
    directions, so a long enough key can match one it merely contains.
    """
    key = agg.key[0]
    if not key:
        return "new", None
    same_key = [row for row in existing if row.key == key]
    for row in same_key:
        if agg.technology in row.technologies:
            return "tracked", row
    if same_key:
        return "tracked-other-tech", same_key[0]
    if len(key) >= 4:
        for row in existing:
            if not row.key:
                continue
            if key in row.key or row.key in key:
                return "partial", row
    return "new", None


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def build_trace(agg: Aggregate, rules: Rules, today: _dt.date) -> str:
    """The provenance block written at the top of the comments cell.

    One record per contributing source row, each on its own line and each
    line parseable, so a reader can find the project this row came from. The
    date is given, never read from the clock: a plan has to be the same plan
    when it is applied.
    """
    lines = [f"{rules.output.trace_prefix} {today:%Y-%m-%d}]"]
    for tag, project, opportunity in agg.source_refs:
        lines.append(
            f"{tag} | project={one_line(project) or '-'} | opp={one_line(opportunity) or '-'}"
        )
    lines.append(f"raw={' || '.join(one_line(text) for text in agg.raw_texts)}")
    return "\n".join(lines)


def match_header(headers: Sequence[str], wanted: str) -> str:
    """The live header that means `wanted`, or nothing."""
    for header in headers:
        if header_key(header) == header_key(wanted):
            return header
    return ""


def watched_but_missing(headers: Sequence[str], rules: Rules) -> list[str]:
    """Watched columns this sheet does not have.

    The failure it exists to prevent is the quietest kind: a misspelt watch
    field produces no error, no highlight and no reason to suspect that the
    feature is off.
    """
    return [
        field_name for field_name in rules.watch_fields if not match_header(headers, field_name)
    ]


def render_row(
    agg: Aggregate,
    match: str,
    existing: ExistingRow | None,
    headers: Sequence[str],
    rules: Rules,
    today: _dt.date,
) -> dict[str, Any]:
    """One record keyed by the sheet's own headers, plus the audit columns.

    What the source workbook knows wins for the business columns, because the
    source is where that changes. What the target sheet knows wins for the
    columns people keep by hand: the owner, the development status and the
    comments.

    **Preserved defect.** The new trace block is written above the previous
    comments without removing the previous trace, so the cell grows on every
    run.
    """
    existing_record: Mapping[str, Any] = existing.record if existing else {}

    def existing_value(name: str) -> Any:
        for key, value in existing_record.items():
            if header_key(key) == header_key(name):
                return value
        return None

    # **Preserved defect.** A real total of exactly zero is reported as
    # unknown, because zero is falsy here and unknown has its own marker.
    biz: Any
    if agg.units_total > 0:
        biz = int(agg.units_total) if float(agg.units_total).is_integer() else agg.units_total
    elif agg.units_texts:
        biz = " / ".join(agg.units_texts)
    else:
        biz = rules.output.unknown_biz_marker

    schedule = format_schedule(agg.schedule_date, rules) or " / ".join(agg.schedule_texts)

    owner = clean_text(existing_value("DRI"))
    if not owner:
        owner = (
            rules.ruleset.dri.by_technology.get(agg.technology)
            or rules.ruleset.dri.by_vendor.get(agg.vendor)
            or rules.ruleset.dri.fallback
        )

    status = clean_text(existing_value("Status")) or rules.ruleset.status.new_row_status

    trace = build_trace(agg, rules, today)
    previous_comments = clean_text(existing_value("Comments"))
    comments = f"{trace}\n\n{previous_comments}" if previous_comments else trace

    values: dict[str, Any] = {
        "chipsetvendor": agg.vendor,
        "chipset": agg.chipset,
        "technology": agg.technology,
        "brand": join_companies(agg.brands, rules),
        "mfg": join_companies(agg.mfgs, rules),
        "protentialbiz": biz,
        "potentialbiz": biz,
        "purchasedschedule": schedule,
        "piority": agg.priority,
        "priority": agg.priority,
        "dri": owner,
        "status": status,
        "comments": comments,
    }

    record: dict[str, Any] = {header: values.get(header_key(header), "") for header in headers}

    # Which watched columns this run would change. Empty on a row with
    # nothing to compare against: every value on a new row differs from
    # nothing, and marking them all would say nothing.
    changed: list[str] = []
    if existing is not None:
        for watched in rules.watch_fields:
            before = clean_text(existing_value(watched))
            after = clean_text(record.get(match_header(headers, watched), ""))
            if before != after:
                changed.append(match_header(headers, watched) or watched)

    record["_Match"] = match
    record["_Changed"] = ", ".join(changed)
    record["_MatchedRow"] = existing.row_number if existing else ""
    record["_SourceFY"] = ", ".join(agg.fiscal_years)
    record["_SourceProjects"] = " | ".join(one_line(project) for project in agg.projects)
    record["_SourceOPPIDs"] = ", ".join(agg.opp_ids)
    record["_SourceRows"] = ", ".join(agg.source_rows)
    record["_RawChipsetText"] = " || ".join(one_line(text) for text in agg.raw_texts)
    record["_TechDetail"] = ", ".join(agg.details)
    record["_Warnings"] = "; ".join(agg.warnings)
    return record


def sort_key(record: Mapping[str, Any], headers: Sequence[str], rules: Rules) -> tuple[Any, ...]:
    """Vendor in the ruleset's order, then chipset, then technology. A vendor
    the ruleset does not name sorts last."""
    order = rules.vendor_order
    vendor = ""
    chipset = ""
    technology = ""
    for header in headers:
        if header_key(header) == "chipsetvendor":
            vendor = str(record.get(header, ""))
        elif header_key(header) == "chipset":
            chipset = str(record.get(header, ""))
        elif header_key(header) == "technology":
            technology = str(record.get(header, ""))
    index = order.index(vendor) if vendor in order else len(order)
    return (index, vendor, chipset.lower(), technology)


def apply_vendor_display(
    records: list[dict[str, Any]], headers: Sequence[str], rules: Rules
) -> None:
    """Blank a repeated vendor cell, if the ruleset asks for the sparse look
    the existing sheet has. Runs after the sort, and only then."""
    if rules.output.vendor_display != "groupFirst":
        return
    column = next((h for h in headers if header_key(h) == "chipsetvendor"), None)
    if not column:
        return
    last: Any = object()
    for record in records:
        current = record.get(column, "")
        if current == last:
            record[column] = ""
        else:
            last = current


def row_colour(record: Mapping[str, Any], rules: Rules) -> str:
    """The fill that says how this row matched, or that its technology could
    not be worked out, which is the more useful thing to say."""
    colours = rules.colours
    warnings = record.get("_Warnings")
    if warnings and UNRESOLVED_TECHNOLOGY in str(warnings):
        return colours.unresolved
    match = record.get("_Match", "new")
    if match == "tracked":
        return colours.tracked
    if match in ("partial", "tracked-other-tech"):
        return colours.partial
    return colours.new


@dataclass(frozen=True)
class TransformResult:
    """The rows this run would write, and everything that explains them."""

    records: tuple[dict[str, Any], ...]
    dropped: tuple[DroppedChipset, ...]
    projects_read: int
    projects_included: int
    chipsets_extracted: int
    rows_generated: int
    unresolved_technology: int
    existing_rows: int
    match_counts: Mapping[str, int]

    @property
    def projects_skipped(self) -> int:
        return self.projects_read - self.projects_included


def transform(
    source_rows: Sequence[SourceRow],
    existing_records: Sequence[Mapping[str, Any]],
    headers: Sequence[str],
    rules: Rules,
    *,
    today: _dt.date,
    include_statuses: Sequence[str] | None = None,
    exclude_statuses: Sequence[str] | None = None,
    target_header_row: int = 1,
) -> TransformResult:
    """Filter, explode, aggregate, match, render, sort.

    `target_header_row` is where the column names sit in the target sheet,
    and it is needed only to turn a record's position into the row number a
    reader can jump to. The records arrive without their header, so nothing
    else here can tell row 2 from row 3, and an off-by-one points at a row
    that still looks real.
    """
    excluded = list(
        exclude_statuses
        if exclude_statuses is not None
        else rules.ruleset.status.exclude_by_default
    )
    kept = [row for row in source_rows if row_is_included(row, include_statuses, excluded)]
    aggregates, dropped = aggregate(kept, rules)
    existing = index_existing(existing_records, rules, first_data_row=max(1, target_header_row) + 1)

    records: list[dict[str, Any]] = []
    counts = dict.fromkeys(MATCH_LEVELS, 0)
    for agg in aggregates:
        match, matched = match_against_existing(agg, existing, rules)
        counts[match] = counts.get(match, 0) + 1
        records.append(render_row(agg, match, matched, headers, rules, today))
    records.sort(key=lambda record: sort_key(record, headers, rules))
    apply_vendor_display(records, headers, rules)

    return TransformResult(
        records=tuple(records),
        dropped=tuple(dropped),
        projects_read=len(source_rows),
        projects_included=len(kept),
        chipsets_extracted=len({agg.key[0] for agg in aggregates}),
        rows_generated=len(records),
        unresolved_technology=sum(1 for agg in aggregates if agg.technology == rules.unresolved),
        existing_rows=len(existing),
        match_counts=counts,
    )
