"""OCR 结果后处理：栏检测、行排序、空格恢复、断词合并、段落重建。

输入：RapidOCR 返回的原始结果（每项 [box4points, text, score]）。
输出：重建后的 Markdown 文本。

原则：
- 中文字符之间不插空格；英文单词之间恢复空格；中英之间允许空格。
- 保守处理：宁可少拆，不破坏原文。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Word:
    """归一化后的 OCR 词（box 中心 + 宽高 + 文本）。"""

    x: float  # 中心 x
    y: float  # 中心 y
    w: float  # 宽度
    h: float  # 高度
    text: str

    @property
    def x_left(self) -> float:
        return self.x - self.w / 2

    @property
    def x_right(self) -> float:
        return self.x + self.w / 2


@dataclass
class Line:
    """同一视觉行的一组词（已按 x 排序）。"""

    words: list[Word] = field(default_factory=list)
    text: str = ""

    @property
    def x_min(self) -> float:
        return min(w.x_left for w in self.words)

    @property
    def x_max(self) -> float:
        return max(w.x_right for w in self.words)

    @property
    def x_center(self) -> float:
        return (self.x_min + self.x_max) / 2

    @property
    def y(self) -> float:
        return sum(w.y for w in self.words) / len(self.words)

    @property
    def height(self) -> float:
        return max(w.h for w in self.words)


_CJK_RANGES = (
    (0x4E00, 0x9FFF),   # 中日韩统一表意文字
    (0x3000, 0x303F),   # 中日韩标点
    (0xFF00, 0xFFEF),   # 全角字符
)


def _is_cjk_char(ch: str) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in _CJK_RANGES)


def has_cjk(text: str) -> bool:
    return any(_is_cjk_char(ch) for ch in text)


# ---------------------------------------------------------------- normalize
def normalize_box(box: list, text: str) -> Word:
    """把 RapidOCR 4 点 box 归一化为 Word。

    box 顺序：[左上, 右上, 右下, 左下]（允许轻微倾斜）。
    """
    (x1, y1), (x2, _y2), (x3, y3), (x4, y4) = box
    w = ((x2 - x1) + (x3 - x4)) / 2
    h = ((y3 - _y2) + (y4 - y1)) / 2
    return Word(
        x=(x1 + x3) / 2,
        y=(y1 + y3) / 2,
        w=abs(w) or 1.0,
        h=abs(h) or 1.0,
        text=text,
    )


# ---------------------------------------------------------------- vertical
def _extract_vertical_blocks(words: list[Word]) -> tuple[list[Word], list[str]]:
    """检测竖排文字链（x 几乎相同、y 递增的连续词），从正文中隔离。

    返回 (剩余词, 竖排块文本列表)。
    """
    if len(words) < 3:
        return words, []
    chains: list[list[Word]] = []
    current = [words[0]]
    for w in words[1:]:
        prev = current[-1]
        x_close = abs(w.x - prev.x) < max(w.w, prev.w) * 0.8
        y_follow = w.y > prev.y and (w.y - prev.y) < max(w.h, prev.h) * 2.0
        if x_close and y_follow:
            current.append(w)
        else:
            chains.append(current)
            current = [w]
    chains.append(current)

    vertical: list[list[Word]] = []
    for chain in chains:
        if len(chain) < 3:
            continue
        # 竖排文字（旋转 90 度）的 box 一定是竖长的；横长词组成的链是正文列
        if any(w.h <= w.w * 1.2 for w in chain):
            continue
        span_y = chain[-1].y - chain[0].y
        span_x = max(w.x for w in chain) - min(w.x for w in chain)
        avg_w = sum(w.w for w in chain) / len(chain)
        if span_y > 3 * max(w.h for w in chain) and span_x < avg_w * 1.2:
            vertical.append(chain)
    removed = {id(w) for chain in vertical for w in chain}
    rest = [w for w in words if id(w) not in removed]
    blocks = [" ".join(w.text for w in chain) for chain in vertical]
    return rest, blocks


# ---------------------------------------------------------------- columns
def split_columns_words(
    words: list[Word], page_w: float, depth: int = 0
) -> list[list[Word]]:
    """词级别多栏检测：x 中心分布出现大空隙 -> 拆成左右两栏。

    必须在行分组之前执行，否则左右两栏的平行行会被误并为一行。
    递归拆分（最多 3 栏）。
    """
    if len(words) < 4 or page_w <= 0 or depth >= 2:
        return [words]
    centers = sorted(w.x_left for w in words)
    gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
    max_gap = max(gaps)
    if max_gap <= 0.25 * page_w:
        return [words]
    idx = gaps.index(max_gap)
    split = (centers[idx] + centers[idx + 1]) / 2
    left = [w for w in words if w.x_left < split]
    right = [w for w in words if w.x_left >= split]
    if not left or not right:
        return [words]
    return [
        *split_columns_words(left, page_w, depth + 1),
        *split_columns_words(right, page_w, depth + 1),
    ]


# ---------------------------------------------------------------- lines
def group_lines(words: list[Word]) -> list[Line]:
    """按 y 中心聚类成行（words 需已按 y 排序）。"""
    if not words:
        return []
    words = sorted(words, key=lambda w: (w.y, w.x))
    lines: list[Line] = []
    current = [words[0]]
    for w in words[1:]:
        prev = current[-1]
        if abs(w.y - prev.y) < max(w.h, prev.h) * 0.6:
            current.append(w)
        else:
            lines.append(Line(words=sorted(current, key=lambda x: x.x)))
            current = [w]
    lines.append(Line(words=sorted(current, key=lambda x: x.x)))
    return lines


# ---------------------------------------------------------------- camel split
def _ends_with_upper_run(chars: list[str]) -> bool:
    """chars 以 >=2 个连续大写字母结尾。"""
    count = 0
    for ch in reversed(chars):
        if ch.isupper():
            count += 1
        else:
            break
    return count >= 2


def split_camel_words(text: str) -> list[tuple[str, bool]]:
    """拆分驼峰粘词；返回 [(片断, 片断前是否原本有空格)]。

    QingyunWut -> [(Qingyun, False), (Wut, False)]
    METAandTESLA -> [(META, False), (and, False), (TESLA, False)]
    "QingyunWut YiranWut" -> [(Qingyun, F), (Wut, F), (Yiran, T), (Wut, F)]
    """
    segments: list[tuple[str, bool]] = []
    # 先按空白分段
    for piece in re_split_ws(text):
        leading_space = piece[0]
        part = piece[1]
        if not part:
            continue
        pieces = _split_camel_one(part)
        for j, p in enumerate(pieces):
            segments.append((p, leading_space or j > 0))
    return segments


_WORDNINJA = None


def _get_wordninja():
    """懒加载 wordninja（内置英文词表，用于长粘词恢复）。"""
    global _WORDNINJA
    if _WORDNINJA is None:
        import wordninja

        _WORDNINJA = wordninja
    return _WORDNINJA


def split_long_lower_token(text: str) -> list[str] | None:
    """对长小写/首字母大写粘词尝试词典分词（Noselectabletextlayershould）。

    保守条件：长度 >= 9、无连字符、无内部大写转换（驼峰已由
    split_camel_words 处理）、分词结果每词长度 >= 2。不可靠时返回 None。
    """
    tail = ""
    while text and not text[-1].isalnum():
        tail = text[-1] + tail
        text = text[:-1]
    if len(text) < 9 or "-" in text:
        return None
    if not (text.islower() or (text[0].isupper() and text[1:].islower())):
        return None
    try:
        words = _get_wordninja().split(text.lower())
    except Exception:  # noqa: BLE001
        return None
    if len(words) < 2 or any(len(w) < 2 for w in words):
        return None
    if tail:
        words[-1] = words[-1] + tail
    if text[0].isupper() and words:
        words[0] = words[0][:1].upper() + words[0][1:]
    return words


def re_split_ws(text: str) -> list[tuple[bool, str]]:
    """按空白切分：返回 [(是否有前导空格, 段)]。"""
    result: list[tuple[bool, str]] = []
    current = ""
    leading = False
    for ch in text:
        if ch.isspace():
            if current:
                result.append((leading, current))
                current = ""
                leading = True
            else:
                leading = True
        else:
            current += ch
    if current:
        result.append((leading, current))
    return result


def _split_camel_one(text: str) -> list[str]:
    """单段（无空白）驼峰拆分。"""
    if not text:
        return []
    parts: list[str] = []
    current: list[str] = []
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if current:
            prev = current[-1]
            alpha_idx = -1
            for idx in range(len(current) - 1, -1, -1):
                if current[idx].isalpha():
                    alpha_idx = idx
                    break
            last_alpha = current[alpha_idx] if alpha_idx >= 0 else ""
            prev_word_len = sum(1 for c in current if c.isalnum())

            if ch.isupper() and prev.isalpha() and i + 1 < n and text[i + 1].islower():
                # 规则1：字母小写 -> 大写 -> 小写（驼峰），前词足够长
                if last_alpha.islower() and prev_word_len >= 3:
                    parts.append("".join(current))
                    current = []
            elif ch.islower() and last_alpha.isupper() and _ends_with_upper_run(current):
                # 规则2：大写组尾 -> 小写（META|and）
                parts.append("".join(current))
                current = []
            elif ch.isupper() and prev.islower() and not (i + 1 < n and text[i + 1].islower()):
                # 规则3：小写 -> 全大写组到段尾（and|TESLA）
                j = i
                while j < n and text[j].isupper():
                    j += 1
                if j - i >= 2:
                    parts.append("".join(current))
                    current = []
        current.append(ch)
        i += 1
    if current:
        parts.append("".join(current))
    return parts


# ---------------------------------------------------------------- join line
def _char_width(line: Line) -> float:
    widths = [
        w.w / max(1, len(w.text))
        for w in line.words
        if any(c.isalpha() or c.isdigit() for c in w.text)
    ]
    if not widths:
        return 10.0
    widths.sort()
    return widths[len(widths) // 2]


def _need_space(a: str, b: str, gap: float | None, char_w: float) -> bool:
    """判断两个相邻 token 之间是否需要空格。"""
    if gap is None:
        # 同一 box 内拆出的片断（无原始空格）：
        # 驼峰拆分点插空格；若拆自空白段则由 was_space 决定
        return True
    a_cjk = has_cjk(a)
    b_cjk = has_cjk(b)
    if a_cjk or b_cjk:
        if a_cjk and b_cjk:
            return False
        return True  # 中英混合：插空格
    a_last = a[-1]
    b_first = b[0]
    if b_first in ".,;:!?，。；：！？、":
        return False  # 标点前不空格
    if a_last in ".,;:!?，。；：！？、":
        return True  # 标点后空格
    if b_first.isupper():
        return True  # 大写开头：新词
    if a_last.isupper() and b_first.islower():
        return True
    # 小写接小写：用水平 gap 判断（避免把被切断的单词拆开）
    return gap > 0.3 * char_w


def join_line_words(line: Line) -> str:
    """把一行内词序列重建为文本（含驼峰拆分与空格恢复）。"""
    if not line.words:
        return ""
    char_w = _char_width(line)
    tokens: list[tuple[str, float | None, bool]] = []  # (text, gap, was_space)
    for index, word in enumerate(line.words):
        parts = split_camel_words(word.text)
        expanded: list[tuple[str, bool]] = []
        for part, had_space in parts:
            long_split = split_long_lower_token(part)
            if long_split is not None:
                for j, piece in enumerate(long_split):
                    expanded.append((piece, had_space or j > 0))
            else:
                expanded.append((part, had_space))
        for part, had_space in expanded:
            if index > 0 and not had_space:
                gap = word.x_left - line.words[index - 1].x_right
            else:
                gap = None
            tokens.append((part, gap, had_space))

    out = tokens[0][0]
    for i in range(1, len(tokens)):
        text, gap, was_space = tokens[i]
        if was_space:
            out += " "
        elif _need_space(tokens[i - 1][0], text, gap, char_w):
            out += " "
        out += text
    return out


# ---------------------------------------------------------------- paragraphs
def rebuild_paragraphs(lines: list[Line]) -> str:
    """按行间垂直间距重建段落（大 gap -> 空行）。"""
    if not lines:
        return ""
    heights = [l.height for l in lines]
    med_h = sorted(heights)[len(heights) // 2] or 1.0
    parts: list[str] = []
    prev_bottom: float | None = None
    for line in lines:
        top = line.y - line.height / 2
        if prev_bottom is not None and top - prev_bottom > 1.2 * med_h:
            parts.append("")
        parts.append(line.text)
        prev_bottom = line.y + line.height / 2
    return "\n".join(parts)


# ---------------------------------------------------------------- dehyphenate
def _dehyphenate_one(prev: str, nxt: str | None) -> str | None:
    """行尾断词合并：ap- + plications -> applications；state-of- + the-art -> state-of-the-art。"""
    if nxt is None:
        return None
    if not prev.endswith("-") or len(prev) < 3:
        return None
    head = prev[:-1]
    if not head or not head[-1].isalpha() or not head[-1].islower():
        return None
    if not nxt or not nxt[0].islower():
        return None
    # 复合词连字符（head 内含 -，如 state-of-）保留连字符；
    # 否则视为行中断词（ap- + plications -> applications）
    if "-" in head:
        return head + "-" + nxt
    return head + nxt


def dehyphenate_lines(lines: list[str]) -> list[str]:
    """跨行断词合并（空行打断，不跨段落合并）。"""
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if i + 1 < len(lines) and lines[i + 1].strip():
            merged = _dehyphenate_one(line.rstrip(), lines[i + 1].strip())
            if merged is not None:
                out.append(merged)
                i += 2
                continue
        out.append(line)
        i += 1
    return out


# ---------------------------------------------------------------- entry
def postprocess_ocr(raw_results: list | None, min_score: float = 0.5) -> str:
    """OCR 原始结果 -> 重建后的 Markdown 文本。"""
    if not raw_results:
        return ""
    words: list[Word] = []
    for item in raw_results:
        if not item or len(item) < 2:
            continue
        try:
            score = item[2] if len(item) > 2 else 1.0
            if score < min_score:
                continue
            words.append(normalize_box(item[0], str(item[1])))
        except (TypeError, ValueError, IndexError):
            continue
    if not words:
        return ""
    words.sort(key=lambda w: (w.y, w.x))
    words, vertical_blocks = _extract_vertical_blocks(words)

    # 词级分栏（必须先于行分组）
    page_w = 0.0
    if words:
        page_w = max(w.x_right for w in words) - min(w.x_left for w in words)
    wide = [w for w in words if w.w > 0.8 * page_w] if page_w > 0 else []
    rest = [w for w in words if w not in wide]
    body_w = 0.0
    if rest:
        body_w = max(w.x_right for w in rest) - min(w.x_left for w in rest)
    columns = split_columns_words(rest, body_w or page_w)

    ordered_lines: list[Line] = []
    for column in columns:
        for line in group_lines(column):
            ordered_lines.append(line)
    # 宽行（页眉等）置顶
    wide_lines: list[Line] = []
    if wide:
        wide_lines = group_lines(wide)
    ordered_lines = wide_lines + ordered_lines

    for line in ordered_lines:
        line.text = join_line_words(line)

    text = rebuild_paragraphs(ordered_lines)
    text = "\n".join(dehyphenate_lines(text.splitlines()))
    if vertical_blocks:
        text = text.rstrip() + "\n\n" + "\n\n".join(vertical_blocks)
    return text.strip()
