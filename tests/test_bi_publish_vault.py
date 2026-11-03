"""A vault is not published with the dataset route: its working database may
hold commits nobody has pushed, and a snapshot would carry them."""

from __future__ import annotations

from pathlib import Path

from test_bi_publish import FakePublisher, _post, _status, _web
from test_bi_vault import _import, _row, _two_pcs
from test_bi_vault import _status as vault_status


def test_a_direct_publish_of_a_vault_dataset_is_refused(tmp_path: Path) -> None:
    _, vault_id, dataset, ws, _ = _two_pcs(tmp_path)
    _import(ws, dataset, _row("tsn", name="TSN"))
    assert vault_status(ws, vault_id)["ahead"] == 1  # a commit nobody has pushed
    publisher = FakePublisher()
    status, answer = _post(_web(ws, publisher), dataset=dataset, note="v")
    assert (status, answer["code"]) == (409, "dataset_is_vault")
    assert publisher.published == []
    assert not (ws / "bi" / dataset / "published.json").exists()


def test_the_status_of_a_vault_dataset_still_answers(tmp_path: Path) -> None:
    _, _, dataset, ws, _ = _two_pcs(tmp_path)
    status, answer = _status(_web(ws, FakePublisher()), dataset)
    assert status == 200 and answer["ok"] is True
