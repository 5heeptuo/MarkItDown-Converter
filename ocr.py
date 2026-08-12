"""本地 OCR 模块（RapidOCR + ONNX，完全离线）。

- ocr_image: 单张图片 -> 文字
- ocr_pdf:   扫描版 PDF -> 文字（pypdfium2 渲染每页 -> RapidOCR）

中 / 英 / 西 文识别已实测通过（ch_PP-OCRv4 模型）。
"""

from __future__ import annotations

from pathlib import Path

from logger import log_exception

# RapidOCR 引擎懒加载单例（每个进程一份，模型约 16MB）
_engine = None


def _get_engine():
    """懒加载 RapidOCR 引擎。首次调用较慢（加载 ONNX 模型）。"""
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


def ocr_image(image_path: str | Path) -> str:
    """对单张图片做 OCR，返回识别出的文字（按行拼接）。失败返回空串。"""
    try:
        result, _ = _get_engine()(str(image_path))
        from ocr_postprocess import postprocess_ocr

        return postprocess_ocr(result)
    except Exception as exc:  # noqa: BLE001
        log_exception(exc, f"OCR 图片失败: {image_path}")
        return ""


def ocr_pdf(pdf_path: str | Path, max_pages: int | None = None) -> str:
    """对扫描版 PDF 做 OCR：每页渲染为图像后识别，失败页跳过。

    max_pages 用于限制页数（默认全部，用于测试可限制）。
    """
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(pdf_path))
    except Exception as exc:  # noqa: BLE001
        log_exception(exc, f"无法打开 PDF: {pdf_path}")
        return ""

    parts: list[str] = []
    try:
        page_count = len(pdf)
        if max_pages is not None:
            page_count = min(page_count, max_pages)
        for index in range(page_count):
            try:
                page = pdf[index]
                bitmap = page.render(scale=2.0)  # 2x 提高小字识别率
                pil_image = bitmap.to_pil()
                text = ocr_image_from_pil(pil_image)
                if text:
                    parts.append(text)
            except Exception as exc:  # noqa: BLE001
                log_exception(exc, f"PDF 第 {index + 1} 页 OCR 失败: {pdf_path}")
    finally:
        pdf.close()
    return "\n\n".join(parts).strip()


def ocr_image_from_pil(pil_image) -> str:
    """对 PIL 图像做 OCR（PDF 渲染页内部使用）。"""
    try:
        result, _ = _get_engine()(pil_image)
        from ocr_postprocess import postprocess_ocr

        return postprocess_ocr(result)
    except Exception as exc:  # noqa: BLE001
        log_exception(exc, "OCR PIL 图像失败")
        return ""
