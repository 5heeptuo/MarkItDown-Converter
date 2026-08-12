from __future__ import annotations

from pathlib import Path

import pytest

from format_registry import (
    MARKITDOWN_EXTENSIONS,
    classify,
    file_dialog_filter,
    get_file_type,
    is_known_unsupported,
    is_supported,
    scan_folder,
)


def test_markitdown_extension_set_matches_0107(tmp_path: Path) -> None:
    """MarkItDown 0.1.7 内置 converter 的扩展名必须全部在支持列表中。"""
    expected = {
        ".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".csv", ".html", ".htm",
        ".txt", ".text", ".md", ".markdown", ".json", ".jsonl",
        ".ipynb", ".msg", ".epub", ".zip",
        ".jpg", ".jpeg", ".png", ".wav", ".mp3", ".m4a", ".mp4",
    }
    assert expected <= MARKITDOWN_EXTENSIONS


def test_is_supported_common_formats(tmp_path: Path) -> None:
    for ext in (".pdf", ".docx", ".xlsx", ".pptx", ".html", ".png", ".gif", ".zip"):
        p = tmp_path / f"sample{ext}"
        p.write_bytes(b"x")
        assert is_supported(p), ext


def test_is_known_unsupported(tmp_path: Path) -> None:
    for ext in (".exe", ".dll", ".msi", ".sys"):
        p = tmp_path / f"bad{ext}"
        p.write_bytes(b"MZ")
        assert is_known_unsupported(p), ext
        assert classify(p) == "unsupported", ext


def test_classify_ocr_image_vs_markitdown(tmp_path: Path) -> None:
    png = tmp_path / "a.png"
    png.write_bytes(b"x")
    webp = tmp_path / "a.webp"
    webp.write_bytes(b"x")
    assert classify(png) == "markitdown"
    assert classify(webp) == "ocr-image"


def test_classify_unknown(tmp_path: Path) -> None:
    p = tmp_path / "random.abcxyz"
    p.write_bytes(b"x")
    assert classify(p) == "unknown"


def test_scan_folder_filters_unsupported(tmp_path: Path) -> None:
    (tmp_path / "ok.pdf").write_bytes(b"x")
    (tmp_path / "img.png").write_bytes(b"x")
    (tmp_path / "bad.exe").write_bytes(b"MZ")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "doc.docx").write_bytes(b"x")
    supported, unsupported = scan_folder(tmp_path, recursive=True)
    names = {p.name for p in supported}
    assert names == {"ok.pdf", "img.png", "doc.docx"}
    assert {p.name for p in unsupported} == {"bad.exe"}


def test_get_file_type_and_filter() -> None:
    assert get_file_type(Path("a.pdf")) == "PDF"
    assert get_file_type(Path("a.png")) == "图片"
    assert "所有文件 (*.*)" in file_dialog_filter()
    assert "*.docx" in file_dialog_filter()
