from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

import worker
from converter import ConvertError
from converter import Status, convert_file


def test_recommended_workers_avoids_pool_for_single_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "cpu_count", lambda: 16)
    assert worker.recommended_workers(1) == 1


def test_recommended_workers_caps_parallelism_at_four(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "cpu_count", lambda: 16)
    assert worker.recommended_workers(20) == 4


def test_recommended_workers_leaves_one_cpu_free(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "cpu_count", lambda: 2)
    assert worker.recommended_workers(20) == 1


def test_convert_one_reports_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "a.txt"
    target = tmp_path / "a.md"
    source.write_text("hello", encoding="utf-8")

    def fake_convert(src, dst, stage_cb=None):
        Path(dst).write_text("ok", encoding="utf-8")
        return Status.SUCCESS, ""

    monkeypatch.setattr(worker, "convert_file", fake_convert)
    row, status_name, message = worker.convert_one((7, str(source), str(target)))
    assert (row, status_name, message) == (7, "SUCCESS", "")


def test_convert_one_reports_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "a.txt"
    source.write_text("hello", encoding="utf-8")

    def fail(src, dst, stage_cb=None):
        raise ConvertError("文件可能已损坏或格式不正确", "corrupt")

    monkeypatch.setattr(worker, "convert_file", fail)
    row, status_name, message = worker.convert_one((3, str(source), str(tmp_path / "a.md")))
    assert row == 3
    assert status_name == "FAILED"
    assert "损坏" in message


def test_convert_txt_success(tmp_path: Path) -> None:
    source = tmp_path / "笔记.txt"
    target = tmp_path / "笔记.md"
    source.write_text("第一行\n第二行", encoding="utf-8")
    status, _ = convert_file(source, target)
    assert status == Status.SUCCESS
    assert "第一行" in target.read_text(encoding="utf-8")
