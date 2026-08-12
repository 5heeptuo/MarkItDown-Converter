"""统一格式支持模块。

格式来源只有这一个地方，gui / worker / converter / main 不再各自维护扩展名列表。

三层判断（与“不要只通过扩展名绝对判断”一致）：
1. 已知支持列表   -> 明确支持（加入队列）
2. 明显不支持列表 -> 明确拒绝（立即提醒，不加入队列）
3. 未知扩展名     -> 允许加入并交给 MarkItDown 尝试（magika 会按内容识别 MIME），
                     转换层仍有完整异常处理；未知扩展名在界面上给出“未知格式”提示。
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# MarkItDown 0.1.7 内置 converter 实际接受的扩展名（取自其源码 ACCEPTED_*）
# ---------------------------------------------------------------------------
MARKITDOWN_EXTENSIONS: frozenset[str] = frozenset({
    # 文档
    ".docx", ".pdf", ".epub", ".msg", ".ipynb",
    # 表格
    ".xlsx", ".xls", ".csv",
    # 演示
    ".pptx",
    # 网页 / 文本 / 结构化数据
    ".html", ".htm", ".txt", ".text", ".md", ".markdown", ".json", ".jsonl",
    # 压缩 / 归档
    ".zip",
    # 图片（0.1.7 的 ImageConverter 仅支持这三种；无 LLM 时输出可能为空，走 OCR fallback）
    ".jpg", ".jpeg", ".png",
    # 音频（默认仅提取元数据）
    ".wav", ".mp3", ".m4a", ".mp4",
})

# ---------------------------------------------------------------------------
# 软件额外支持的 OCR 图片格式（MarkItDown 0.1.7 的 ImageConverter 不接受这些，
# 但本地 RapidOCR 可以识别其中的文字；svg 交给 OCR 前先栅格化失败则跳过）
# ---------------------------------------------------------------------------
OCR_IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    ".gif", ".bmp", ".webp", ".tiff", ".tif", ".svg",
})

# 支持范围 = MarkItDown 原生 + OCR 图片
SUPPORTED_EXTENSIONS: frozenset[str] = MARKITDOWN_EXTENSIONS | OCR_IMAGE_EXTENSIONS

# ---------------------------------------------------------------------------
# 明显不支持的格式：添加阶段直接拒绝，不进入转换队列
# ---------------------------------------------------------------------------
UNSUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    # 可执行 / 系统 / 安装包
    ".exe", ".dll", ".sys", ".msi", ".msp", ".cab", ".com", ".scr", ".pif",
    ".bat", ".cmd", ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf",
    ".drv", ".ocx", ".cpl", ".efi", ".bin",
    # 驱动 / 固件
    ".inf", ".cat", ".mui",
    # 数据库 / 二进制数据
    ".mdf", ".ldf", ".db", ".sqlite", ".sqlite3", ".dat", ".idx",
    # 其他二进制（几乎不可能有可提取文本）
    ".o", ".obj", ".lib", ".a", ".so", ".dylib", ".ko", ".pyc", ".pyd",
    ".iso", ".img", ".vhd", ".vhdx",
    # 快捷方式（需要先解析目标，不直接转换）
    ".lnk",
})

# 扩展名 -> 友好类型名
TYPE_NAMES: dict[str, str] = {
    ".pdf": "PDF", ".docx": "DOCX", ".xlsx": "XLSX", ".xls": "XLS",
    ".pptx": "PPTX", ".csv": "CSV", ".html": "HTML", ".htm": "HTML",
    ".txt": "TXT", ".text": "TXT", ".md": "MD", ".markdown": "MD",
    ".json": "JSON", ".jsonl": "JSONL", ".ipynb": "IPYNB",
    ".msg": "OUTLOOK", ".epub": "EPUB", ".zip": "ZIP",
    ".jpg": "图片", ".jpeg": "图片", ".png": "图片",
    ".gif": "图片", ".bmp": "图片", ".webp": "图片",
    ".tiff": "图片", ".tif": "图片", ".svg": "图片",
    ".wav": "音频", ".mp3": "音频", ".m4a": "音频", ".mp4": "音频",
}


def get_file_type(path: Path) -> str:
    """根据扩展名返回类型标签（用于表格“类型”列）。"""
    ext = path.suffix.lower()
    return TYPE_NAMES.get(ext, ext.upper().lstrip(".") or "文件")


def is_supported(path: Path) -> bool:
    """是否属于 MarkItDown 或 OCR 已知支持范围。"""
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def is_known_unsupported(path: Path) -> bool:
    """是否属于明显不支持的格式（添加阶段应直接拒绝）。"""
    return path.suffix.lower() in UNSUPPORTED_EXTENSIONS


def classify(path: Path) -> str:
    """返回格式类别：\"markitdown\" / \"ocr-image\" / \"unknown\" / \"unsupported\"。"""
    ext = path.suffix.lower()
    if ext in MARKITDOWN_EXTENSIONS:
        return "markitdown"
    if ext in OCR_IMAGE_EXTENSIONS:
        return "ocr-image"
    if ext in UNSUPPORTED_EXTENSIONS:
        return "unsupported"
    return "unknown"


def scan_folder(folder: Path, recursive: bool) -> tuple[list[Path], list[Path]]:
    """扫描文件夹，返回 (支持的文件, 不支持的文件)。

    支持 = MarkItDown 原生 + OCR 图片 + 未知扩展名（交给转换层尝试）；
    不支持 = 明显不支持列表中的扩展名。
    """
    supported: list[Path] = []
    unsupported: list[Path] = []
    it = folder.rglob("*") if recursive else folder.glob("*")
    for p in it:
        try:
            if not p.is_file():
                continue
        except OSError:
            continue
        if is_known_unsupported(p):
            unsupported.append(p)
        else:
            supported.append(p)
    return sorted(supported), sorted(unsupported)


def file_dialog_filter() -> str:
    """Windows 文件选择器过滤器：MarkItDown 支持的文件 + OCR 图片 + 所有文件。"""
    exts = sorted(SUPPORTED_EXTENSIONS)
    pattern = " ".join(f"*{e}" for e in exts)
    return (
        f"MarkItDown 支持的文件 ({pattern});;"
        f"所有文件 (*.*)"
    )
