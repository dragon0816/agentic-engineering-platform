"""Look-alike CJK code points from PDF text extraction."""


def test_only_look_alike_cjk_code_points_are_folded() -> None:
    from common.cjk_text import fold_cjk_lookalikes

    assert fold_cjk_lookalikes("客⼾代碼，⼀筆（Ａ）") == "客戶代碼，一筆（Ａ）"
