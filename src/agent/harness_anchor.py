"""G2: the person's own sentence anchors a Harness tool's input (owner 2026-10-18).

The conversation model chooses a Harness tool and writes its argument (for
Knowledge, the question). The model may make the sentence self-contained, but
it must not change what was asked. The Host therefore passes the person's
original message (the current turn's text) to the domain adapter next to the
model's version, and the adapter uses the original as its primary input. The
model's version may only add:

- retrieval breadth: an accepted version is a supplementary query, never the
  question that synthesis and validation answer;
- context: terms it added that come from the recent conversation (a pronoun
  such as "那車用呢?" resolved from history) or from the domain's glossary.

This check is deterministic, with no model call:

1. Entity preservation. Every entity-like term of the original (a token with a
   digit or a capital letter, a time word, a glossary term) must appear in the
   model's version, directly or through a glossary synonym group. If one is
   missing, the model's version is rejected and the original alone is used.
2. Added terms. A term in the model's version that is not in the original, the
   recent conversation or the glossary is dropped from it.

Limitation (documented in docs/HARNESS_DESIGN.zh-TW.md): there is no general
bilingual dictionary in the repository, so cross-language matching only works
through the domain glossary's synonym groups (for Knowledge, the installed
Skill procedure's facet and focus terms). Chinese text has no word boundaries:
Chinese terms are runs split at common function words, matched as substrings,
and only glossary or time terms of the original are required to survive.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

MAX_SUPPLEMENT_CHARS = 400
MAX_RECORDED_CHARS = 2_000

# Latin words, product codes and numbers: CMX500, 5G, Wi-Fi, 802.11ax, Q3.
_LATIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9+._/-]*[A-Za-z0-9+])?")
_CJK = re.compile(r"[㐀-䶿一-鿿豈-﫿]+")
# Chinese function words that separate content terms inside a run.
_CJK_FUNCTION = re.compile(
    "(?:什麼|甚麼|哪些|哪個|哪裡|如何|怎麼|怎樣|為什麼|是否|有沒有|有哪些|一下|以及|還有|"
    "請問|請|的|是|嗎|呢|吧|了|和|與|及|或|跟|那|這)"
)
_TIME_WORDS = (
    "今年",
    "去年",
    "明年",
    "前年",
    "後年",
    "今天",
    "昨天",
    "明天",
    "本月",
    "上個月",
    "下個月",
    "本季",
    "上季",
    "下季",
    "上半年",
    "下半年",
    "近期",
    "最近",
    "目前",
    "未來",
    "過去",
    "today",
    "yesterday",
    "tomorrow",
    "this year",
    "last year",
    "next year",
    "this quarter",
    "last quarter",
    "next quarter",
    "this month",
    "last month",
    "next month",
    "recent",
    "recently",
    "current",
    "currently",
)
# English function words (the same list Knowledge retrieval drops).
_STOPWORDS = frozenset(
    """
a about above after again against all am an and any are as at be because been before
being below between both but by can could did do does doing down during each few for
from further had has have having he her here hers him his how i if in into is it its
itself just me more most my no nor not now of off on once only or other our out over own
same she should so some such than that the their them then there these they this those
through to too under until up very was we were what when where which while who whom why
will with would you your please tell show give list explain describe
""".split()
)

AnchorOutcome = Literal["same", "accepted", "rejected", "absent"]


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").casefold()


def _squash(text: str) -> str:
    """Letters, digits and CJK only: what makes two sentences the same request."""
    return "".join(ch for ch in _norm(text) if ch.isalnum())


def _latin_tokens(text: str) -> list[str]:
    return _LATIN.findall(unicodedata.normalize("NFKC", text or ""))


def _cjk_terms(text: str) -> list[str]:
    terms: list[str] = []
    for run in _CJK.findall(unicodedata.normalize("NFKC", text or "")):
        for part in _CJK_FUNCTION.split(run):
            if len(part) >= 2 and part not in terms:
                terms.append(part)
    return terms


def _has_token(text_norm: str, token: str) -> bool:
    if _CJK.fullmatch(token):
        return token in text_norm
    return re.search(rf"(?<![a-z0-9]){re.escape(_norm(token))}(?![a-z0-9])", text_norm) is not None


def _entity_tokens(text: str) -> list[str]:
    """Latin tokens that name something: a digit or a capital letter, not a
    function word ("What" is capitalized but asks, it does not name)."""
    found: list[str] = []
    for token in _latin_tokens(text):
        if token.casefold() in _STOPWORDS:
            continue
        if any(ch.isdigit() for ch in token) or any(ch.isupper() for ch in token):
            if token not in found:
                found.append(token)
    return found


@dataclass(frozen=True)
class Glossary:
    """A domain's bilingual vocabulary as synonym groups. A required term is
    preserved when any term of a group that contains it appears."""

    groups: tuple[tuple[str, ...], ...] = ()

    @classmethod
    def of(cls, groups: Iterable[Iterable[str]]) -> Glossary:
        kept = []
        for group in groups:
            terms = tuple(dict.fromkeys(t.strip() for t in group if t and len(t.strip()) >= 2))
            if terms:
                kept.append(terms)
        return cls(tuple(kept))

    def terms(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(term for group in self.groups for term in group))

    def synonyms(self, term: str) -> tuple[str, ...]:
        wanted = _norm(term)
        found = [term]
        for group in self.groups:
            if any(_norm(item) == wanted for item in group):
                found.extend(group)
        return tuple(dict.fromkeys(found))


@dataclass(frozen=True)
class ToolAnchor:
    """What the Host passes to a Harness tool next to the model's argument."""

    original: str
    history: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnchorCheck:
    original: str
    proposed: str
    outcome: AnchorOutcome
    reason: str | None = None
    missing: tuple[str, ...] = ()
    dropped: tuple[str, ...] = ()
    context_terms: tuple[str, ...] = ()
    supplement: str | None = None

    @property
    def question(self) -> str:
        """What synthesis and validation answer: the original, with the
        model's version alongside only when it resolved terms from the
        conversation (the original is not self-contained)."""
        if self.outcome == "accepted" and self.context_terms and self.supplement:
            return f"{self.original} ({self.supplement})"
        return self.original

    @property
    def supplementary(self) -> tuple[str, ...]:
        """Extra retrieval queries; they only widen what is retrieved."""
        if self.outcome == "accepted" and self.supplement:
            return (self.supplement,)
        return ()

    def record(self) -> dict[str, object]:
        """The tool record's anchor entry, from which the benchmark computes
        an intent drift rate (rejected / all)."""
        return {
            "original": self.original[:MAX_RECORDED_CHARS],
            "model_version": self.proposed[:MAX_RECORDED_CHARS],
            "outcome": self.outcome,
            "reason": self.reason,
            "missing_terms": list(self.missing),
            "dropped_terms": list(self.dropped),
            "context_terms": list(self.context_terms),
            "used_question": self.question[:MAX_RECORDED_CHARS],
            "supplementary_queries": list(self.supplementary),
        }


def _grounded(term: str, sources: Sequence[str]) -> bool:
    """A Latin token is grounded when a source has it as a word; a Chinese term
    when it splits into pieces of two or more characters that each appear in
    a source ("車用雷達市場" from "車用" and "雷達市場")."""
    if not _CJK.fullmatch(term):
        return any(_has_token(source, term) for source in sources)
    wanted = _norm(term)
    reachable = [True] + [False] * len(wanted)
    for end in range(2, len(wanted) + 1):
        reachable[end] = any(
            reachable[start] and any(wanted[start:end] in source for source in sources)
            for start in range(0, end - 1)
        )
    return reachable[-1]


def required_terms(original: str, glossary: Glossary) -> list[str]:
    """Entity, number, product, market and time terms of the original."""
    norm = _norm(original)
    required = _entity_tokens(original)
    for word in _TIME_WORDS:
        if _has_token(norm, word) and word not in required:
            required.append(word)
    for term in glossary.terms():
        if (
            _has_token(norm, term)
            and term not in required
            and _norm(term) not in {_norm(item) for item in required}
        ):
            required.append(term)
    return required


def check_anchor(
    original: str,
    proposed: str,
    *,
    history: Sequence[str] = (),
    glossary: Glossary | None = None,
) -> AnchorCheck:
    """Compare the model's version with the person's sentence (see module doc)."""
    words = glossary or Glossary()
    original = (original or "").strip()
    proposed = (proposed or "").strip()
    if not proposed:
        return AnchorCheck(original, proposed, "absent", reason="no model version")
    if not original:
        # Nothing to anchor to (a turn without the person's text): the model's
        # version is all there is, recorded as such.
        return AnchorCheck(original, proposed, "absent", reason="no original message")
    if _squash(original) == _squash(proposed):
        return AnchorCheck(original, proposed, "same")
    proposed_norm = _norm(proposed)
    missing = [
        term
        for term in required_terms(original, words)
        if not any(_has_token(proposed_norm, item) for item in words.synonyms(term))
    ]
    if missing:
        return AnchorCheck(
            original,
            proposed,
            "rejected",
            reason="missing terms of the original: " + ", ".join(missing[:10]),
            missing=tuple(missing),
        )
    original_norm = _norm(original)
    glossary_norm = "\n".join(_norm(term) for term in words.terms())
    history_norm = _norm("\n".join(history))
    dropped: list[str] = []
    context: list[str] = []
    candidates = [
        token
        for token in _latin_tokens(proposed)
        if token.casefold() not in _STOPWORDS and not _has_token(original_norm, token)
    ] + [term for term in _cjk_terms(proposed) if _norm(term) not in original_norm]
    for term in dict.fromkeys(candidates):
        if _grounded(term, (original_norm, glossary_norm)):
            continue
        if _grounded(term, (original_norm, glossary_norm, history_norm)):
            context.append(term)
        else:
            dropped.append(term)
    supplement = proposed
    for term in dropped:
        if _CJK.fullmatch(term):
            supplement = supplement.replace(term, " ")
        else:
            supplement = re.sub(
                rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])",
                " ",
                supplement,
                flags=re.IGNORECASE,
            )
    supplement = " ".join(supplement.split())[:MAX_SUPPLEMENT_CHARS]
    return AnchorCheck(
        original,
        proposed,
        "accepted",
        reason=("dropped terms not in the conversation or glossary" if dropped else None),
        dropped=tuple(dropped),
        context_terms=tuple(context),
        supplement=supplement or None,
    )
