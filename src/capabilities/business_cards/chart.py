"""The org chart: grouped boxes and reporting lines, drawn with Pillow.

No Graphviz: a colleague's install has Pillow (it comes with the bundle's
`weekly-mail` extra; CI has it through `office`), and the layout here is a
simple nested-box packing. Business group → division → department are nested
frames; people sit inside their innermost group, ordered by title seniority.
A reporting line is drawn from the manager's card to the person's: solid when
it has evidence, dashed when it was inferred. People who left are left out,
or drawn grey when asked for.

The legend says what the picture is every time: without evidenced lines the
order inside a box is title seniority, not who reports to whom.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from capabilities.business_cards.contracts import FIELD_LABELS

#: Seniority, used only to order people inside their box (from the Hermes
#: `cards.py`, with a few more titles). An unknown title sorts last.
TITLE_RANKS: tuple[tuple[tuple[str, ...], int], ...] = (
    (("董事長", "chairman", "ceo", "president"), 10),
    (("總經理", "general manager", "managing director"), 20),
    (("執行副總", "資深副總", "副總", "vice president", "vp", "deputy general"), 30),
    (("處長", "協理", "director", "head of"), 40),
    (("部長", "經理", "manager"), 50),
    (("副理", "課長", "主任", "supervisor", "team lead", "leader"), 60),
    (("資深", "senior", "principal", "staff"), 70),
    (("工程師", "engineer", "specialist", "專員", "業務", "sales"), 80),
    (("助理", "assistant", "intern", "實習"), 90),
)
FONT_CANDIDATES = (
    "C:/Windows/Fonts/msjh.ttc",
    "C:/Windows/Fonts/msjhl.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/mingliu.ttc",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
EVIDENCE_LABELS = {
    "signature": "簽名檔",
    "email_content": "郵件內容",
    "title_inference": "依職稱推論",
    "user": "使用者告知",
}
NOTE = (
    "依事業群 → 處 → 部門分組，框內依職稱高低排序。框線只表示分組；"
    "只有畫出的線才是回報關係：實線有證據，虛線是推論。"
)
NO_LINES_NOTE = "這張圖沒有任何有證據的回報關係：框內的上下順序只代表職稱高低，不代表誰向誰報告。"

CARD_W, CARD_H = 210, 78
PAD, GAP, HEADER = 12, 14, 30
MAX_ROW_W = 2600
TITLE_H = 72
UNLABELLED = "（未標示部門）"
_INK = (33, 37, 41)
_GREY = (150, 150, 150)
_FRAMES = ((220, 230, 245), (232, 240, 236), (246, 241, 230))
_LINE = (60, 90, 160)
_UNSURE = (196, 127, 0)


def needs_label(fields: Sequence[str]) -> str:
    """The card's "needs confirmation" line, fields named in Chinese."""
    return "需確認：" + "、".join(FIELD_LABELS.get(name, name) for name in fields)


def rank_title(title: str) -> int:
    text = (title or "").casefold()
    best = 999
    for words, rank in TITLE_RANKS:
        if any(word.casefold() in text for word in words):
            best = min(best, rank)
    return best


@dataclass
class _Node:
    label: str
    depth: int
    people: list[sqlite3.Row] = field(default_factory=list)
    children: dict[str, _Node] = field(default_factory=dict)
    w: int = 0
    h: int = 0


def _paths(people: Sequence[sqlite3.Row]) -> dict[str, list[str]]:
    """Each person's (business group, division, department) path. A missing
    upper level is taken from colleagues when they agree on it: a card
    without the business group still lands in the division's one group."""
    levels = ("business_group", "division", "department")
    rows = [[str(person[key]).strip() for key in levels] for person in people]
    above: dict[tuple[int, str], set[tuple[str, ...]]] = {}
    for row in rows:
        for depth in (1, 2):
            if row[depth] and all(row[:depth]):
                above.setdefault((depth, row[depth]), set()).add(tuple(row[:depth]))
    paths: dict[str, list[str]] = {}
    for person, row in zip(people, rows, strict=True):
        for depth in (2, 1):
            known = above.get((depth, row[depth])) if row[depth] else None
            if known is not None and len(known) == 1 and not all(row[:depth]):
                filled = next(iter(known))
                row[:depth] = [row[i] or filled[i] for i in range(depth)]
        paths[person["person_id"]] = [label for label in row if label] or [UNLABELLED]
    return paths


def _tree(people: Sequence[sqlite3.Row]) -> _Node:
    root = _Node("", 0)
    paths = _paths(people)
    for person in people:
        node = root
        for depth, label in enumerate(paths[person["person_id"]], 1):
            node = node.children.setdefault(label, _Node(label, depth))
        node.people.append(person)
    return root


def _measure(node: _Node) -> None:
    for child in node.children.values():
        _measure(child)
    people_h = len(node.people) * (CARD_H + GAP)
    people_w = CARD_W if node.people else 0
    kids = list(node.children.values())
    kids_w = sum(child.w for child in kids) + GAP * max(0, len(kids) - 1)
    kids_h = max((child.h for child in kids), default=0)
    inner_w = max(people_w, kids_w, CARD_W)
    node.w = inner_w + 2 * PAD
    node.h = HEADER + people_h + kids_h + PAD + (GAP if node.people and kids else 0)


@dataclass
class _Placed:
    person: sqlite3.Row
    box: tuple[int, int, int, int]


@dataclass
class _Layout:
    frames: list[tuple[tuple[int, int, int, int], str, int]] = field(default_factory=list)
    cards: dict[str, _Placed] = field(default_factory=dict)


def _place(node: _Node, x: int, y: int, layout: _Layout) -> None:
    layout.frames.append(((x, y, x + node.w, y + node.h), node.label, node.depth))
    cursor = y + HEADER
    for person in sorted(node.people, key=lambda p: (rank_title(p["title"]), p["name"])):
        box = (x + PAD, cursor, x + PAD + CARD_W, cursor + CARD_H)
        layout.cards[person["person_id"]] = _Placed(person, box)
        cursor += CARD_H + GAP
    if node.people and node.children:
        cursor += GAP
    left = x + PAD
    for child in node.children.values():
        _place(child, left, cursor, layout)
        left += child.w + GAP


def layout(people: Sequence[sqlite3.Row]) -> tuple[_Layout, int, int]:
    """Top-level groups packed into rows no wider than `MAX_ROW_W`."""
    root = _tree(people)
    _measure(root)
    placed = _Layout()
    x, y, row_h, width = PAD, TITLE_H, 0, 0
    for group in root.children.values():
        if x > PAD and x + group.w > MAX_ROW_W:
            x, y = PAD, y + row_h + GAP
            row_h = 0
        _place(group, x, y, placed)
        x += group.w + GAP
        row_h = max(row_h, group.h)
        width = max(width, x)
    return placed, max(width + PAD, 480), y + row_h + PAD


def _font(size: int) -> Any:
    from PIL import ImageFont

    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow before 10.1 has one bitmap size
        return ImageFont.load_default()


def _fit(draw: Any, text: str, font: Any, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text + "…"


def _dashed(draw: Any, points: Sequence[tuple[int, int]], fill: Any, width: int) -> None:
    dash, space = 8, 6
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        length = abs(x1 - x0) + abs(y1 - y0)
        steps = max(1, length // (dash + space) + 1)
        for step in range(int(steps)):
            start = step * (dash + space)
            end = min(start + dash, length)
            if start >= length:
                break
            fx0, fy0 = x0 + (x1 - x0) * start / length, y0 + (y1 - y0) * start / length
            fx1, fy1 = x0 + (x1 - x0) * end / length, y0 + (y1 - y0) * end / length
            draw.line([(fx0, fy0), (fx1, fy1)], fill=fill, width=width)


def render(
    path: Path,
    company: str,
    people: Sequence[sqlite3.Row],
    lines: Sequence[sqlite3.Row],
    *,
    uncertain: Mapping[str, Sequence[str]],
) -> None:
    """Write the PNG. Raises ImportError when Pillow is not installed."""
    from PIL import Image, ImageDraw

    placed, width, height = layout(people)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    big, mid, small = _font(22), _font(15), _font(12)
    draw.text((PAD, 14), _fit(draw, f"{company} 組織圖", big, width - 2 * PAD), fill=_INK, font=big)
    for (x0, y0, x1, y1), label, depth in placed.frames:
        colour = _FRAMES[(depth - 1) % len(_FRAMES)]
        draw.rounded_rectangle((x0, y0, x1, y1), radius=8, fill=colour, outline=(170, 180, 195))
        draw.text((x0 + 8, y0 + 7), _fit(draw, label, mid, x1 - x0 - 16), fill=_INK, font=mid)
    lane = 0
    for line in lines:
        head, member = placed.cards.get(line["manager_id"]), placed.cards.get(line["person_id"])
        if head is None or member is None:
            continue
        bx = (head.box[0] + head.box[2]) // 2
        px = (member.box[0] + member.box[2]) // 2
        end = (px, member.box[1])
        if member.box[1] >= head.box[3] and abs(px - bx) <= CARD_W:
            # Below the manager in the same column: straight down.
            start = (bx, head.box[3])
            middle = (start[1] + end[1]) // 2
        else:
            # Elsewhere: up from the manager to a lane under the title, across,
            # and down into the person's card.
            start = (bx, head.box[1])
            middle = TITLE_H - 8 - 5 * (lane % 4)
            lane += 1
        points = [start, (start[0], middle), (end[0], middle), end]
        if line["inferred"]:
            _dashed(draw, points, _LINE, 2)
        else:
            draw.line(points, fill=_LINE, width=2, joint="curve")
        draw.polygon([(end[0] - 5, end[1] - 8), (end[0] + 5, end[1] - 8), end], fill=_LINE)
    for placed_card in placed.cards.values():
        person = placed_card.person
        x0, y0, x1, y1 = placed_card.box
        left = person["status"] == "left"
        unsure = bool(uncertain.get(person["person_id"]))
        outline = _UNSURE if unsure else ((190, 190, 190) if left else (120, 130, 150))
        draw.rounded_rectangle(
            (x0, y0, x1, y1),
            radius=6,
            fill=(238, 238, 238) if left else "white",
            outline=outline,
            width=2 if unsure else 1,
        )
        ink = _GREY if left else _INK
        name = person["name"] + ("  ！" if unsure else "")
        draw.text((x0 + 8, y0 + 6), _fit(draw, name, mid, CARD_W - 16), fill=ink, font=mid)
        second = person["title"] or person["romanised_name"]
        if left:
            second = f"已離職 {person['left_at']}".strip()
        draw.text((x0 + 8, y0 + 30), _fit(draw, second, small, CARD_W - 16), fill=ink, font=small)
        contact = person["mobile"] or (
            person["phone"] + (f" #{person['ext']}" if person["ext"] else "")
        )
        if unsure:
            contact = needs_label(uncertain[person["person_id"]])
        draw.text((x0 + 8, y0 + 50), _fit(draw, contact, small, CARD_W - 16), fill=ink, font=small)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")


def legend(
    company: str,
    people: Sequence[sqlite3.Row],
    lines: Sequence[sqlite3.Row],
    *,
    include_left: bool,
    left_omitted: int,
) -> str:
    """The Markdown that goes with the picture: what it is and every line's evidence."""
    named = {person["person_id"]: person["name"] for person in people}
    shown = [line for line in lines if line["person_id"] in named and line["manager_id"] in named]
    evidenced = [line for line in shown if not line["inferred"]]
    out = [f"**{company} 組織圖**（{len(people)} 人）", "", NOTE]
    if not evidenced:
        out += ["", f"**{NO_LINES_NOTE}**"]
    if include_left:
        out += ["", "已離職的人以灰色顯示。"]
    elif left_omitted:
        out += ["", f"已離職的 {left_omitted} 人沒有畫出。"]
    if shown:
        out += ["", "| 成員 | 主管 | 依據 | 推論 |", "|---|---|---|---|"]
        for line in shown:
            evidence = EVIDENCE_LABELS.get(line["evidence_kind"], line["evidence_kind"])
            if line["evidence_ref"]:
                evidence += f"（{line['evidence_ref']}）"
            out.append(
                f"| {named[line['person_id']]} | {named[line['manager_id']]} | {evidence} | "
                f"{'是（虛線）' if line['inferred'] else '否（實線）'} |"
            )
    return "\n".join(out)
