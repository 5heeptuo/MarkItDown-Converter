"""v2.1 修复回归测试：XLSX NaN、ZIP 路径隐私、OCR 后处理集成。"""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from converter import Status, convert_file


# ---------------------------------------------------------------- XLSX NaN
def test_xlsx_empty_cells_no_nan(tmp_path: Path) -> None:
    """空单元格不得输出 NaN。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["姓名", "科目", "分数", "备注"])
    ws.append(["Maria", "SO", 7.00, None])   # 空单元格
    ws.append(["Juan", "BD", None, "ok"])
    src = tmp_path / "grades.xlsx"
    wb.save(src)

    status, _ = convert_file(src, tmp_path / "grades.md")
    assert status == Status.SUCCESS
    text = (tmp_path / "grades.md").read_text(encoding="utf-8")
    assert "NaN" not in text and "nan" not in text and "None" not in text
    # 数据仍完整
    assert "Maria" in text and "SO" in text and "7" in text


def test_xlsx_user_typed_nan_preserved(tmp_path: Path) -> None:
    """用户单元格真正写了 'NaN' 文本时不得删除。"""
    wb = Workbook()
    ws = wb.active
    ws.append(["A", "B"])
    ws.append(["NaN", 1])   # 用户真的写了 NaN
    ws.append([None, 2])
    src = tmp_path / "typed_nan.xlsx"
    wb.save(src)

    status, _ = convert_file(src, tmp_path / "typed_nan.md")
    assert status == Status.SUCCESS
    text = (tmp_path / "typed_nan.md").read_text(encoding="utf-8")
    # 用户写的 NaN 保留
    assert "NaN" in text


# ---------------------------------------------------------------- ZIP path
def test_zip_no_absolute_path(tmp_path: Path) -> None:
    """ZIP 输出不得包含本机绝对路径。"""
    import zipfile

    src = tmp_path / "archive.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("docs/readme.txt", "hello zip content")
    status, _ = convert_file(src, tmp_path / "archive.md")
    assert status == Status.SUCCESS
    text = (tmp_path / "archive.md").read_text(encoding="utf-8")
    assert "hello zip content" in text
    # 绝对路径（盘符）不得出现
    assert str(src).split(":")[0] + ":" not in text
    assert "Users" not in text.replace("docs/readme.txt", "")
    # 归档名保留
    assert "archive.zip" in text


# ---------------------------------------------------------------- OCR postprocess
def test_ocr_postprocess_english_image(suite_inputs: Path) -> None:
    """英文图片 OCR：内容识别 + 无粘连退化。"""
    src = suite_inputs / "10_image_english.png"
    if not src.exists():
        pytest.skip("测试套件图片不存在")
    status, _ = convert_file(src, src.with_suffix(".md"))
    assert status == Status.SUCCESS
    text = (src.with_suffix(".md")).read_text(encoding="utf-8")
    assert "Image OCR English Fixture" in text
    assert "CHECKPOINT" in text
    assert "Invoice" in text


def test_ocr_scan_pdf_no_word_sticking(suite_inputs: Path) -> None:
    """扫描 PDF：不得再出现 Noselectabletextlayershould bepresent 式粘词。"""
    src = suite_inputs / "12_scan_pdf_image_only.pdf"
    if not src.exists():
        pytest.skip("测试套件扫描 PDF 不存在")
    status, _ = convert_file(src, src.with_suffix(".md"))
    assert status == Status.SUCCESS
    text = (src.with_suffix(".md")).read_text(encoding="utf-8")
    assert "No selectable text layer should be present." in text
