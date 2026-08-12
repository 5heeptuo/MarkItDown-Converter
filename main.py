"""入口：`python main.py` 启动 GUI；打包后的 EXE 支持 `--convert` 命令行自测模式。

版本信息统一来自 version.py。
"""

from __future__ import annotations

import multiprocessing
import sys


def run_cli() -> int | None:
    """命令行模式：MarkItDownConverter.exe --convert <输入文件> <输出.md>

    用于打包后验证依赖是否齐全（退出码 0=成功，1=失败）。
    失败时把详细错误写入 <输出路径>.error.log（--windowed 模式下没有控制台可看）。
    """
    if len(sys.argv) == 4 and sys.argv[1] == "--convert":
        import traceback
        from pathlib import Path

        from converter import convert_file
        from logger import get_logger

        try:
            status, _ = convert_file(sys.argv[2], sys.argv[3])
            if status.name == "SUCCESS":
                return 0
            get_logger().error("转换未成功: %s", status.value)
            return 1
        except Exception:  # noqa: BLE001
            get_logger().exception("CLI 转换失败")
            try:
                err_path = Path(sys.argv[3]).with_suffix(".error.log")
                err_path.write_text(traceback.format_exc(), encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass
            return 1
    return None


def main() -> None:
    code = run_cli()
    if code is not None:
        sys.exit(code)

    _acquire_single_instance_mutex()

    from PySide6.QtWidgets import QApplication

    from gui import MainWindow
    from version import APP_NAME

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


def _acquire_single_instance_mutex() -> None:
    """创建全局互斥体：安装程序（AppMutex）用它检测程序是否在运行并提示关闭。"""
    import ctypes

    handle = ctypes.windll.kernel32.CreateMutexW(None, False, "MarkItDownConverter_SingleInstance")
    if handle and ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        # 已有实例在运行：激活已有窗口后退出
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication(sys.argv)
        QMessageBox.information(None, "MarkItDown Converter", "程序已经在运行。")
        sys.exit(0)
    # 句柄必须保持存活，否则互斥体会被释放；存入全局引用
    global _MUTEX_HANDLE
    _MUTEX_HANDLE = handle


_MUTEX_HANDLE = None  # 保持互斥体句柄存活


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
