"""主窗口：拖拽添加、格式过滤、批量转换、OCR 阶段反馈、进度、日志。"""
from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QBrush, QColor, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from converter import Status
from format_registry import (
    classify,
    file_dialog_filter,
    get_file_type,
    is_known_unsupported,
    scan_folder,
)
from logger import get_logger, log_exception
from utils import resolve_lnk, resolve_output_path
from version import APP_NAME, APP_VERSION
from worker import ConvertWorker

STATUS_PENDING = Status.WAITING.value
STATUS_RUNNING = Status.CONVERTING.value
STATUS_OCR = Status.OCR.value

_COLLISION_MODES = ["rename", "overwrite", "skip"]
_COLLISION_LABELS = ["自动重命名", "覆盖", "跳过"]

_STATUS_COLORS = {
    Status.SUCCESS.value: "#2e7d32",
    Status.NO_CONTENT.value: "#e65100",
    Status.FAILED.value: "#c62828",
    Status.UNSUPPORTED.value: "#9e9e9e",
    Status.WAITING.value: "#757575",
    Status.CONVERTING.value: "#1565c0",
    Status.OCR.value: "#6a1b9a",
}
_STATUS_ICONS = {
    Status.SUCCESS.value: "✓ ",
    Status.NO_CONTENT.value: "⚠ ",
    Status.FAILED.value: "✕ ",
    Status.OCR.value: "◉ ",
}


def _find_icon() -> str:
    """在开发目录和打包后的目录里找图标，找不到返回空串。"""
    candidates = [
        Path(sys.executable).parent / "_internal",
        Path(sys.executable).parent,
        Path(__file__).resolve().parent,
    ]
    for base in candidates:
        p = base / "assets" / "icon.ico"
        if p.exists():
            return str(p)
    return ""


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"MarkItDown 批量转换器 v{APP_VERSION}")
        self.resize(820, 700)
        self.setMinimumSize(680, 560)
        self.setAcceptDrops(True)
        icon = _find_icon()
        if icon:
            self.setWindowIcon(QIcon(icon))
        # QSettings 组织/应用名与 v1 完全一致 -> 升级后用户设置自动保留
        self.settings = QSettings("MarkItDownConverter", "MarkItDownConverter")
        self.worker: ConvertWorker | None = None
        self._build_ui()
        self._restore_settings()
        self._log(f"{APP_NAME} v{APP_VERSION} 已启动。把文件或文件夹拖到窗口，或点击“选择文件 / 选择文件夹”。")
        try:
            import markitdown

            self._log(f"MarkItDown 引擎版本：{getattr(markitdown, '__version__', '未知')}")
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # ---- 拖拽区 ----
        self.drop_label = QLabel(
            "📄\n\n将文件或文件夹拖到这里\n\n自动转换为 Markdown (.md)\n\n"
            "支持 MarkItDown 可处理的文档、表格、演示文稿、网页、图片等格式"
        )
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setMinimumHeight(150)
        self.drop_label.setStyleSheet(
            "QLabel{border:2px dashed #4a90d9;border-radius:10px;"
            "background:#f2f7fd;color:#444;font-size:14px;}"
            "QLabel[dragOver=\"true\"]{border:2px dashed #1b6ec2;background:#e3f0fc;color:#1b6ec2;}"
        )
        root.addWidget(self.drop_label)

        # ---- 按钮行 ----
        btn_row = QHBoxLayout()
        self.btn_files = QPushButton("选择文件…")
        self.btn_folder = QPushButton("选择文件夹…")
        self.btn_start = QPushButton("开始转换")
        self.btn_del = QPushButton("删除选中")
        self.btn_clear = QPushButton("清空列表")
        self.btn_open = QPushButton("打开输出文件夹")
        self.btn_start.setEnabled(False)  # 空列表时禁用
        for b in (self.btn_files, self.btn_folder, self.btn_start,
                  self.btn_del, self.btn_clear, self.btn_open):
            btn_row.addWidget(b)
        root.addLayout(btn_row)

        # ---- 输出设置 ----
        opt = QGroupBox("输出设置")
        self.opt_group = opt
        form = QVBoxLayout(opt)

        out_row = QHBoxLayout()
        self.rb_same = QRadioButton("保存到原文件目录")
        self.rb_custom = QRadioButton("保存到指定目录")
        self.rb_same.setChecked(True)
        self.btn_browse = QPushButton("浏览…")
        self.ed_outdir = QLineEdit()
        self.ed_outdir.setPlaceholderText("请选择输出目录…")
        self.ed_outdir.setEnabled(False)
        out_row.addWidget(self.rb_same)
        out_row.addWidget(self.rb_custom)
        out_row.addWidget(self.ed_outdir, 1)
        out_row.addWidget(self.btn_browse)
        form.addLayout(out_row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("文件已存在时："))
        self.cb_collision = QComboBox()
        self.cb_collision.addItems(_COLLISION_LABELS)
        row2.addWidget(self.cb_collision)
        row2.addSpacing(24)
        self.cb_recursive = QCheckBox("扫描子文件夹")
        self.cb_recursive.setChecked(True)
        row2.addWidget(self.cb_recursive)
        row2.addStretch(1)
        form.addLayout(row2)
        root.addWidget(opt)

        # ---- 文件列表 ----
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["文件名", "类型", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._on_row_double_clicked)
        self.table.model().rowsInserted.connect(self._update_start_enabled)
        self.table.model().rowsRemoved.connect(self._update_start_enabled)
        root.addWidget(self.table, 1)

        # ---- 进度 ----
        self.progress = QProgressBar()
        self.progress.setFormat("%v / %m")
        self.progress.setValue(0)
        root.addWidget(self.progress)
        self.lbl_current = QLabel("")
        root.addWidget(self.lbl_current)

        # ---- 日志 ----
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(140)
        root.addWidget(self.log_view)

        self.btn_files.clicked.connect(self._pick_files)
        self.btn_folder.clicked.connect(self._pick_folder)
        self.btn_start.clicked.connect(self._start)
        self.btn_del.clicked.connect(self._delete_selected)
        self.btn_clear.clicked.connect(self._clear_list)
        self.btn_open.clicked.connect(self._open_output_folder)
        self.btn_browse.clicked.connect(self._browse_outdir)
        self.rb_custom.toggled.connect(lambda on: self.ed_outdir.setEnabled(on))

    # -------------------------------------------------------------- settings
    def _restore_settings(self) -> None:
        geo = self.settings.value("geometry")
        if isinstance(geo, QByteArray) and not geo.isEmpty():
            self.restoreGeometry(geo)
        outdir = self.settings.value("outdir", "")
        if outdir:
            self.ed_outdir.setText(str(outdir))
        idx = int(self.settings.value("collision", 0))
        if 0 <= idx < len(_COLLISION_MODES):
            self.cb_collision.setCurrentIndex(idx)
        rec = self.settings.value("recursive", "true")
        self.cb_recursive.setChecked(str(rec).lower() != "false")
        custom = self.settings.value("custom_outdir", "false")
        if str(custom).lower() == "true" and str(outdir):
            self.rb_custom.setChecked(True)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker is not None and self.worker.isRunning():
            answer = QMessageBox.question(
                self, "确认退出", "转换尚未完成，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.worker.requestInterruption()
            self.worker.wait(8000)
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("outdir", self.ed_outdir.text())
        self.settings.setValue("collision", self.cb_collision.currentIndex())
        self.settings.setValue("recursive", "true" if self.cb_recursive.isChecked() else "false")
        self.settings.setValue("custom_outdir", "true" if self.rb_custom.isChecked() else "false")
        event.accept()

    # ------------------------------------------------------------ drag & drop
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_label.setProperty("dragOver", "true")
            self.drop_label.setText("松开即可添加文件")
            self.drop_label.style().unpolish(self.drop_label)
            self.drop_label.style().polish(self.drop_label)

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._reset_drop_label()

    def dropEvent(self, event) -> None:  # noqa: N802
        self._reset_drop_label()
        if self.worker is not None and self.worker.isRunning():
            self._log("转换进行中，请等待完成后再添加文件。")
            return
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        self._add_paths(paths)

    def _reset_drop_label(self) -> None:
        self.drop_label.setProperty("dragOver", "false")
        self.drop_label.setText(
            "📄\n\n将文件或文件夹拖到这里\n\n自动转换为 Markdown (.md)\n\n"
            "支持 MarkItDown 可处理的文档、表格、演示文稿、网页、图片等格式"
        )
        self.drop_label.style().unpolish(self.drop_label)
        self.drop_label.style().polish(self.drop_label)

    # ---------------------------------------------------------------- actions
    def _pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择要转换的文件", "", file_dialog_filter()
        )
        if files:
            self._add_paths(files)

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择要扫描的文件夹")
        if folder:
            self._add_paths([folder])

    def _add_paths(self, paths: list[str]) -> None:
        """添加文件/文件夹：支持的文件加入队列，明显不支持的汇总提醒。"""
        existing = self._existing_paths()
        added: list[Path] = []
        rejected: list[tuple[str, str]] = []  # (名称, 原因)
        unknown: list[Path] = []

        def add_file(p: Path) -> None:
            kind = classify(p)
            if kind == "unsupported":
                rejected.append((p.name, f"不支持 .{p.suffix.lower().lstrip('.')}"))
            elif kind == "unknown":
                unknown.append(p)
            else:
                added.append(p)

        for raw in paths:
            p = Path(raw)
            try:
                if not p.exists():
                    self._log(f"路径不存在，已忽略：{raw}")
                    continue
                if p.is_dir():
                    supported, unsupported = scan_folder(p, self.cb_recursive.isChecked())
                    added.extend(supported)
                    rejected.extend((f.name, f"不支持 .{f.suffix.lower().lstrip('.')}") for f in unsupported)
                    self._log(f"文件夹扫描完成：{raw}（发现 {len(supported) + len(unsupported)} 个文件，"
                              f"可添加 {len(supported)}，不支持 {len(unsupported)}）")
                    continue
                if p.suffix.lower() == ".lnk":
                    target = resolve_lnk(p)
                    if target is None:
                        self._log(f"无法解析快捷方式，已忽略：{raw}")
                        continue
                    p = target
                    if p.is_dir():
                        supported, unsupported = scan_folder(p, self.cb_recursive.isChecked())
                        added.extend(supported)
                        rejected.extend(
                            (f.name, f"不支持 .{f.suffix.lower().lstrip('.')}") for f in unsupported
                        )
                        continue
                add_file(p)
            except Exception as exc:  # noqa: BLE001
                log_exception(exc, f"添加文件失败: {raw}")
                self._log(f"添加失败：{raw}")

        added_count = self._insert_rows(added, existing)
        unknown_count = self._insert_rows(unknown, existing, unknown_format=True)
        if unknown_count:
            self._log(f"已添加 {unknown_count} 个未知格式文件（将尝试由 MarkItDown 识别转换）。")

        if rejected:
            self._show_rejected_summary(len(added) + unknown_count, rejected)
        elif added_count or unknown_count:
            self._log(f"已添加 {added_count + unknown_count} 个文件。")

    def _insert_rows(self, paths: list[Path], existing: set[str], unknown_format: bool = False) -> int:
        count = 0
        for path in paths:
            key = str(path.resolve())
            if key in existing:
                continue
            existing.add(key)
            row = self.table.rowCount()
            self.table.insertRow(row)
            item_name = QTableWidgetItem(path.name)
            item_name.setData(Qt.ItemDataRole.UserRole, key)
            item_name.setToolTip(str(path))
            item_type = QTableWidgetItem(get_file_type(path))
            if unknown_format:
                item_type.setText(f"{item_type.text()} ?")
                item_type.setToolTip("未知格式，将尝试由 MarkItDown 识别")
            item_status = QTableWidgetItem(STATUS_PENDING)
            item_status.setForeground(QBrush(QColor(_STATUS_COLORS[STATUS_PENDING])))
            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_type)
            self.table.setItem(row, 2, item_status)
            count += 1
            self._log(f"已添加：{path}")
        return count

    def _show_rejected_summary(self, added_count: int, rejected: list[tuple[str, str]]) -> None:
        """一次性汇总提醒被拒绝的文件（不逐个弹窗）。"""
        lines = "\n".join(f"• {name}（{reason}）" for name, reason in rejected[:20])
        if len(rejected) > 20:
            lines += f"\n… 以及另外 {len(rejected) - 20} 个文件"
        body = (
            f"{added_count} 个文件已成功添加。\n\n"
            f"{len(rejected)} 个文件由于格式不受支持而被跳过：\n\n{lines}\n\n"
            "MarkItDown 不支持这些文件格式。"
        )
        self._log(f"有 {len(rejected)} 个文件因格式不支持被跳过。")
        QMessageBox.information(self, "部分文件无法添加", body)

    def _existing_paths(self) -> set[str]:
        return {
            self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
            for r in range(self.table.rowCount())
        }

    def _delete_selected(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedItems()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)

    def _clear_list(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.lbl_current.setText("")
        self._log("已清空列表。")

    def _browse_outdir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self.ed_outdir.setText(folder)

    # ---------------------------------------------------------------- convert
    def _start(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        count = self.table.rowCount()
        if count == 0:
            self._log("列表为空，请先添加文件。")
            return

        custom = self.rb_custom.isChecked()
        if custom:
            outdir_text = self.ed_outdir.text().strip()
            if not outdir_text:
                QMessageBox.warning(self, "提示", "请先选择输出目录，或改为“保存到原文件目录”。")
                return
            outdir = Path(outdir_text)
        else:
            outdir = None
        mode = _COLLISION_MODES[self.cb_collision.currentIndex()]

        tasks: list[tuple[int, str, str | None]] = []
        reserved: set[str] = set()  # 本次批量中已分配的输出路径，防止同名前缀互相覆盖
        for r in range(count):
            src = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
            try:
                dst = resolve_output_path(Path(src), outdir, mode, reserved)
            except Exception as exc:  # noqa: BLE001
                log_exception(exc, f"计算输出路径失败: {src}")
                dst = None
            if dst is not None:
                reserved.add(str(dst))
            tasks.append((r, src, None if dst is None else str(dst)))
            self._set_status(r, Status.WAITING)

        self._update_start_enabled()
        self.worker = ConvertWorker(tasks, self)
        self.worker.progress.connect(self._on_progress)
        self.worker.file_result.connect(self._on_file_result)
        self.worker.all_done.connect(self._on_all_done)
        self.progress.setRange(0, count)
        self.progress.setValue(0)
        self.lbl_current.setText("")
        self._set_running(True)
        self._log(f"开始转换，共 {count} 个文件。")
        self.worker.start()

    def _on_progress(self, completed: int, total: int, row: int, name: str, status_name: str) -> None:
        self.progress.setValue(completed)
        if status_name == Status.OCR.name:
            self.lbl_current.setText(f"正在进行 OCR：{name}")
        else:
            self.lbl_current.setText(f"正在处理 {completed}/{total}：{name}")

    def _on_file_result(self, row: int, status_name: str, message: str) -> None:
        name_item = self.table.item(row, 0)
        if name_item is None:
            return
        name = name_item.text()
        status = Status[status_name] if status_name in Status.__members__ else Status.FAILED
        if status == Status.SUCCESS:
            self._set_status(row, status)
            self._log(f"转换完成：{Path(name).stem}.md")
        elif status == Status.NO_CONTENT:
            self._set_status(row, status)
            self._log(f"未检测到可提取内容：{name}")
        elif status == Status.SKIPPED:
            self._set_status(row, status)
            self._log(f"已跳过（目标 .md 已存在）：{name}")
        else:
            self._set_status(row, status)
            self._log(f"转换失败：{name} —— {message or '未知错误'}")

    def _on_all_done(self, ok: int, no_content: int, fail: int, skipped: int) -> None:
        self.progress.setValue(self.progress.maximum())
        self.lbl_current.setText("")
        self._set_running(False)
        total = ok + no_content + fail + skipped
        msg = f"转换完成\n\n成功：{ok}"
        if no_content:
            msg += f"\n无内容：{no_content}"
        if fail:
            msg += f"\n失败：{fail}"
        if skipped:
            msg += f"\n跳过：{skipped}"
        msg += f"\n总计：{total}"
        self._log(f"全部完成：成功 {ok}，无内容 {no_content}，失败 {fail}，跳过 {skipped}，总计 {total}。")
        box = QMessageBox(self)
        box.setWindowTitle("转换完成")
        box.setText(msg)
        btn_open = box.addButton("打开输出文件夹", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("确定", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is btn_open:
            self._open_output_folder()

    def _set_running(self, running: bool) -> None:
        for b in (self.btn_files, self.btn_folder, self.btn_clear,
                  self.btn_del, self.btn_start):
            b.setEnabled(not running)
        self.opt_group.setEnabled(not running)
        self._update_start_enabled()

    def _update_start_enabled(self) -> None:
        """开始转换按钮：有文件且未在转换时可用。"""
        running = self.worker is not None and self.worker.isRunning()
        self.btn_start.setEnabled(not running and self.table.rowCount() > 0)

    def _set_status(self, row: int, status: Status) -> None:
        item = self.table.item(row, 2)
        if item is None:
            return
        label = status.value
        icon = _STATUS_ICONS.get(label, "")
        item.setText(icon + label if icon else label)
        item.setForeground(QBrush(QColor(_STATUS_COLORS.get(label, "#000000"))))

    # ---------------------------------------------------------------- opening
    def _on_row_double_clicked(self, item: QTableWidgetItem) -> None:
        src = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        try:
            os.startfile(str(Path(src).parent))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            self._log(f"无法打开文件夹：{exc}")

    def _open_output_folder(self) -> None:
        target = None
        if self.rb_custom.isChecked() and self.ed_outdir.text().strip():
            target = Path(self.ed_outdir.text())
        else:
            for r in range(self.table.rowCount()):
                item = self.table.item(r, 2)
                if item and item.text().startswith(_STATUS_ICONS[Status.SUCCESS.value]):
                    src = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
                    target = Path(src).parent
                    break
        if target is None:
            self._log("还没有可打开的文件夹（请先添加并转换文件）。")
            return
        try:
            os.startfile(str(target))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            self._log(f"无法打开文件夹：{exc}")

    # ------------------------------------------------------------------- log
    def _log(self, message: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{ts}] {message}")
        get_logger().info(message)
