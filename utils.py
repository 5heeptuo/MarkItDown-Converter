"""工具函数：路径处理、重名策略、快捷方式解析。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def resolve_output_path(
    input_path: Path,
    output_dir: Path | None,
    mode: str,
    reserved: set[str] | None = None,
) -> Path | None:
    """计算输出路径。mode: "rename" 自动重命名 / "overwrite" 覆盖 / "skip" 跳过。

    output_dir 为 None 表示保存到原文件目录；reserved 是本次批量任务里已经
    分配出去的输出路径（避免同名前缀文件互相覆盖）。返回 None 表示应跳过。
    """

    def taken(p: Path) -> bool:
        if p.exists():
            return True
        return reserved is not None and str(p) in reserved

    target_dir = output_dir if output_dir is not None else input_path.parent
    base = target_dir / f"{input_path.stem}.md"

    if mode == "overwrite":
        return base
    if mode == "skip":
        return None if taken(base) else base
    # rename：report.md -> report_1.md -> report_2.md ...
    if not taken(base):
        return base
    for i in range(1, 10000):
        candidate = target_dir / f"{input_path.stem}_{i}.md"
        if not taken(candidate):
            return candidate
    return target_dir / f"{input_path.stem}_{os.urandom(4).hex()}.md"


def resolve_lnk(lnk_path: Path) -> Path | None:
    """解析 .lnk 快捷方式的目标路径；失败返回 None（不会抛出异常）。"""
    try:
        quoted = str(lnk_path).replace("'", "''")
        script = (
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('"
            + quoted
            + "').TargetPath;"
            "[Console]::Out.Write($s)"
        )
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            timeout=10,
        )
        target = out.stdout.decode("utf-8", errors="ignore").strip()
        if target and Path(target).exists():
            return Path(target)
    except Exception:  # noqa: BLE001
        pass
    return None
