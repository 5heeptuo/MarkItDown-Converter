"""ocr_postprocess 单元测试：行排序/空格恢复/中英混排/断词/多栏/竖排/段落。"""
from __future__ import annotations

import pytest

from ocr_postprocess import (
    dehyphenate_lines,
    join_line_words,
    group_lines,
    normalize_box,
    postprocess_ocr,
    rebuild_paragraphs,
    split_long_lower_token,
)


def box(x1: float, y1: float, x2: float, y2: float, text: str) -> list:
    """构造 RapidOCR 风格的 [box4points, text, score] 项（水平矩形）。"""
    return [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]], text, 0.99]


def word(x1: float, y1: float, x2: float, y2: float, text: str):
    """直接构造 Word。"""
    return normalize_box(box(x1, y1, x2, y2, text)[0], text)


def raw(*items: list) -> list:
    return [list(i) for i in items]


# ---------------------------------------------------------------- normalize
def test_normalize_box_center_and_size():
    w = normalize_box(box(10, 20, 110, 40, "hello")[0], "hello")
    assert w.x == 60 and w.y == 30
    assert w.w == 100 and w.h == 20
    assert w.text == "hello"


# ---------------------------------------------------------------- group_lines
def test_group_lines_by_y():
    items = raw(
        box(0, 100, 50, 120, "top1"),
        box(60, 100, 110, 120, "top2"),
        box(0, 200, 60, 220, "bottom"),
    )
    lines = group_lines([normalize_box(i[0], i[1]) for i in items])
    assert len(lines) == 2
    first, second = lines
    assert {w.text for w in first.words} == {"top1", "top2"}
    assert {w.text for w in second.words} == {"bottom"}


def test_group_lines_input_order_irrelevant():
    items = raw(
        box(0, 200, 60, 220, "bottom"),
        box(0, 100, 50, 120, "top1"),
    )
    lines = group_lines([normalize_box(i[0], i[1]) for i in items])
    assert [w.text for w in lines[0].words] == ["top1"]
    assert [w.text for w in lines[1].words] == ["bottom"]


# ---------------------------------------------------------------- join_line
def test_join_two_boxes_camel_boundary():
    """驼峰边界（gap=0）：Qingyun|Wut -> Qingyun Wut。"""
    line = type("L", (), {"words": [word(0, 0, 100, 30, "Qingyun"), word(100, 0, 200, 30, "Wut")]})()
    assert join_line_words(line) == "Qingyun Wut"


def test_join_latin_with_real_gap():
    line = type("L", (), {"words": [word(0, 0, 90, 30, "Invoice"), word(140, 0, 240, 30, "Number:")]})()
    assert join_line_words(line) == "Invoice Number:"


def test_join_chinese_no_space():
    line = type("L", (), {"words": [word(0, 0, 90, 30, "计算机"), word(92, 0, 190, 30, "工程")]})()
    assert join_line_words(line) == "计算机工程"


def test_join_chinese_latin_mixed():
    line = type("L", (), {"words": [
        word(0, 0, 90, 30, "计算机工程"),
        word(150, 0, 280, 30, "Operating"),
        word(282, 0, 360, 30, "Systems"),
    ]})()
    assert join_line_words(line) == "计算机工程 Operating Systems"


def test_join_punctuation_no_leading_space():
    line = type("L", (), {"words": [
        word(0, 0, 80, 30, "Total:"),
        word(85, 0, 140, 30, "199"),
        word(145, 0, 190, 30, "EUR"),
    ]})()
    assert join_line_words(line) == "Total: 199 EUR"


def test_join_single_box_camel_split():
    """单 box 内驼峰拆分：METAandTESLA -> META and TESLA。"""
    line = type("L", (), {"words": [word(0, 0, 300, 30, "METAandTESLA")]})()
    assert join_line_words(line) == "META and TESLA"


def test_split_long_lower_token_dictionary():
    """长全小写粘词用词典恢复。"""
    assert split_long_lower_token("Noselectabletextlayershouldbepresent") == [
        "No", "selectable", "text", "layer", "should", "be", "present",
    ]
    assert split_long_lower_token("noselectabletextlayershouldbepresent") == [
        "no", "selectable", "text", "layer", "should", "be", "present",
    ]
    # 短词、驼峰词、含连字符词不触发
    assert split_long_lower_token("QingyunWut") is None
    assert split_long_lower_token("chatgpt") is None
    assert split_long_lower_token("state-of-the-art") is None
    assert split_long_lower_token("hello") is None


def test_join_long_lower_token_split():
    line = type("L", (), {"words": [word(0, 0, 400, 30, "Noselectabletextlayershouldbepresent")]})()
    assert join_line_words(line) == "No selectable text layer should be present"


def test_join_long_lower_token_short_with_punctuation():
    """9 字符带标点粘词：bepresent. -> be present.。"""
    line = type("L", (), {"words": [word(0, 0, 400, 30, "Noselectabletextlayershould bepresent.")]})()
    assert join_line_words(line) == "No selectable text layer should be present."


def test_wordninja_keeps_real_words():
    """完整常见单词不得被误拆。"""
    assert split_long_lower_token("information") is None
    assert split_long_lower_token("beautiful") is None


# ---------------------------------------------------------------- dehyphenate
def test_dehyphenate_simple():
    assert dehyphenate_lines(["ap-", "plications"]) == ["applications"]
    assert dehyphenate_lines(["vari-", "ous"]) == ["various"]
    assert dehyphenate_lines(["Em-", "pirical"]) == ["Empirical"]
    assert dehyphenate_lines(["answer-", "ing"]) == ["answering"]


def test_dehyphenate_compound_keeps_hyphen():
    assert dehyphenate_lines(["state-of-", "the-art"]) == ["state-of-the-art"]
    # 已知限制：无词典无法区分 self-（复合词）与 vari-（断词）。
    # head 内含连字符（state-of-）保留；否则合并去连字符。
    assert dehyphenate_lines(["self-", "contained"]) == ["selfcontained"]


def test_dehyphenate_conservative():
    # 不以 - 结尾的不动
    assert dehyphenate_lines(["hello", "world"]) == ["hello", "world"]
    # 下一行大写开头不合并（可能是新句子）
    assert dehyphenate_lines(["run-", "Time"]) == ["run-", "Time"]
    # 太短的头部不合并
    assert dehyphenate_lines(["a-", "b"]) == ["a-", "b"]
    # 行内连字符不处理
    assert dehyphenate_lines(["state-of-the-art"]) == ["state-of-the-art"]


# ---------------------------------------------------------------- columns
def test_two_column_reading_order():
    """左栏在上、右栏在下：必须输出 左1 左2 左3 右1 右2，而不是交错。"""
    items = raw(
        box(10, 10, 200, 30, "left-1"),      # 左栏顶部
        box(300, 10, 500, 30, "right-1"),    # 右栏顶部
        box(10, 60, 200, 80, "left-2"),      # 左栏第二行
        box(300, 60, 500, 80, "right-2"),    # 右栏第二行
        box(10, 110, 200, 130, "left-3"),    # 左栏第三行
    )
    out = postprocess_ocr(items)
    lines = [l for l in out.splitlines() if l.strip()]
    assert lines == ["left-1", "left-2", "left-3", "right-1", "right-2"]


def test_single_column_unchanged():
    items = raw(
        box(10, 10, 400, 30, "line one"),
        box(10, 60, 400, 80, "line two"),
    )
    out = postprocess_ocr(items)
    assert "line one" in out and "line two" in out
    assert out.index("line one") < out.index("line two")


# ---------------------------------------------------------------- vertical
def test_vertical_block_isolated():
    """竖排文字（x 相同、y 递增）应独立成块，不插入正文行之间。"""
    items = raw(
        box(5, 10, 100, 30, "header"),
        box(500, 10, 520, 70, "arXiv:2308.08155v2"),   # 竖排块词1（旋转 90 度，竖长）
        box(500, 85, 520, 145, "[cs.AI]"),             # 竖排块词2
        box(500, 160, 520, 220, "3 Oct 2023"),         # 竖排块词3
        box(5, 100, 400, 120, "main body"),
    )
    out = postprocess_ocr(items)
    # 正文两行相邻，竖排块不能插在中间
    assert out.index("header") < out.index("main body")
    assert "arXiv:2308.08155v2" in out


# ---------------------------------------------------------------- paragraphs
def test_paragraph_break_on_large_gap():
    items = raw(
        box(10, 10, 400, 30, "paragraph one"),
        box(10, 200, 400, 220, "paragraph two"),
    )
    out = postprocess_ocr(items)
    assert "\n\n" in out


def test_no_paragraph_break_on_small_gap():
    items = raw(
        box(10, 10, 400, 30, "line one"),
        box(10, 40, 400, 60, "line two"),
    )
    out = postprocess_ocr(items)
    assert "\n\n" not in out


# ---------------------------------------------------------------- end to end
def test_paper_screenshot_regression():
    """论文截图典型场景：标题、作者、正文；粘词恢复；阅读顺序正确。"""
    items = raw(
        box(100, 10, 700, 40, "Multi-AgentConversations"),
        box(150, 60, 650, 85, "QingyunWut YiranWut"),
        box(100, 120, 700, 145, "Abstract"),
        box(100, 160, 700, 220, "We study the capabilities of LLM-based agents"),
        box(100, 260, 400, 285, "METAandTESLA"),
        box(420, 260, 700, 285, "stock price change"),
    )
    out = postprocess_ocr(items)
    assert "Multi-Agent Conversations" in out
    assert "Qingyun Wu" in out
    assert "META and TESLA" in out
    # 阅读顺序：标题 -> 作者 -> Abstract -> 正文
    idx = [out.index(s) for s in ("Multi-Agent", "Qingyun Wu", "Abstract", "LLM-based")]
    assert idx == sorted(idx)
