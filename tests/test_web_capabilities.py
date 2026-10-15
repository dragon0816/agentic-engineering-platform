"""`web/read`, `web/act` and `data/select` as Workflow building blocks (W2)."""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from test_gateway import request

from capabilities.runtime import CapabilityRefused
from capabilities.web.handlers import (
    ACT_SPEC,
    READ_SPEC,
    SELECT_SPEC,
    SelectHandler,
    SelectRequest,
    WebHostBinding,
    WebScriptHandler,
)
from evaluation.sop_practice import PracticeSite
from integrations.web_script import WebScript

SEARCH = [
    {"do": "open", "url": "{site}/"},
    {"do": "fill", "target": {"label": "客戶代碼", "kind": "field"}, "value": "{customer}"},
    {"do": "click", "target": {"label": "查詢", "kind": "button"}},
    {"do": "read_table", "table": "#orders", "save_as": "orders"},
]
NOTIFY = [
    {"do": "open", "url": "{site}/orders?customer={customer}"},
    {
        "do": "click",
        "target": {"label": "標記已通知", "kind": "button"},
        "row": {"table": "#orders", "column": "訂單號", "equals": "{item}"},
    },
]


def call(handler: object, inputs: object) -> object:
    return asyncio.run(handler(request("run"), inputs))  # type: ignore[operator]


def test_select_keeps_matching_rows_and_returns_one_column() -> None:
    rows = [
        {"訂單號": "A", "狀態": "延遲", "通知": "標記已通知"},
        {"訂單號": "B", "狀態": "準時", "通知": ""},
        {"訂單號": "C", "狀態": "延遲", "通知": "已通知"},
    ]
    chosen = call(
        SelectHandler(),
        SelectRequest(rows=rows, where={"狀態": "延遲", "通知": "標記已通知"}, take="訂單號"),
    )
    assert chosen.values == ("A",) and chosen.count == 1  # type: ignore[attr-defined]
    with pytest.raises(CapabilityRefused) as refused:
        call(SelectHandler(), SelectRequest(rows=rows, take="客戶"))
    assert refused.value.code == "data_column_missing"


def test_the_specs_say_what_each_block_may_do() -> None:
    assert READ_SPEC.side_effect == "read" and SELECT_SPEC.side_effect == "read"
    assert ACT_SPEC.side_effect == "external_side_effect"
    assert ACT_SPEC.policy.approval_required


@pytest.fixture(scope="module")
def site() -> Iterator[PracticeSite]:
    served = PracticeSite()
    served.start()
    yield served
    served.close()


@pytest.mark.skipif(sys.platform != "win32", reason="drives the installed Edge")
def test_read_select_then_act_on_the_practice_site(site: PracticeSite, tmp_path: Path) -> None:
    from integrations.browser import browser_path

    if browser_path() is None:
        pytest.skip("no Chromium browser installed")
    binding = WebHostBinding(allowed_origins=(site.url,))
    values = {"site": site.url, "customer": "C001"}
    read = call(
        WebScriptHandler(binding, tmp_path / "profile", "read"),
        WebScript.model_validate({"actions": SEARCH, "values": values}),
    )
    rows = read.data["orders"]  # type: ignore[attr-defined]
    delayed = call(
        SelectHandler(),
        SelectRequest(rows=rows, where={"狀態": "延遲", "通知": "標記已通知"}, take="訂單號"),
    )
    act = call(
        WebScriptHandler(binding, tmp_path / "profile", "act"),
        WebScript.model_validate(
            {"actions": NOTIFY, "values": values, "for_each": list(delayed.values)}
        ),
    )  # type: ignore[attr-defined]
    assert act.done == ("SO-1002", "SO-1004")  # type: ignore[attr-defined]
    with urllib.request.urlopen(site.url + "/state.json") as reply:
        assert json.loads(reply.read())["notified"] == ["SO-1002", "SO-1004"]
    with pytest.raises(CapabilityRefused) as refused:
        call(
            WebScriptHandler(binding, tmp_path / "profile", "read"),
            WebScript.model_validate({"actions": [{"do": "open", "url": "https://example.com/"}]}),
        )
    assert refused.value.code == "web_origin_not_allowed"


def test_a_host_with_web_installs_the_blocks(tmp_path: Path) -> None:
    from test_host_wiring import ready

    from host_runtime.host import build_runtime

    plain, layout = ready(tmp_path)
    config = plain.model_copy(update={"web": WebHostBinding(allowed_origins=("http://x:1",))})
    with build_runtime(config, layout=layout) as runtime:
        installed = runtime.agent.gateway.bridge.installed
        assert all(
            installed.get(spec.identity) is not None for spec in (READ_SPEC, ACT_SPEC, SELECT_SPEC)
        )
    with build_runtime(plain, layout=layout) as runtime:
        assert runtime.agent.gateway.bridge.installed.get(READ_SPEC.identity) is None
