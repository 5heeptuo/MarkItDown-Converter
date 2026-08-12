"""后台转换线程：避免转换过程阻塞 GUI 主线程（防“程序未响应”）。

多文件时用独立进程并行转换（实测约 2 倍提速）；单文件直接转换避免进程开销。
OCR 阶段通过 stage 信号通知 GUI 显示“OCR 识别中”。
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from converter import Status, convert_file


def recommended_workers(task_count: int) -> int:
    """返回适合桌面应用的进程数：最多 4 个，并给系统保留一个核心。"""
    if task_count <= 1:
        return 1
    available = max(1, (os.cpu_count() or 2) - 1)
    return min(task_count, available, 4)


def convert_one(task: tuple[int, str, str]) -> tuple[int, str, str]:
    """转换单个文件；作为顶层函数以兼容 Windows 多进程。

    Returns: (row, status_name, message)。message 为空表示成功。
    """
    row, src, dst = task
    try:
        status, message = convert_file(src, dst)
        if status == Status.SUCCESS:
            return row, Status.SUCCESS.name, ""
        return row, status.name, message
    except Exception as exc:  # noqa: BLE001
        from converter import ConvertError
        from logger import log_exception

        if isinstance(exc, ConvertError):
            return row, Status.FAILED.name, str(exc)
        # 意外异常：完整信息写日志，界面只显示通用消息
        log_exception(exc, f"转换未预期异常: {src}")
        return row, Status.FAILED.name, "转换失败：发生了未预期的错误（详见日志）"


class ConvertWorker(QThread):
    # 信号：已完成数 / 总数 / 表格行 / 文件名 / 阶段(状态名)
    progress = Signal(int, int, int, str, str)  # (completed, total, row, name, status_name)
    file_result = Signal(int, str, str)         # (row, status_name, message)
    all_done = Signal(int, int, int, int)       # (成功, 无内容, 失败, 跳过)

    def __init__(self, tasks: list[tuple[int, str, str | None]], parent=None) -> None:
        """tasks: [(行号, 输入文件, 输出文件或 None(跳过)), ...]"""
        super().__init__(parent)
        self._tasks = tasks

    def run(self) -> None:  # noqa: D102
        ok = no_content = fail = skipped = completed = 0
        total = len(self._tasks)
        runnable: list[tuple[int, str, str]] = []
        source_by_row = {row: src for row, src, _ in self._tasks}
        for row, src, dst in self._tasks:
            if dst is None:
                skipped += 1
                completed += 1
                self.progress.emit(completed, total, row, Path(src).name, Status.SKIPPED.name)
                self.file_result.emit(row, Status.SKIPPED.name, "")
                continue
            runnable.append((row, src, dst))

        workers = recommended_workers(len(runnable))
        if workers == 1:
            results = map(convert_one, runnable)
            for row, status_name, message in results:
                self._finish_one(row, status_name, message)
                completed += 1
                ok += status_name == Status.SUCCESS.name
                no_content += status_name == Status.NO_CONTENT.name
                fail += status_name == Status.FAILED.name
                self.progress.emit(completed, total, row, Path(source_by_row[row]).name, status_name)
        else:
            # 独立进程绕过 Python GIL；实测大型 XLSX 批量转换约快 2 倍。
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(convert_one, task) for task in runnable]
                for future in as_completed(futures):
                    row, status_name, message = future.result()
                    self._finish_one(row, status_name, message)
                    completed += 1
                    ok += status_name == Status.SUCCESS.name
                    no_content += status_name == Status.NO_CONTENT.name
                    fail += status_name == Status.FAILED.name
                    self.progress.emit(completed, total, row, Path(source_by_row[row]).name, status_name)
        self.all_done.emit(ok, no_content, fail, skipped)

    def _finish_one(self, row: int, status_name: str, message: str) -> None:
        self.file_result.emit(row, status_name, message)
