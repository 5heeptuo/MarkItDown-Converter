"""Worker 集成测试：批量（单进程/多进程路径）、失败不中断、连续两次转换。"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from converter import Status
from worker import ConvertWorker

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.fixture(scope="session")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    return app


def _run_worker(worker: ConvertWorker, timeout_ms: int = 120_000) -> dict:
    """运行 worker 直到 all_done，收集结果。"""
    results: dict[str, list] = {"progress": [], "results": [], "done": []}
    worker.progress.connect(lambda *a: results["progress"].append(a))
    worker.file_result.connect(lambda *a: results["results"].append(a))
    worker.all_done.connect(lambda *a: results["done"].append(a))
    worker.start()
    if not worker.wait(timeout_ms):
        worker.terminate()
        worker.wait(5000)
        raise RuntimeError("worker timeout")
    # 跨线程信号是 QueuedConnection，需要处理事件队列
    QCoreApplication.processEvents()
    return results


def test_batch_100_txt_mixed_paths(tmp_path: Path) -> None:
    """100 个 TXT（含中文路径）批量转换：全部成功，进度准确，无漏文件。"""
    folder = tmp_path / "大学资料" / "第一学期"
    folder.mkdir(parents=True)
    tasks: list[tuple[int, str, str | None]] = []
    for i in range(100):
        src = folder / f"课程笔记_{i:03d}.txt"
        dst = folder / f"课程笔记_{i:03d}.md"
        src.write_text(f"笔记内容 {i}", encoding="utf-8")
        tasks.append((i, str(src), str(dst)))

    results = _run_worker(ConvertWorker(tasks))
    done = results["done"][0]
    assert done == (100, 0, 0, 0), f"成功/无内容/失败/跳过 = {done}"
    # 进度信号数量 = 任务数，最大值不超过总数
    assert len(results["results"]) == 100
    progress_counts = [p[0] for p in results["progress"]]
    assert max(progress_counts) == 100
    assert sorted(progress_counts) == list(range(1, 101))
    for i in range(100):
        assert (folder / f"课程笔记_{i:03d}.md").exists()


def test_batch_failure_does_not_stop_queue(tmp_path: Path) -> None:
    """批量中单个损坏文件失败，其余文件继续完成。"""
    tasks: list[tuple[int, str, str | None]] = []
    for i in range(5):
        src = tmp_path / f"f{i}.txt"
        src.write_text(f"content {i}", encoding="utf-8")
        tasks.append((i, str(src), str(tmp_path / f"f{i}.md")))
    # 第 2 个任务改为损坏 docx（扩展名支持但内容损坏）
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"PK\x03\x04" + b"\x00" * 64)
    tasks[2] = (2, str(bad), str(tmp_path / "bad.md"))

    results = _run_worker(ConvertWorker(tasks))
    done = results["done"][0]
    assert done == (4, 0, 1, 0), f"成功/无内容/失败/跳过 = {done}"
    statuses = {row: name for row, name, _ in results["results"]}
    assert statuses[2] == Status.FAILED.name
    assert (tmp_path / "f0.md").exists() and (tmp_path / "f4.md").exists()


def test_skip_when_dst_exists(tmp_path: Path) -> None:
    """目标已存在（跳过模式）计入 skipped，进度仍到总数。"""
    src = tmp_path / "a.txt"
    src.write_text("x", encoding="utf-8")
    tasks = [(0, str(src), None), (1, str(src), str(tmp_path / "a.md"))]
    results = _run_worker(ConvertWorker(tasks))
    done = results["done"][0]
    assert done == (1, 0, 0, 1)
    assert max(p[0] for p in results["progress"]) == 2


def test_two_consecutive_runs_same_worker_class(tmp_path: Path) -> None:
    """连续两次转换：Worker 可重新创建，状态不残留。"""
    for round_index in range(2):
        tasks = []
        for i in range(3):
            src = tmp_path / f"r{round_index}_f{i}.txt"
            src.write_text(f"round {round_index} file {i}", encoding="utf-8")
            tasks.append((i, str(src), str(tmp_path / f"r{round_index}_f{i}.md")))
        results = _run_worker(ConvertWorker(tasks))
        assert results["done"][0] == (3, 0, 0, 0)
        assert max(p[0] for p in results["progress"]) == 3
