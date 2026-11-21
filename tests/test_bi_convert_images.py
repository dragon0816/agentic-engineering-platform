"""BI step 1 keeps a document's pictures (owner 2026-11-20).

「convert 後，圖都不見了，我覺得要跟知識庫維護的 convert 處理有圖的文章一樣」: a PDF
page's images, a Word document's pictures and a slide's pictures are taken out with
the same core helpers as the LLM Wiki intake (`knowledge.office`), kept beside the
Markdown as `assets/<hash>.<ext>` and referenced in place; when the Host's model can
see images, each picture gets a description (core `knowledge.describe`) in the next
revision. All documents are fictional fixtures built in the test.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from test_bi_source_markdown import Jobs
from test_describe import VisionModel
from test_office import PNG, make_docx, make_pdf, make_pptx

from aep_bi.cards import convert, image_describe
from aep_bi.cards.ai_runs import AiRuntime
from aep_bi.cards.staging import Staging
from aep_bi.host.bi_cards_api import route

pytest.importorskip("pypdf")
pytest.importorskip("pptx")
pytest.importorskip("docx")

ACTOR = "tester"


def _call(tmp_path: Path, method: str, path: str, body: Any = None, ai: Any = None) -> Any:
    query = {"dataset": "demo"} if method == "GET" else {}
    return route(tmp_path, ACTOR, method, path, query, body, None, ai)


def _add(tmp_path: Path, name: str, data: bytes, ai: Any = None) -> dict[str, Any]:
    body = {"dataset": "demo", "name": name, "content_base64": base64.b64encode(data).decode()}
    status, reply = _call(tmp_path, "POST", "/api/bi/sources", body, ai)
    assert status == 200, reply
    return dict(reply)


def _images(markdown: str) -> list[str]:
    return [m["ref"] for line in markdown.split("\n") if (m := convert.IMAGE_LINE.match(line))]


@pytest.mark.parametrize(
    ("name", "data", "count"),
    [
        ("brief.pdf", make_pdf(["Page one text", "Page two text"], image=True), 1),
        ("report.docx", make_docx(), 1),
        ("deck.pptx", make_pptx(), 2),
    ],
    ids=["pdf", "docx", "pptx"],
)
def test_each_document_keeps_its_pictures_as_assets_in_place(
    name: str, data: bytes, count: int
) -> None:
    text, assets = convert.convert_with_assets(name, data)
    refs = [line for line in text.split("\n") if convert.IMAGE_LINE.match(line)]
    assert len(refs) == count
    assert refs[0].startswith("![圖 1](assets/")
    assert set(assets) == {convert.IMAGE_LINE.match(r)["ref"] for r in refs}  # type: ignore[index]
    assert all(blob for blob in assets.values())
    # Without a sink the text is what it was before pictures were kept.
    assert "assets/" not in convert.convert(name, data)


def test_pictures_sit_where_they_were_in_the_document() -> None:
    deck, _ = convert.convert_with_assets("deck.pptx", make_pptx())
    slide_one = deck.index("## 投影片 1")
    slide_two = deck.index("## 投影片 2")
    first, second = (deck.index(f"![圖 {n}]") for n in (1, 2))
    assert slide_one < first < slide_two < second
    word, _ = convert.convert_with_assets("report.docx", make_docx())
    assert word.index("After the table.") < word.index("![圖 1]") < word.index("## Closing")


def test_a_document_added_keeps_its_pictures_and_they_are_served(tmp_path: Path) -> None:
    reply = _add(tmp_path, "report.docx", make_docx())
    source = reply["source"]
    assert reply["images"] is None or reply["images"]["status"] in ("no_vision", "idle")
    _, view = _call(tmp_path, "GET", f"/api/bi/sources/{source['id']}/markdown")
    refs = _images(view["markdown"])
    assert len(refs) == 1
    staging = Staging(tmp_path, "demo")
    picture = staging.asset_file(source["id"], refs[0].split("/", 1)[1])
    assert picture.read_bytes() == PNG
    assert picture.parent == tmp_path / "bi" / "demo" / "markdown" / source["id"] / "assets"
    # No model: the picture is kept and counted as still without a description.
    _, shown = _call(tmp_path, "GET", f"/api/bi/sources/{source['id']}/images")
    assert shown["images"] == {"status": "idle", "done": 0, "total": 1, "pending": 1}


def test_a_vision_model_describes_each_picture_in_a_new_revision(tmp_path: Path) -> None:
    jobs, model = Jobs(), VisionModel()
    ai = AiRuntime(model=lambda: (model, "vision-model"), background=jobs, vision=lambda: True)
    reply = _add(tmp_path, "deck.pptx", make_pptx(), ai)
    source_id = reply["source"]["id"]
    # The deck shows one fictional picture twice: one asset, asked about once.
    assert reply["images"]["status"] == "running" and reply["images"]["total"] == 1
    jobs.run_all()
    _, shown = _call(tmp_path, "GET", f"/api/bi/sources/{source_id}/images")
    assert shown["images"]["status"] == "finished"
    assert (shown["images"]["described"], shown["images"]["failed"]) == (1, 0)
    assert shown["images"]["rev"] == 2 and shown["images"]["done"] == 1
    _, view = _call(tmp_path, "GET", f"/api/bi/sources/{source_id}/markdown")
    assert view["revision"]["note"] == "圖片說明" and view["revision"]["origin"] == "conversion"
    lines = [line for line in view["markdown"].split("\n") if line.strip()]
    assert len(_images(view["markdown"])) == 2
    for ref in _images(view["markdown"]):
        under = lines[lines.index(next(x for x in lines if ref in x)) + 1]
        assert under.startswith("> 圖片說明（vision-model）：A chart (")
    assert image_describe.pending(view["markdown"]) == []
    assert len(model.requests) == 1  # the same picture twice is asked once


def test_a_model_that_cannot_see_keeps_the_pictures_without_descriptions(tmp_path: Path) -> None:
    jobs, model = Jobs(), VisionModel()
    ai = AiRuntime(model=lambda: (model, "text-only"), background=jobs, vision=lambda: False)
    reply = _add(tmp_path, "report.docx", make_docx(), ai)
    assert reply["images"]["status"] == "no_vision" and reply["images"]["pending"] == 1
    assert jobs.pending == [] and model.requests == []
    status, refused = _call(
        tmp_path, "POST", f"/api/bi/sources/{reply['source']['id']}/images", {"dataset": "demo"}, ai
    )
    assert status == 409 and refused["code"] == "vision_unavailable"


def test_a_document_converted_before_pictures_gets_them_when_added_again(tmp_path: Path) -> None:
    staging = Staging(tmp_path, "demo")
    data = make_docx()
    old = convert.convert("report.docx", data)
    source = staging.add_source(
        "report.docx",
        content_base64=base64.b64encode(data).decode(),
        actor=ACTOR,
    )
    # Pretend revision 1 came from the converter that dropped pictures.
    staging.add_markdown(
        source["id"],
        old,
        origin="conversion",
        note="轉檔",
        actor=ACTOR,
        base_rev=1,
        converter="aep.bi.convert/1",
    )
    again = _add(tmp_path, "report.docx", data)
    assert again["source"]["already"] is True and again["source"]["reconverted"] is True
    _, view = _call(tmp_path, "GET", f"/api/bi/sources/{source['id']}/markdown")
    assert view["current_rev"] == 3 and len(_images(view["markdown"])) == 1
    assert view["revision"]["note"] == "重新轉檔（保留圖片）"
    # A person's edit is never replaced.
    staging.add_markdown(source["id"], "mine", origin="edit", note="", actor=ACTOR, base_rev=3)
    assert _add(tmp_path, "report.docx", data)["source"]["reconverted"] is False


def test_an_unknown_picture_name_is_refused(tmp_path: Path) -> None:
    source = _add(tmp_path, "report.docx", make_docx())["source"]
    staging = Staging(tmp_path, "demo")
    for name in ("../staging.sqlite", "0123456789abcdef.png", "x.png"):
        with pytest.raises(Exception) as caught:
            staging.asset_file(source["id"], name)
        assert getattr(caught.value, "code", "") == "asset_unknown"
