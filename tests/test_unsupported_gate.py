"""v2 套件发现的修复回归：convert_file 拒绝明显不支持格式。"""
from __future__ import annotations

from pathlib import Path

import pytest

from converter import ConvertError, convert_file
from format_registry import classify


@pytest.mark.parametrize(
    "name,content",
    [
        ("fake_program.exe", b"This is a fake executable. Do not execute."),
        ("fake_library.dll", b"MZ fake dll content"),
        ("do_not_run.bat", b"echo hello"),
        ("do_not_run.cmd", b"@echo off"),
        ("do_not_run.ps1", b"Write-Host hello"),
    ],
)
def test_convert_rejects_unsupported_formats(tmp_path: Path, name: str, content: bytes) -> None:
    """即使文件内容是文本，exe/dll/bat/cmd/ps1 也必须被拒绝（不按内容猜测）。"""
    src = tmp_path / name
    src.write_bytes(content)
    assert classify(src) == "unsupported"
    with pytest.raises(ConvertError) as excinfo:
        convert_file(src, tmp_path / "out.md")
    assert excinfo.value.category == "unsupported"
    assert not (tmp_path / "out.md").exists()


def test_fake_pdf_text_still_converts(tmp_path: Path) -> None:
    """假扩展名但内容可读：.pdf 是支持格式，按内容转换成功（宽容行为）。"""
    src = tmp_path / "fake.pdf"
    src.write_text("plain text, not a PDF. CHECKPOINT FAKE-PDF.", encoding="utf-8")
    assert classify(src) != "unsupported"
    status, _ = convert_file(src, tmp_path / "fake.md")
    assert status.name == "SUCCESS"
    assert "CHECKPOINT" in (tmp_path / "fake.md").read_text(encoding="utf-8")
