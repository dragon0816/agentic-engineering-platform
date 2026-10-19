"""Extract a conference slide deck (.pptx or .pdf) into a staging markdown file for distillation.

The output goes OUTSIDE the BI/ folder (default: ../_Inbox) so Dataview never indexes raw slide text.
It records per-slide title/text/tables/speaker notes, flags slides that look like test-solution
content, and lists known vendors/cards mentioned (from --vault). Then follow prompts/slide_distill.md.

OCR (PaddleOCR, optional): --ocr auto|on|off (default auto). Pictures inside pptx and scanned / image-heavy
PDF pages are read with PaddleOCR; text-poor pages that still contain pictures (diagrams) are flagged
"需要讀圖" and their images are saved under <out>/<name>_images/ so you can show them to Claude.

usage:  python bi_slides_extract.py talk.pptx [--vault ../BI] [--out ../_Inbox] [--ocr auto] [--ocr-lang ch]
install OCR (Windows):  py -m pip install paddlepaddle paddleocr
"""
import argparse, io, os, re, sys
from pathlib import Path

SOLUTION_HINTS = [
    "test setup", "setup", "block diagram", "dut", "测试方案", "測試方案", "解決方案", "solution", "測試系統",
    "test system", "chamber", "暗室", "緊縮場", "catr", "ota", "conformance", "一致性", "throughput", "吞吐量",
    "emulator", "模擬器", "analyzer", "分析儀", "tester", "測試儀", "automation", "自動化", "evm", "eirp", "trp",
    "protocol test", "calibration", "校正", "production test", "量產測試",
]



# ----------------------------------------------------------------------------- OCR (PaddleOCR)
MIN_IMG_PX = 120          # ignore tiny pictures (icons, logos)
MIN_PAGE_CHARS = 40       # a PDF page with fewer text chars is treated as scanned / image-only


class OcrEngine:
    """Thin wrapper over PaddleOCR (supports 2.x `ocr()` and 3.x `predict()` result formats)."""

    def __init__(self, lang="ch", min_conf=0.6):
        self.lang, self.min_conf, self._ocr = lang, min_conf, None

    def _init(self):
        if self._ocr is not None:
            return
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        from paddleocr import PaddleOCR
        try:      # PaddleOCR 3.x
            self._ocr = PaddleOCR(lang=self.lang, use_doc_orientation_classify=False,
                                  use_doc_unwarping=False, use_textline_orientation=True)
        except (TypeError, ValueError):   # PaddleOCR 2.x
            self._ocr = PaddleOCR(lang=self.lang, use_angle_cls=True, show_log=False)

    def read(self, pil_image):
        """-> (lines, n_low) ; lines are strings in reading order, low-confidence ones are dropped."""
        import numpy as np
        self._init()
        arr = np.array(pil_image.convert("RGB"))
        items = []   # (y, x, text, conf)
        if hasattr(self._ocr, "predict"):
            for res in self._ocr.predict(arr):
                data = res.json["res"] if hasattr(res, "json") and "res" in getattr(res, "json", {}) else res
                texts, scores = data.get("rec_texts", []), data.get("rec_scores", [])
                boxes = data.get("rec_polys", data.get("dt_polys", []))
                for i, t in enumerate(texts):
                    b = boxes[i] if i < len(boxes) else [[0, 0]]
                    ys, xs = [pt[1] for pt in b], [pt[0] for pt in b]
                    items.append((sum(ys) / len(ys), min(xs), t, float(scores[i]) if i < len(scores) else 1.0))
        else:
            for page in self._ocr.ocr(arr, cls=True) or []:
                for box, (t, c) in page or []:
                    ys, xs = [pt[1] for pt in box], [pt[0] for pt in box]
                    items.append((sum(ys) / len(ys), min(xs), t, float(c)))
        return group_lines(items, self.min_conf)


def group_lines(items, min_conf):
    """Merge boxes whose y centres are close into one line; drop low-confidence text."""
    keep = [i for i in items if i[3] >= min_conf and i[2].strip()]
    n_low = len(items) - len(keep)
    keep.sort(key=lambda i: (i[0], i[1]))
    lines, cur, cur_y = [], [], None
    for y, x, t, _ in keep:
        if cur_y is not None and abs(y - cur_y) > 14:
            lines.append("  ".join(tx for _, tx in sorted(cur)))
            cur = []
        cur.append((x, t.strip()))
        cur_y = y if not cur[:-1] else cur_y
    if cur:
        lines.append("  ".join(tx for _, tx in sorted(cur)))
    return lines, n_low


def pil_from_bytes(blob):
    from PIL import Image
    return Image.open(io.BytesIO(blob))


def known_names(vault):
    names = {}
    if not vault:
        return names
    for folder in ("Competitor", "Ecosystem", "Account", "Technology", "Concept"):
        d = Path(vault) / folder
        if d.exists():
            for f in d.glob("*.md"):
                names[f.stem] = folder
    return names


def hint_hits(text):
    low = text.lower()
    return sorted({h for h in SOLUTION_HINTS if h in low})


def extract_pptx(path):
    from pptx import Presentation
    prs = Presentation(path)
    slides = []
    for i, sl in enumerate(prs.slides, 1):
        title = sl.shapes.title.text.strip() if sl.shapes.title is not None and sl.shapes.title.has_text_frame else ""
        texts, tables, pics, images = [], [], 0, []

        def walk(shapes):
            nonlocal pics
            for sh in shapes:
                if sh.shape_type == 6:  # group
                    walk(sh.shapes)
                    continue
                if sh.shape_type == 13:
                    pics += 1
                    try:
                        images.append(sh.image.blob)
                    except Exception:
                        pass
                if getattr(sh, "has_table", False) and sh.has_table:
                    rows = [[c.text.strip().replace("\n", " ") for c in r.cells] for r in sh.table.rows]
                    tables.append(rows)
                elif sh.has_text_frame and sh != sl.shapes.title:
                    t = "\n".join(p.text.strip() for p in sh.text_frame.paragraphs if p.text.strip())
                    if t:
                        texts.append(t)
        walk(sl.shapes)
        notes = sl.notes_slide.notes_text_frame.text.strip() if sl.has_notes_slide else ""
        slides.append({"n": i, "title": title, "texts": texts, "tables": tables, "notes": notes, "pics": pics, "images": images, "render": None})
    return slides


def extract_pdf(path):
    import pdfplumber
    slides = []
    with pdfplumber.open(path) as pdf:
        for i, pg in enumerate(pdf.pages, 1):
            text = (pg.extract_text() or "").strip()
            lines = text.split("\n")
            tables = [[[(c or "").replace("\n", " ").strip() for c in r] for r in t] for t in pg.extract_tables()]
            slides.append({"n": i, "title": lines[0] if lines else "", "texts": ["\n".join(lines[1:])] if len(lines) > 1 else [],
                           "tables": tables, "notes": "", "pics": len(pg.images), "images": [],
                           "render": pg.to_image(resolution=170).original if (len(text) < MIN_PAGE_CHARS or pg.images) else None,
                           "chars": len(text)})
    return slides


def md_table(rows):
    if not rows:
        return ""
    w = max(len(r) for r in rows)
    rows = [r + [""] * (w - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * w]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)


def norm_txt(t):
    return re.sub(r"\s+", "", t).lower()


def run_ocr(slides, engine, mode):
    """Fill s['ocr'] = [(label, lines)], return (status, total_low_dropped)."""
    cand = [s for s in slides if s["images"] or s.get("render") is not None]
    for s in slides:
        s["ocr"] = []
    if mode == "off" or not cand:
        return ("off" if mode == "off" else "not-needed"), 0
    try:
        engine._init() if hasattr(engine, "_init") and engine._ocr is None else None
    except ImportError:
        if mode == "on":
            sys.exit("PaddleOCR 未安裝。請執行: py -m pip install paddlepaddle paddleocr")
        print("⚠ 未安裝 PaddleOCR,略過 OCR(安裝: py -m pip install paddlepaddle paddleocr)")
        return "unavailable", 0
    except Exception as e:   # model download / init failure
        if mode == "on":
            sys.exit(f"PaddleOCR 初始化失敗:{e}")
        print(f"⚠ PaddleOCR 初始化失敗,略過 OCR:{str(e)[:120]}")
        return "unavailable", 0
    low_total = 0
    for s in cand:
        have = norm_txt(" ".join([s["title"], *s["texts"], *[" ".join(sum(t, [])) for t in s["tables"]]]))
        if s["images"]:                                   # pptx: read each embedded picture
            for k, blob in enumerate(s["images"], 1):
                try:
                    im = pil_from_bytes(blob)
                except Exception:
                    continue
                if min(im.size) < MIN_IMG_PX:
                    continue
                lines, low = engine.read(im)
                low_total += low
                lines = [l for l in lines if norm_txt(l) not in have]
                if lines:
                    s["ocr"].append((f"圖片 {k}", lines))
        elif s.get("render") is not None:                  # pdf: read the rendered page
            lines, low = engine.read(s["render"])
            low_total += low
            lines = [l for l in lines if norm_txt(l) and norm_txt(l) not in have]
            if lines:
                s["ocr"].append(("整頁" if s.get("chars", 0) < MIN_PAGE_CHARS else "圖中文字", lines))
    return "paddleocr", low_total


def save_page_images(s, img_dir, stem):
    saved = []
    img_dir.mkdir(parents=True, exist_ok=True)
    if s["images"]:
        for k, blob in enumerate(s["images"], 1):
            try:
                im = pil_from_bytes(blob)
                if min(im.size) < MIN_IMG_PX:
                    continue
                f = img_dir / f"p{s['n']:02d}_{k}.png"
                im.convert("RGB").save(f)
                saved.append(f.name)
            except Exception:
                pass
    elif s.get("render") is not None:
        f = img_dir / f"p{s['n']:02d}.png"
        s["render"].convert("RGB").save(f)
        saved.append(f.name)
    return saved


def main(argv=None, engine=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--vault")
    ap.add_argument("--out", default="../_Inbox")
    ap.add_argument("--ocr", choices=["auto", "on", "off"], default="auto",
                    help="auto: 有 PaddleOCR 才用;on: 必須使用;off: 不做 OCR")
    ap.add_argument("--ocr-lang", default="ch", help="PaddleOCR 語言: ch(中英)、chinese_cht(繁中)、en")
    ap.add_argument("--min-conf", type=float, default=0.6, help="低於此信心度的 OCR 文字會被捨棄(預設 0.6)")
    ap.add_argument("--no-save-images", action="store_true", help="不另存『需要讀圖』頁的圖片")
    a = ap.parse_args(argv)
    src = Path(a.input)
    ext = src.suffix.lower()
    if ext == ".pptx":
        slides = extract_pptx(src)
    elif ext == ".pdf":
        slides = extract_pdf(src)
    else:
        sys.exit("only .pptx or .pdf supported (save .ppt as .pptx first)")
    engine = engine or OcrEngine(a.ocr_lang, a.min_conf)
    ocr_status, low_total = run_ocr(slides, engine, a.ocr)

    def page_text(s):
        return " ".join([s["title"], *s["texts"], s["notes"], *[" ".join(sum(t, [])) for t in s["tables"]],
                         *[" ".join(l) for _, l in s["ocr"]]])

    names = known_names(a.vault)
    full = "\n".join(page_text(s) for s in slides)
    mentioned = {n: k for n, k in names.items() if len(n) >= 3 and re.search(re.escape(n), full, re.I)}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    img_dir = out / f"{src.stem}_images"
    flagged, vision, ocr_pages, body = [], [], [], []
    for s in slides:
        hh = hint_hits(page_text(s))
        is_sol = len(hh) >= 2
        n_ocr = sum(len(l) for _, l in s["ocr"])
        needs_vision = s["pics"] > 0 and (is_sol or n_ocr < 3)
        tag = f"  ⟵ 疑似測試方案頁({', '.join(hh[:4])})" if is_sol else ""
        if is_sol:
            flagged.append(s["n"])
        if s["ocr"]:
            ocr_pages.append(s["n"])
        body.append(f"## [p{s['n']}] {s['title'] or '(無標題)'}{tag}")
        body += s["texts"]
        for t in s["tables"]:
            body.append(md_table(t))
        for label, lines in s["ocr"]:
            body.append(f"> OCR({label}):")
            body += [f">   {l}" for l in lines]
        if s["notes"]:
            body.append(f"> 講者備註:{s['notes']}")
        if s["pics"]:
            msg = f"_(含 {s['pics']} 張圖片" + (";OCR 讀不到足夠文字或為方案頁,**需要讀圖**" if needs_vision else "") + ")_"
            if needs_vision:
                vision.append(s["n"])
                if not a.no_save_images:
                    saved = save_page_images(s, img_dir, src.stem)
                    if saved:
                        msg += f" 圖片已存:{img_dir.name}/{', '.join(saved)}"
            body.append(msg)
        body.append("")
    dest = out / f"{src.stem}.md"
    head = ["---", "type: slide-extract", f"source_file: {src.name}", f"pages: {len(slides)}",
            f"ocr: {ocr_status}", f"ocr_pages: [{', '.join(map(str, ocr_pages))}]",
            f"needs_vision_pages: [{', '.join(map(str, vision))}]",
            f"possible_solution_pages: [{', '.join(map(str, flagged))}]",
            "mentioned_cards: [" + ", ".join(f'"[[{n}]]"' for n in sorted(mentioned)) + "]",
            "status: raw   # raw -> distilled", "---", "",
            "> 暫存檔(未蒸餾)。OCR 文字可能有錯(尤其是型號、數字),請對照原圖;依 tools/prompts/slide_distill.md 整理成卡片。",
            "> 不要把此檔放進 BI/ 資料夾。", ""]
    dest.write_text("\n".join(head + body), encoding="utf-8")
    print(f"wrote {dest}: {len(slides)} 頁, OCR={ocr_status}(讀到文字的頁 {ocr_pages},捨棄低信心 {low_total} 段), "
          f"需要讀圖的頁 {vision}, 疑似測試方案頁 {flagged}, 已知卡片 {sorted(mentioned)}")


if __name__ == "__main__":
    main()
