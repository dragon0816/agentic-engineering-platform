#!/usr/bin/env python3
"""BI vault ingest: CSV / XLSX / Markdown table / JSON  ->  Obsidian cards with YAML frontmatter.

Examples
  python bi_ingest.py data.csv   --type test_solution --vault ../BI --dry-run
  python bi_ingest.py data.xlsx  --type customer_product --vault ../BI --sheet Sheet1
  python bi_ingest.py report.md  --type ecosystem --vault ../BI --table "has:全球代表廠" --mapping map.json
  python bi_ingest.py shared.csv --type competitor --vault ../BI --fill-only
  python bi_ingest.py --emit-templates ../BI/_Templates
  python bi_ingest.py --list-types

Behaviour
  * Column headers are matched to schema fields by name or alias (Chinese and English); see bi_schema.py.
  * Values are normalised: dates -> YYYY-MM-DD (ROC years ok), lists split on ; , 、 | (not inside brackets),
    links -> "[[name]]" (trailing (...) removed), enums mapped through aliases, ints range-checked.
  * Existing cards are merged by default: new non-empty scalars overwrite, lists are unioned,
    the body text and unknown frontmatter keys are kept, new notes are appended under "## 匯入備註".
    Re-running the same input changes nothing.
  * --fill-only (v4): merge but never overwrite an existing scalar value; empty fields are filled and lists
    are unioned. Use it to add a domain (e.g. robotics) to cards that already exist in another domain.
  * v4 guards: (1) domain list values are validated against DOMAINS; (2) for single-domain card types a
    same-name card that belongs to another domain is skipped with a warning (rename it with a prefix);
    (3) when a card has `node` and `nodes`, `node` is always included in `nodes`.
  * Mapping JSON can also reshape layer-style tables (one row = a layer listing many vendors) into
    one card per vendor: skip_rows, text_replace, explode, derive, compose, exclude_names, name_aliases.
    See samples/real/README.md.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

from bi_schema import DOMAINS, ENUM_ALIASES, GLOBAL_ALIASES, SCHEMAS

TODAY = dt.date.today().isoformat()
BAD_CHARS = r'[\\/:*?"<>|#^\[\]]'
SEPS = set(";；,，、|\n")
OPEN, CLOSE = set("(（"), set(")）")
PAREN_TAIL = re.compile(r"\s*[(（]([^()（）]*)[)）]\s*等?\s*$")
EMPTY = {"", "nan", "none", "null", "n/a", "na", "-", "—", "tbd", "待定"}
TRUE_SET = {"true", "yes", "y", "1", "是", "有", "t"}
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)
NOTE_HEAD = "## 匯入備註"
ALIASES: dict[str, str] = {}  # norm_key(alias) -> canonical name


# ----------------------------------------------------------------------------- helpers
def norm_key(s) -> str:
    return re.sub(r"[\s_\-　()（）:：/／.]", "", str(s)).lower()


def canon(s) -> str:
    s = str(s).strip()
    return ALIASES.get(norm_key(s), s)


def sanitize(name) -> str:
    s = re.sub(BAD_CHARS, "-", str(name)).strip()
    return re.sub(r"\s+", " ", s).strip(" .")


def split_top(s):
    """Split on ; , 、 | newline, but not inside (...) or （...）."""
    parts, buf, depth = [], [], 0
    for ch in str(s):
        if ch in OPEN:
            depth += 1
        elif ch in CLOSE:
            depth = max(0, depth - 1)
        if depth == 0 and ch in SEPS:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def split_paren(part: str):
    """'Qorvo(GaN)' -> ('Qorvo', 'GaN');  '穩懋(3105)' -> ('穩懋', '3105')."""
    m = PAREN_TAIL.search(part)
    if m:
        return part[:m.start()].strip(), m.group(1).strip()
    return re.sub(r"等$", "", part).strip(), ""


def to_link_name(v) -> str:
    s = str(v).strip()
    m = re.fullmatch(r"\[\[(.+?)\]\]", s)
    if m:
        s = m.group(1).split("|")[0].split("/")[-1]
        s = re.sub(r"\.md$", "", s)
    else:
        s, _ = split_paren(s)
    return sanitize(canon(s))


def parse_date(s: str):
    s = s.strip()
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if not m:
        t = s.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-").replace(".", "-")
        m = (re.fullmatch(r"(\d{4})-?(\d{1,2})-?(\d{1,2})", t)
             or re.fullmatch(r"(\d{2,3})-(\d{1,2})-(\d{1,2})", t))  # ROC year, e.g. 115/10/13
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    if y < 200:
        y += 1911
    try:
        return dt.date(y, mo, d).isoformat()
    except ValueError:
        return None


def as_items(raw):
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]
    return split_top(raw)


def convert_domain_list(items, enum_aliases, keep_unknown=False):
    """Validate a multi-domain list.
    New data (keep_unknown=False): unknown values are dropped and reported, so typos never reach a card.
    Existing cards (keep_unknown=True): unknown values are kept so a merge never loses data."""
    out, bad = [], []
    for x in items:
        hit = next((d for d in DOMAINS if d.lower() == x.lower()), None)
        if hit is None:
            hit = next((e for a, e in enum_aliases.get("domain", {}).items() if norm_key(a) == norm_key(x)), None)
        if hit is None:
            bad.append(x)
            if not keep_unknown:
                continue
            hit = x
        if hit not in out:
            out.append(hit)
    return out, (f"domain: 不認得 {bad},允許值 {DOMAINS}" if bad else None)


def convert(key, spec, raw, enum_aliases, keep_unknown=False):
    """Return (value, warning). value None means 'empty / invalid'."""
    kind = spec["kind"]
    if raw is None:
        return None, None
    if kind in ("list", "linklist"):
        items = as_items(raw)
        if not items:
            return None, None
        if key == "domain" and kind == "list":
            return convert_domain_list(items, enum_aliases, keep_unknown)
        return ([to_link_name(x) for x in items] if kind == "linklist" else items), None
    s = str(raw).strip()
    if s.lower() in EMPTY:
        return None, None
    if kind in ("str", "virtual"):
        return (canon(s) if key in ("name", "product_name") else s), None
    if kind == "link":
        return to_link_name(s), None
    if kind == "int":
        m = re.search(r"-?\d+", s)
        if not m:
            return None, f"{key}: '{s}' 不是整數"
        n = int(m.group())
        rng = spec.get("range")
        if rng and not (rng[0] <= n <= rng[1]):
            return None, f"{key}: {n} 超出範圍 {rng[0]}-{rng[1]}"
        return n, None
    if kind == "bool":
        return s.lower() in TRUE_SET, None
    if kind == "date":
        d = parse_date(s)
        return (d, None) if d else (None, f"{key}: 無法解析日期 '{s}'")
    if kind == "enum":
        for e in spec["enum"]:
            if s.lower() == e.lower():
                return e, None
        for a, e in enum_aliases.get(key, {}).items():
            if norm_key(a) == norm_key(s):
                return e, None
        return None, f"{key}: '{s}' 不在允許值 {spec['enum']}"
    return s, None


# ----------------------------------------------------------------------------- readers
def read_text(path: Path) -> str:
    b = path.read_bytes()
    for enc in ("utf-8-sig", "cp950", "gb18030"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def clean_md(s: str) -> str:
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"<br\s*/?>", "; ", s, flags=re.I)
    return s.replace("**", "").replace("`", "").strip()


def parse_md_tables(text: str):
    """Return [(headers, rows)] for every pipe table in the text."""
    blocks, cur = [], []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            cur.append(line.strip())
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    tables = []
    for b in blocks:
        rows = [[clean_md(c) for c in ln.strip().strip("|").split("|")] for ln in b]
        if len(rows) < 2 or not all(re.fullmatch(r":?-{1,}:?", c.strip()) for c in rows[1] if c.strip()):
            continue
        headers = rows[0]
        tables.append((headers, [dict(zip(headers, r)) for r in rows[2:]]))
    return tables


def select_tables(tables, sel: str):
    sel = str(sel).strip()
    if sel == "all":
        return list(range(len(tables)))
    if sel.startswith("has:"):
        cols = [c.strip() for c in sel[4:].split("|") if c.strip()]
        return [i for i, (h, _) in enumerate(tables) if any(c in h for c in cols)]
    idx = []
    for part in sel.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            idx += list(range(int(a), int(b) + 1))
        elif part:
            idx.append(int(part))
    bad = [i for i in idx if i < 0 or i >= len(tables)]
    if bad:
        sys.exit(f"--table {bad} 超出範圍(共 {len(tables)} 個表格,編號從 0 起算)")
    return idx


def read_rows(path: Path, sheet=None, table="0"):
    ext = path.suffix.lower()
    if ext in (".csv", ".tsv", ".txt"):
        text = read_text(path)
        rdr = csv.DictReader(io.StringIO(text), delimiter="\t" if ext == ".tsv" else ",")
        return [{(k or "").strip(): v for k, v in r.items()} for r in rdr]
    if ext in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError:
            sys.exit("需要 openpyxl:pip install openpyxl")
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb[sheet] if sheet else wb.worksheets[0]
        it = ws.iter_rows(values_only=True)
        headers = [str(h).strip() if h is not None else "" for h in next(it)]
        rows = []
        for r in it:
            d = {}
            for h, c in zip(headers, r):
                if not h:
                    continue
                d[h] = "" if c is None else (c.isoformat()[:10] if isinstance(c, dt.date) else c)
            rows.append(d)
        return rows
    if ext in (".md", ".markdown"):
        tables = parse_md_tables(read_text(path))
        if not tables:
            sys.exit("Markdown 檔中找不到表格")
        idx = select_tables(tables, table)
        if not idx:
            sys.exit(f"沒有符合 --table {table!r} 的表格")
        print(f"使用表格:{idx}(共 {len(tables)} 個)")
        return [r for i in idx for r in tables[i][1]]
    if ext == ".json":
        data = json.loads(read_text(path))
        return data["rows"] if isinstance(data, dict) else data
    sys.exit(f"不支援的檔案格式:{ext}")


# ----------------------------------------------------------------------------- row transforms
def skip_hit(row, specs) -> bool:
    for s in specs:
        v = str(row.get(s["column"], "")).lower()
        if any(k.lower() in v for k in s["contains"]):
            return True
    return False


def explode_cell(raw, spec):
    s = str(raw).strip()
    if s.lower() in EMPTY:
        return []
    items = []
    for part in split_top(s):
        if spec.get("strip_after"):
            part = part.split(spec["strip_after"])[0].strip()
        base, paren = split_paren(part)
        if not base or base.lower() in EMPTY:
            continue
        ticker = paren if re.fullmatch(r"\d{4}", paren) else ""
        items.append({"name": canon(base), "ticker": ticker, "note": "" if ticker else paren})
    return items


def apply_derive(row, derive):
    for target, spec in derive.items():
        if str(row.get(target, "")).strip():
            continue
        text = " ".join(str(row.get(c, "")) for c in spec["from"])
        hits = []
        for pat, val in spec["map"].items():
            if re.search(pat, text, re.I):
                hits.append(val)
                if not spec.get("all"):
                    break
        if hits:
            row[target] = "、".join(dict.fromkeys(hits))


def render_line(line, row) -> str:
    names = re.findall(r"\{([^{}]+)\}", line)
    vals = {}
    for n in names:
        v = str(row.get(n, "") or "").strip()
        vals[n] = "" if v.lower() in EMPTY else v
    if names and not any(vals.values()):
        return ""
    return re.sub(r"\{([^{}]+)\}", lambda m: vals[m.group(1)], line)


def transform_rows(rows, cfg):
    skip = cfg.get("skip_rows", [])
    trs = cfg.get("text_replace", [])
    explode = cfg.get("explode", [])
    derive = cfg.get("derive", {})
    compose = cfg.get("compose", {})
    exclude = {norm_key(canon(x)) for x in cfg.get("exclude_names", [])}
    out = []
    for row in rows:
        row = dict(row)
        if skip and skip_hit(row, skip):
            continue
        for t in trs:
            if t["column"] not in row:
                continue
            val = str(row[t["column"]])
            for pat, rep in t["pairs"]:
                val = re.sub(pat, rep, val)
            row[t.get("into", t["column"])] = val
        if explode:
            candidates = []
            for spec in explode:
                if spec["column"] not in row:
                    continue
                for it in explode_cell(row[spec["column"]], spec):
                    nr = dict(row)
                    nr[spec["into"]] = it["name"]
                    nr["__ticker"], nr["__note"] = it["ticker"], it["note"]
                    nr.update(spec.get("set", {}))
                    candidates.append(nr)
        else:
            candidates = [row]
        for r in candidates:
            if exclude and norm_key(canon(r.get("name", ""))) in exclude:
                continue
            apply_derive(r, derive)
            for target, tmpl in compose.items():
                text = "\n".join(x for x in (render_line(l, r) for l in tmpl.split("\n")) if x)
                if text:
                    r[target] = text
            out.append(r)
    return out


def used_columns(cfg):
    used = set()
    for s in cfg.get("skip_rows", []):
        used.add(s["column"])
    for t in cfg.get("text_replace", []):
        used.add(t["column"])
    for s in cfg.get("explode", []):
        used.add(s["column"])
    for d in cfg.get("derive", {}).values():
        used.update(d["from"])
    for tmpl in cfg.get("compose", {}).values():
        used.update(re.findall(r"\{([^{}]+)\}", tmpl))
    return used


# ----------------------------------------------------------------------------- mapping & rows
def build_header_map(schema, headers, mapping_cols):
    lookup = {}
    for fname, spec in schema["fields"].items():
        for a in [fname, *spec["aliases"]]:
            lookup[norm_key(a)] = fname
    for a in GLOBAL_ALIASES["body"]:
        lookup.setdefault(norm_key(a), "body")
    result = {}
    for h in headers:
        if h in mapping_cols:
            result[h] = mapping_cols[h]
        elif norm_key(h) in lookup:
            result[h] = lookup[norm_key(h)]
    return result


def row_to_vals(schema, hmap, row, enum_aliases, warns, rowno):
    vals, body = {}, None
    for h, f in hmap.items():
        raw = row.get(h)
        if f == "body":
            s = "" if raw is None else str(raw).strip()
            if s and s.lower() not in EMPTY and (body is None or h == "body"):
                body = s
            continue
        if f not in schema["fields"]:
            warns.append(f"對應欄位 '{f}' 不存在於 schema(欄名 '{h}')")
            continue
        v, w = convert(f, schema["fields"][f], raw, enum_aliases)
        if w:
            warns.append(f"第 {rowno} 列 {w}")
        if v not in (None, [], "") and f not in vals:
            vals[f] = v
    return vals, body


def with_defaults(schema, vals, cli_defaults, enum_aliases):
    full = dict(vals)
    for k, spec in schema["fields"].items():
        if k in full:
            continue
        d = cli_defaults.get(k, spec["default"])
        if d is None:
            continue
        if d == "today":
            full[k] = TODAY
        else:
            v, _ = convert(k, spec, d, enum_aliases)
            if v not in (None, [], ""):
                full[k] = v
    return full


def card_filename(schema, vals):
    parts = []
    for k in schema["filename"]:
        v = vals.get(k)
        if not v:
            return None
        parts.append(str(v))
    return sanitize("-".join(parts))


def ensure_primary_node(schema, vals):
    """v4: when a card type has both `node` (primary) and `nodes` (all), keep node inside nodes."""
    f = schema["fields"]
    if "node" in f and "nodes" in f and vals.get("node"):
        vals["nodes"] = list(dict.fromkeys([*vals.get("nodes", []), vals["node"]]))


# ----------------------------------------------------------------------------- emitters
def emit_scalar(v) -> str:
    s = str(v)
    if (s == "" or s != s.strip() or re.search(r"[:#\[\]{}&*!|>'\"%@`,]", s) or s[0] in "-?"
            or s.lower() in {"true", "false", "null", "yes", "no", "on", "off", "~"}
            or re.fullmatch(r"[-+]?\d+(\.\d+)?", s) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", s)):
        return json.dumps(s, ensure_ascii=False)
    return s


def emit_value(kind, v) -> str:
    if kind == "int":
        return str(v)
    if kind == "bool":
        return "true" if v else "false"
    if kind == "date":
        return str(v)
    if kind == "link":
        return json.dumps(f"[[{v}]]", ensure_ascii=False)
    if kind == "linklist":
        return "[" + ", ".join(json.dumps(f"[[{x}]]", ensure_ascii=False) for x in v) + "]"
    if kind == "list":
        return "[" + ", ".join(emit_scalar(x) for x in v) + "]"
    return emit_scalar(v)


def emit_generic(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dt.date):
        return v.isoformat()[:10]
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(emit_generic(x) for x in v) + "]"
    if v is None:
        return ""
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False, default=str)
    return emit_scalar(v)


def emit_fm(typ, schema, vals, extras) -> str:
    out = ["---", f"type: {typ}"]
    for k, spec in schema["fields"].items():
        if spec["kind"] == "virtual" or k not in vals:
            continue
        out.append(f"{k}: {emit_value(spec['kind'], vals[k])}")
    for k, v in extras.items():
        out.append(f"{k}: {emit_generic(v)}")
    out.append("---")
    return "\n".join(out)


def compose_body(schema, body) -> str:
    """Put body text under the first heading; sections in body that start with '## ' replace the
    schema block with the same heading, any other '## ' sections are appended."""
    blocks = list(schema["body"])
    if not body:
        return "\n\n".join(blocks)
    parts = re.split(r"(?m)^(?=## )", body)
    lead = parts[0].strip()
    secs = {}
    for p in parts[1:]:
        secs[p.split("\n", 1)[0].strip()] = p.strip()
    out = []
    if not blocks and lead:
        out.append(lead)
    for i, b in enumerate(blocks):
        head = b.split("\n", 1)[0].strip()
        out.append(secs.pop(head) if head in secs else b)
        if i == 0 and lead:
            out.append(lead)
    out.extend(secs.values())
    return "\n\n".join(out)


def emit_template(typ, schema) -> str:
    name_field = schema["filename"][0] if len(schema["filename"]) == 1 else None
    lines = ["---", f"type: {typ}"]
    for k, spec in schema["fields"].items():
        kind, comment = spec["kind"], ""
        if kind == "virtual":
            continue
        if k == name_field:
            v = "<% tp.file.title %>"
        elif kind == "date" and spec["default"] == "today":
            v = '<% tp.date.now("YYYY-MM-DD") %>'
        elif kind in ("list", "linklist"):
            v = "[]"
            if k == "domain":
                comment = "  # " + " | ".join(DOMAINS)
        elif kind == "enum":
            v = spec["default"] or ""
            comment = "  # " + " | ".join(spec["enum"])
        elif kind == "bool":
            v = "false"
        elif kind == "int" and spec.get("range"):
            v, comment = "", f"  # {spec['range'][0]}-{spec['range'][1]}"
        else:
            v = ""
        lines.append(f"{k}: {v}{comment}".rstrip() if v == "" and not comment else f"{k}: {v}{comment}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + compose_body(schema, None) + "\n"


# ----------------------------------------------------------------------------- merge
def load_existing(schema, enum_aliases, text):
    m = FM_RE.match(text)
    if not m:
        return None
    try:
        import yaml
    except ImportError:
        sys.exit("合併既有卡片需要 PyYAML:pip install pyyaml")
    raw = yaml.safe_load(m.group(1)) or {}
    old, extras = {}, {}
    for k, v in raw.items():
        spec = schema["fields"].get(k)
        if spec and spec["kind"] != "virtual":
            cv, _ = convert(k, spec, v, enum_aliases, keep_unknown=True)
            if cv not in (None, [], ""):
                old[k] = cv
        elif k != "type":
            extras[k] = v
    return old, extras, m.group(2)


def merge_vals(schema, old, new, replace_lists, fill_only):
    out = dict(old)
    for k, v in new.items():
        kind = schema["fields"][k]["kind"]
        if kind in ("list", "linklist"):
            if k in old and (fill_only or not replace_lists):
                out[k] = list(old[k]) + [x for x in v if x not in old[k]]
            else:
                out[k] = v
        elif not (fill_only and k in old):
            out[k] = v
    return out


def add_source(extras, src):
    cur = extras.get("ingested_from")
    if cur is None:
        extras["ingested_from"] = src
    else:
        lst = list(cur) if isinstance(cur, (list, tuple)) else [cur]
        if src not in lst:
            lst.append(src)
        extras["ingested_from"] = lst[0] if len(lst) == 1 else lst


def append_note(old_body, body):
    if not body:
        return old_body, False
    lines = [l.strip() for l in body.split("\n") if l.strip()]
    if all(l in old_body for l in lines):
        return old_body, False
    bullet = "- " + " / ".join(lines)
    if NOTE_HEAD in old_body:
        return old_body.rstrip() + "\n" + bullet + "\n", True
    return old_body.rstrip() + "\n\n" + NOTE_HEAD + "\n" + bullet + "\n", True


# ----------------------------------------------------------------------------- main flow
def run(args):
    typ = args.type
    schema = SCHEMAS[typ]
    vault = Path(args.vault)
    inp = Path(args.input)
    enum_aliases = {k: dict(v) for k, v in ENUM_ALIASES.items()}
    mapping = {}
    if args.mapping:
        mapping = json.loads(read_text(Path(args.mapping)))
        for k, v in mapping.get("enum_aliases", {}).items():
            enum_aliases.setdefault(k, {}).update(v)
    for src in (json.loads(read_text(Path(args.name_aliases))) if args.name_aliases else {},
                mapping.get("name_aliases", {})):
        for k, v in src.items():
            ALIASES[norm_key(k)] = v
    cli_defaults = dict(mapping.get("defaults", {}))
    for d in args.default or []:
        k, _, v = d.partition("=")
        cli_defaults[k.strip()] = v.strip()
    cols = dict(mapping.get("columns", {}))
    if "ticker" in schema["fields"]:
        cols.setdefault("__ticker", "ticker")

    raw_rows = read_rows(inp, args.sheet, args.table)
    if not raw_rows:
        sys.exit("沒有資料列")
    rows = transform_rows(raw_rows, mapping)
    if not rows:
        sys.exit("轉換後沒有資料列(檢查 --table、skip_rows 與 explode 設定)")
    headers = list(dict.fromkeys(k for r in rows for k in r))
    hmap = build_header_map(schema, headers, cols)
    mode_label = args.mode + ("+fill-only" if args.fill_only and args.mode == "merge" else "")
    print(f"[{typ}] 輸入:{inp.name}  原始列:{len(raw_rows)} → 轉換後:{len(rows)}  "
          f"模式:{mode_label}{'  (dry-run)' if args.dry_run else ''}")
    print("欄位對應:" + "、".join(f"{h}→{f}" for h, f in hmap.items() if not h.startswith("__") or f == "ticker"))
    used = used_columns(mapping)
    unmapped = [h for h in headers if h not in hmap and h not in used and not h.startswith("__")]
    if unmapped:
        print("⚠ 未對應的欄位(將被忽略,可用 --mapping 指定):" + "、".join(unmapped))

    folder = vault / schema["folder"]
    existing_stems = {p.stem for p in vault.rglob("*.md")} if vault.exists() else set()
    pending: dict[Path, str] = {}
    touched: set[Path] = set()
    stats, warns, link_refs, preview = Counter(), [], {}, []

    def collect_links(fvals, fname):
        for k, spec in schema["fields"].items():
            if spec["kind"] in ("link", "linklist") and k in fvals:
                for t in ([fvals[k]] if spec["kind"] == "link" else fvals[k]):
                    link_refs.setdefault(t, set()).add(fname)

    for i, row in enumerate(rows, start=2):
        vals, body = row_to_vals(schema, hmap, row, enum_aliases, warns, i)
        if not vals and not body:
            continue
        ensure_primary_node(schema, vals)
        full = with_defaults(schema, vals, cli_defaults, enum_aliases)
        ensure_primary_node(schema, full)
        missing = [k for k, s in schema["fields"].items() if s["required"] and not full.get(k)]
        if missing:
            warns.append(f"第 {i} 列缺少必填欄位 {missing},已略過")
            stats["skipped"] += 1
            continue
        fname = card_filename(schema, full)
        if not fname:
            warns.append(f"第 {i} 列無法產生檔名,已略過")
            stats["skipped"] += 1
            continue
        path = folder / f"{fname}.md"
        rel = path.relative_to(vault)
        existing_text = pending.get(path)
        if existing_text is None and path.exists():
            existing_text = read_text(path)

        if existing_text is not None and args.mode == "skip":
            stats["skipped"] += 1
            print(f"- skipped   {rel}")
            continue

        if existing_text is not None and args.mode == "merge":
            loaded = load_existing(schema, enum_aliases, existing_text)
            if loaded is None:
                warns.append(f"{rel} 沒有 frontmatter,已略過")
                stats["skipped"] += 1
                continue
            old, extras, old_body = loaded

            # v4 guard: single-domain card types must not be silently merged across domains.
            dom_spec = schema["fields"].get("domain")
            if dom_spec and dom_spec["kind"] == "enum":
                new_dom, _ = convert("domain", dom_spec, vals.get("domain") or cli_defaults.get("domain"),
                                     enum_aliases)
                old_dom = old.get("domain", "wireless")  # cards without domain count as wireless
                if new_dom and new_dom != old_dom:
                    warns.append(f"{rel}: 同名卡屬於 {old_dom},本次匯入為 {new_dom},已略過"
                                 f"(請改名加領域前綴,例如 L1-Robot-Chipset)")
                    stats["skipped"] += 1
                    print(f"- skipped   {rel}  (領域衝突)")
                    continue

            old_text = emit_fm(typ, schema, old, extras)
            # v4: a multi-domain card without `domain` counts as wireless. Make that explicit before adding
            # another domain, otherwise adding robotics would silently remove it from the wireless view.
            if dom_spec and dom_spec["kind"] == "list" and vals.get("domain") and "domain" not in old:
                old["domain"] = ["wireless"]
            extras2 = dict(extras)
            if not args.no_source_tag:
                add_source(extras2, inp.name)
            merged = merge_vals(schema, old, vals, args.replace_lists,
                                fill_only=args.fill_only or path in touched)
            ensure_primary_node(schema, merged)
            new_body, body_changed = append_note(old_body, body)
            if emit_fm(typ, schema, merged, extras2) == old_text and not body_changed:
                stats["unchanged"] += 1
                touched.add(path)
                collect_links(merged, fname)
                if not args.quiet:
                    print(f"= unchanged {rel}")
                continue
            if "updated" in schema["fields"] and "updated" not in vals:
                merged["updated"] = TODAY
            text = emit_fm(typ, schema, merged, extras2) + "\n\n" + new_body.lstrip("\n")
            if not text.endswith("\n"):
                text += "\n"
            action, final_vals = "~ updated  ", merged
            stats["updated"] += 1
        else:
            extras_new = {} if args.no_source_tag else {"ingested_from": inp.name}
            text = emit_fm(typ, schema, full, extras_new) + "\n\n" + compose_body(schema, body) + "\n"
            action, final_vals = ("+ created  " if existing_text is None else "! replaced "), full
            stats["created" if existing_text is None else "replaced"] += 1

        print(f"{action} {rel}")
        pending[path] = text
        touched.add(path)
        if not args.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        if action.startswith("+") and not preview:
            preview.append(text)
        existing_stems.add(path.stem)
        collect_links(final_vals, fname)

    missing_targets = {t: refs for t, refs in link_refs.items() if t not in existing_stems}
    if missing_targets:
        print(f"⚠ 尚未建立的連結目標({len(missing_targets)}):")
        for t, refs in sorted(missing_targets.items()):
            r = sorted(refs)
            print(f"   [[{t}]] ← {', '.join(r[:4])}{' …' if len(r) > 4 else ''}")
    for w in warns:
        print("⚠", w)
    print("結果:" + "、".join(f"{k} {v}" for k, v in stats.items()) if stats else "結果:無變更")
    if args.dry_run and preview:
        print("\n--- 預覽第一張新卡 ---\n" + preview[0])


def main():
    ap = argparse.ArgumentParser(description="Ingest tabular data into BI vault cards")
    ap.add_argument("input", nargs="?", help="csv / tsv / xlsx / md / json")
    ap.add_argument("--type", choices=sorted(SCHEMAS), help="card type")
    ap.add_argument("--vault", default=".", help="path to the BI folder (default: .)")
    ap.add_argument("--mapping", help="mapping JSON (columns, defaults, enum_aliases, explode, derive, compose ...)")
    ap.add_argument("--name-aliases", help="JSON {alias: canonical name}, shared across runs")
    ap.add_argument("--sheet", help="xlsx sheet name (default: first)")
    ap.add_argument("--table", default="0",
                    help="markdown tables: index, range '0-6', list '1,3', 'all', or 'has:欄名|欄名' (default 0)")
    ap.add_argument("--mode", choices=["merge", "skip", "overwrite"], default="merge")
    ap.add_argument("--replace-lists", action="store_true", help="merge mode: replace lists instead of union")
    ap.add_argument("--fill-only", action="store_true",
                    help="merge mode: only fill empty fields, never overwrite an existing scalar (lists still union)")
    ap.add_argument("--default", action="append", metavar="KEY=VALUE", help="default for new cards (repeatable)")
    ap.add_argument("--no-source-tag", action="store_true", help="do not write ingested_from")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", "-q", action="store_true", help="hide 'unchanged' lines")
    ap.add_argument("--emit-templates", metavar="DIR", help="write Templater templates for all types")
    ap.add_argument("--list-types", action="store_true")
    args = ap.parse_args()

    if args.list_types:
        for t, s in SCHEMAS.items():
            print(f"{t}  ->  {s['folder']}/")
            for k, spec in s["fields"].items():
                extra = f" {spec['enum']}" if spec["enum"] else ""
                req = " *required" if spec["required"] else ""
                print(f"    {k}: {spec['kind']}{extra}{req}")
        return
    if args.emit_templates:
        d = Path(args.emit_templates)
        d.mkdir(parents=True, exist_ok=True)
        for t, s in SCHEMAS.items():
            tname = "T-" + "".join(p.capitalize() for p in t.split("_")) + ".md"
            (d / tname).write_text(emit_template(t, s), encoding="utf-8")
            print("wrote", d / tname)
        return
    if not args.input or not args.type:
        ap.error("需要 input 與 --type(或使用 --emit-templates / --list-types)")
    run(args)


if __name__ == "__main__":
    main()
