"""List candidate Concept terms found in the vault but not yet explained by a Concept card.

Sources: list fields (test_items, measurement_topics, new_test_requirements, typical_test_needs,
standards, instruments, product_lines, spec_milestones) + uppercase acronyms / mixed tokens like
EVM, OTA, MIMO, 802.11be found anywhere in cards (frontmatter and body).

usage: python bi_concept_candidates.py ../BI [--min 1] [--out candidates.md]
"""
import argparse, re, sys
from collections import defaultdict
from pathlib import Path

LIST_FIELDS = ["test_items", "measurement_topics", "new_test_requirements", "typical_test_needs",
               "standards", "instruments", "product_lines", "spec_milestones"]
STOP = {"BI", "TBD", "OK", "NO", "YES", "ID", "AND", "OR", "TODO", "RD", "ATE", "AI", "IP", "ODM", "OEM", "SO", "WHAT", "TX", "RX"}
VENDOR_FOLDERS = {"Ecosystem", "Competitor", "Account"}  # acronym text-scan skipped (vendor boilerplate)
ACRONYM = re.compile(r"\b[A-Z]{2,}[0-9a-z]*\b|\b[A-Za-z]*[a-z][A-Z][A-Za-z0-9]*\b|\b802\.\d+[a-z]*\b")


def split_card(text):
    m = re.match(r"---\n(.*?)\n---\n?(.*)", text, re.S)
    return (m.group(1), m.group(2)) if m else ("", text)


def parse_list(raw):
    raw = raw.strip()
    if raw.startswith("["):
        raw = raw[1:-1]
    items, depth, cur = [], 0, ""
    for ch in raw:
        if ch in "([（":
            depth += 1
        elif ch in ")]）":
            depth -= 1
        if ch in ",、" and depth == 0:
            items.append(cur)
            cur = ""
        else:
            cur += ch
    items.append(cur)
    return [i.strip().strip('"').strip("'") for i in items if i.strip()]


def clean(term):
    term = re.sub(r"[(（].*?[)）]", "", term).strip()
    return term


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vault")
    ap.add_argument("--min", type=int, default=1)
    ap.add_argument("--out")
    a = ap.parse_args()
    root = Path(a.vault)
    known = set()
    for f in (root / "Concept").glob("*.md") if (root / "Concept").exists() else []:
        fm, _ = split_card(f.read_text(encoding="utf-8"))
        known.add(f.stem.lower())
        m = re.search(r"^aliases:\s*(.*)$", fm, re.M)
        if m:
            known.update(x.lower() for x in parse_list(m.group(1)))
    names = {f.stem.lower() for f in root.rglob("*.md")}
    hits = defaultdict(lambda: {"cards": set(), "src": set()})
    for f in root.rglob("*.md"):
        rel = f.relative_to(root)
        if rel.parts[0] in ("_Templates", "Concept", "Dashboard.md"):
            continue
        fm, body = split_card(f.read_text(encoding="utf-8"))
        for fld in LIST_FIELDS:
            m = re.search(rf"^{fld}:\s*(.*)$", fm, re.M)
            if m:
                for it in parse_list(m.group(1)):
                    t = clean(it)
                    if t:
                        hits[t]["cards"].add(f.stem)
                        hits[t]["src"].add(fld)
        if rel.parts[0] in VENDOR_FOLDERS:
            continue
        for t in ACRONYM.findall(fm + "\n" + re.sub(r"```.*?```", "", body, flags=re.S)):
            if t.upper() in STOP or len(t) < 2 or t.lower() in ("dataview", "table", "list", "from", "where", "sort", "this"):
                continue
            hits[t]["cards"].add(f.stem)
            hits[t]["src"].add("text")
    rows = []
    for t, v in hits.items():
        if t.lower() in known or t.lower() in names or len(v["cards"]) < a.min:
            continue
        rows.append((len(v["cards"]), t, sorted(v["src"]), sorted(v["cards"])))
    rows.sort(key=lambda r: (r[2] == ["text"], -r[0], r[1].lower()))
    out = ["# Concept 候選名詞", "", f"(已有 Concept 卡 {len(known)} 個;欄位列出的術語優先,再依出現的卡片數排序。請挑業務最常遇到的建卡)", "",
           "| 名詞 | 出現卡片數 | 來源欄位 | 出現在 |", "|---|---|---|---|"]
    for n, t, src, cards in rows:
        out.append(f"| {t} | {n} | {', '.join(src)} | {', '.join(cards[:4])}{'…' if len(cards) > 4 else ''} |")
    text = "\n".join(out) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"wrote {a.out} ({len(rows)} candidates)")
    else:
        print(text)


if __name__ == "__main__":
    main()
