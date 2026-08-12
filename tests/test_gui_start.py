"""GUI 开始转换按钮的端到端回归测试。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from converter import Status
from gui import MainWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_start_button_launches_worker_and_completes(tmp_path: Path, monkeypatch) -> None:
    """添加 TXT 后点击开始转换，必须启动 Worker 并产生 Markdown。"""
    _app()
    # 防止完成弹窗阻塞无头测试；行为验证聚焦启动链和输出。
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)

    src = tmp_path / "用户点击测试.txt"
    src.write_text("GUI conversion works", encoding="utf-8")

    window = MainWindow()
    window._add_paths([str(src)])
    assert window.btn_start.isEnabled()

    # 模拟用户点击按钮，覆盖 clicked -> _start 的真实信号链。
    window.btn_start.click()

    worker = window.worker
    assert worker is not None, "点击开始转换后没有创建 Worker"
    assert worker.wait(30_000), "Worker 没有在 30 秒内结束"
    QApplication.processEvents()

    output = src.with_suffix(".md")
    assert output.exists(), "点击开始转换后未生成 Markdown"
    assert "GUI conversion works" in output.read_text(encoding="utf-8")
    status_item = window.table.item(0, 2)
    assert status_item is not None
    assert Status.SUCCESS.value in status_item.text()
