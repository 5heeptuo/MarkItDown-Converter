"""日志系统：GUI 只显示简略信息，完整 traceback 写入
%LOCALAPPDATA%\\MarkItDownConverter\\logs\\app.log（按大小轮转）。"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _log_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / "AppData" / "Local"
    return root / "MarkItDownConverter" / "logs"


def get_logger(name: str = "markitdown-converter") -> logging.Logger:
    """获取应用日志记录器（首次调用时配置）。"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_file = _log_dir() / "app.log"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
    except OSError:
        # 日志目录不可写时退回临时目录，绝不让日志问题拖垮程序
        import tempfile

        handler = RotatingFileHandler(
            Path(tempfile.gettempdir()) / "markitdown-converter.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(handler)
    return logger


def log_exception(exc: BaseException, context: str = "") -> None:
    """把异常完整 traceback 写入日志（不暴露给 GUI）。"""
    logger = get_logger()
    logger.exception("%s: %s", context, exc)
