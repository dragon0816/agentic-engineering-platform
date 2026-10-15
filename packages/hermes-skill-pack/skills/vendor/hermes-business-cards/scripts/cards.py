"""Business-card store and org chart.

Every scan is an immutable row. A person who changes title -- or company -- gets a
new row and the old one stays: "where was this person three years ago" is worth
more to a salesperson than a tidy table. Queries take the newest row per
(name, company); the history is one flag away.

    python cards.py add --json '{"name":"...","company":"..."}'
    python cards.py list [--company X] [--all-history]
    python cards.py history --name X
    python cards.py chart --company X --out chart.png
"""
import argparse
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(os.environ.get("BUSINESS_CARDS_HOME", Path.home() / ".business-cards"))
DB = HOME / "cards.db"

FIELDS = ["name", "company", "department", "title", "phone", "mobile",
          "email", "address", "website", "notes"]

# Seniority, used only to lay the tree out. An unknown title sorts last inside its
# department rather than being dropped: a card whose title did not survive the
# photo is still a contact worth keeping.
TITLE_RANKS = [
    (["董事長", "chairman", "president", "ceo"], 10),
    (["總經理", "general manager", "managing director"], 20),
    (["副總", "vice president", "vp", "deputy general"], 30),
    (["處長", "協理", "director", "head of"], 40),
    (["部長", "經理", "manager"], 50),
    (["課長", "主任", "supervisor", "team lead"], 60),
    (["資深", "senior", "principal", "staff"], 70),
    (["工程師", "engineer", "specialist", "專員", "業務", "sales"], 80),
    (["助理", "assistant", "intern", "實習"], 90),
]


def rank_title(title):
    t = (title or "").lower()
    best = 999
    for words, rank in TITLE_RANKS:
        for w in words:
            if w.lower() in t:
                best = min(best, rank)
    return best


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute(
        """CREATE TABLE IF NOT EXISTS cards (
               id           INTEGER PRIMARY KEY AUTOINCREMENT,
               captured_at  TEXT NOT NULL,
               name         TEXT NOT NULL,
               company      TEXT NOT NULL,
               department   TEXT,
               title        TEXT,
               phone        TEXT,
               mobile       TEXT,
               email        TEXT,
               address      TEXT,
               website      TEXT,
               notes        TEXT,
               uncertain    TEXT,
               image_path   TEXT,
               raw_text     TEXT
           )"""
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_company ON cards(company)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_name ON cards(name)")
    con.commit()
    return con


def cmd_add(args):
    # Prefer --json-file. Chinese passed as a command-line argument on Windows
    # goes through the console code page and can arrive mangled; a UTF-8 file
    # does not care what the console thinks.
    if args.json_file:
        d = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    elif args.json:
        d = json.loads(args.json)
    else:
        raise SystemExit("pass either --json-file (preferred) or --json")
    if not d.get("name") or not d.get("company"):
        raise SystemExit("both name and company are required")
    con = connect()
    prev = con.execute(
        "SELECT * FROM cards WHERE name=? AND company=? ORDER BY captured_at DESC LIMIT 1",
        (d["name"], d["company"]),
    ).fetchone()

    row = {f: d.get(f) for f in FIELDS}
    row["captured_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    row["uncertain"] = json.dumps(d.get("uncertain") or [], ensure_ascii=False)
    row["image_path"] = d.get("image_path")
    row["raw_text"] = d.get("raw_text")
    cols = ",".join(row)
    marks = ",".join("?" * len(row))
    con.execute("INSERT INTO cards (" + cols + ") VALUES (" + marks + ")", list(row.values()))
    con.commit()

    changed = []
    if prev:
        for k in ("title", "department", "phone", "mobile", "email"):
            if (prev[k] or None) != (d.get(k) or None):
                changed.append(k)
    print(json.dumps({
        "stored": True,
        "name": d["name"],
        "company": d["company"],
        "previous": ({k: prev[k] for k in ("title", "department", "captured_at")} if prev else None),
        "changed": changed,
    }, ensure_ascii=False))


def _latest(con, company=None):
    q = ("SELECT * FROM cards c WHERE c.id = ("
         " SELECT id FROM cards x WHERE x.name=c.name AND x.company=c.company"
         " ORDER BY x.captured_at DESC LIMIT 1)")
    p = []
    if company:
        q += " AND c.company LIKE ?"
        p.append("%" + company + "%")
    return con.execute(q + " ORDER BY c.company, c.department, c.name", p).fetchall()


def cmd_list(args):
    con = connect()
    rows = (con.execute("SELECT * FROM cards ORDER BY captured_at DESC").fetchall()
            if args.all_history else _latest(con, args.company))
    print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))


def cmd_history(args):
    con = connect()
    rows = con.execute("SELECT * FROM cards WHERE name LIKE ? ORDER BY captured_at",
                       ("%" + args.name + "%",)).fetchall()
    print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))


def _esc(s):
    return str(s or "").replace('"', '\\"').replace("\n", "\\n")


def cmd_chart(args):
    con = connect()
    rows = _latest(con, args.company)
    if not rows:
        raise SystemExit("no cards stored for company matching " + repr(args.company))

    by_company = {}
    for r in rows:
        dept = r["department"] or "（未標示部門）"
        by_company.setdefault(r["company"], {}).setdefault(dept, []).append(r)

    lines = ["digraph org {", "  rankdir=TB;",
             "  graph [splines=ortho, nodesep=0.35, ranksep=0.6];",
             '  node [shape=box, style=rounded, fontname="Microsoft JhengHei", fontsize=11];',
             '  edge [arrowsize=0.7, color="#888888"];']
    n = 0
    for company, depts in by_company.items():
        cid = "c%d" % n
        n += 1
        lines.append('  %s [label="%s", style="rounded,filled", fillcolor="#dce6f5", fontsize=14];'
                     % (cid, _esc(company)))
        for dept, people in depts.items():
            did = "d%d" % n
            n += 1
            lines.append('  %s [label="%s", style="rounded,filled", fillcolor="#eef2f8"];'
                         % (did, _esc(dept)))
            lines.append("  %s -> %s;" % (cid, did))
            for p in sorted(people, key=lambda r: (rank_title(r["title"]), r["name"])):
                pid = "p%d" % n
                n += 1
                bits = [p["name"]]
                if p["title"]:
                    bits.append(p["title"])
                contact = p["mobile"] or p["phone"]
                if contact:
                    bits.append(contact)
                unc = json.loads(p["uncertain"] or "[]")
                label = _esc("\n".join(bits)) + ("\\n⚠ 需確認" if unc else "")
                colour = ', color="#c47f00"' if unc else ""
                lines.append('  %s [label="%s"%s];' % (pid, label, colour))
                lines.append("  %s -> %s;" % (did, pid))
    lines.append("}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["dot", "-Tpng", "-o", str(out)],
                       input="\n".join(lines).encode("utf-8"), capture_output=True)
    if r.returncode != 0:
        raise SystemExit("graphviz failed: " + r.stderr.decode(errors="replace")[:400])

    print(json.dumps({
        "chart": str(out),
        "companies": list(by_company),
        "people": len(rows),
        "uncertain": sum(1 for x in rows if json.loads(x["uncertain"] or "[]")),
        # Said out loud on every render, because a tree that looks like an org
        # chart will be read as one.
        "note": ("Grouped by department and title seniority. Business cards carry no "
                 "reporting lines, so this is not a reporting chart."),
    }, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("--json-file", help="UTF-8 file holding the card JSON (preferred)")
    a.add_argument("--json", help="Card JSON inline; ASCII-safe values only")
    a.set_defaults(func=cmd_add)

    l = sub.add_parser("list")
    l.add_argument("--company")
    l.add_argument("--all-history", action="store_true")
    l.set_defaults(func=cmd_list)

    h = sub.add_parser("history")
    h.add_argument("--name", required=True)
    h.set_defaults(func=cmd_history)

    c = sub.add_parser("chart")
    c.add_argument("--company", required=True)
    c.add_argument("--out", default=str(HOME / "org.png"))
    c.set_defaults(func=cmd_chart)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
