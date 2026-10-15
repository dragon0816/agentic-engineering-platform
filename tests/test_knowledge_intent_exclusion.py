"""D1 (coding_v1, 2026-10-06): a task naming local work is not a Knowledge question."""

import pytest

from host_runtime.web import names_local_work


@pytest.mark.parametrize(
    "message",
    [
        "CMP180 的選配規格是什麼？",
        "R&S FSW 的頻率範圍和價格？",
        "CMX500 支援 5G NR 嗎",
        "比較 FSV3000 與 FSVA3000 的規格差異",
        "Wi-Fi 7 測試需要哪些產品？",
    ],
)
def test_knowledge_questions_still_route_by_intent(message: str) -> None:
    assert not names_local_work(message)


@pytest.mark.parametrize(
    "message",
    [
        "從提供的 catalog URL 取得全部產品名稱、價格：http://127.0.0.1:5000/t10/catalog",
        "從 specs.md 的三個產品段落抽出 Model、Frequency",
        r"工作目錄：C:\Users\Chi_L\work\T07",
        r"請讀取 \\server\share\specs 的資料",
        "把結果輸出到 products.xlsx",
        "C:/data/input 裡的檔案",
    ],
)
def test_messages_that_name_local_work_go_to_the_model(message: str) -> None:
    assert names_local_work(message)
