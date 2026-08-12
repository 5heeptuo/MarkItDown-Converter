# MarkItDown Converter

> 把 PDF / Word / Excel / PowerPoint / HTML / 图片 / 扫描件拖进窗口，一键批量转成 Markdown。
> 基于 [Microsoft MarkItDown](https://github.com/microsoft/markitdown) 构建，**完全本地运行，不上传任何数据**。

**MarkItDown Converter** is a Windows desktop tool that converts files to Markdown by drag-and-drop. Built on Microsoft MarkItDown with a fully offline OCR engine (RapidOCR + ONNX) and an OCR post-processing layer that rebuilds reading order, spacing and paragraphs. Everything runs locally — no cloud, no login.

## ✨ 功能特性

- **核心引擎：Microsoft MarkItDown**（0.1.7）——支持范围跟随 MarkItDown 本身，不重复造轮子
- **本地 OCR（完全离线）**：图片与扫描版 PDF 在 MarkItDown 无输出时自动识别
  - 支持简体中文、English、Español（RapidOCR / ONNX，模型随安装包分发）
- **OCR 输出重建**（`ocr_postprocess.py`，本项目特色）：
  - 按文字框坐标重建阅读顺序：多栏页面左栏 → 右栏，宽行页眉置顶
  - 驼峰粘词恢复：`METAandTESLA` → `META and TESLA`
  - 长粘词词典恢复：`Noselectabletextlayershould` → `No selectable text layer should`
  - 行尾断词合并：`ap-` + `plications` → `applications`（复合连字符 `state-of-the-art` 不误伤）
  - 中英混排空格规则（中文之间不插空格，中英之间正常空格）
  - 竖排文字块隔离、段落重建（大行距自动分段）
- **格式智能检测**：拖入时立即判断——支持 → 入队；明显不支持（exe/dll 等）→ 汇总提醒并跳过；未知格式 → 尝试交给 MarkItDown 按内容识别
- **空内容检测**：转换结果为空时显示「无内容」，绝不假报成功
- **错误分类**：损坏文件 / 无权限 / 无法写入 / 无内容，各有明确提示；完整 traceback 写入日志
- **细节可靠**：XLSX 空单元格不输出 `NaN`（用户真写的 `NaN` 文本保留）；ZIP 转换不暴露本机绝对路径；中文 / 西班牙语文件名原样保留
- **批量转换**：多进程并行（实测约 2 倍提速），单个文件失败不中断队列
- **拖拽交互**：单文件 / 多文件 / 整个文件夹（可选扫描子目录）/ `.lnk` 快捷方式
- **输出策略**：保存到原目录或指定目录；重名时自动重命名 / 覆盖 / 跳过
- **设置记忆**：输出目录、重名策略、窗口大小位置（QSettings），升级不丢失

## 📸 截图

<!-- 建议在此添加两张截图：主界面、转换完成统计 -->

## 🚀 快速开始

### 方式一：安装包（推荐）

从 **Releases** 下载 `MarkItDownConverter_Setup_2.1.0.exe`，双击安装：

- 自动检测旧版本并**升级替换**（固定 AppId，不会出现两个软件）
- 保留用户设置（QSettings）
- 开始菜单 + 可选桌面快捷方式
- 标准卸载：设置 → 应用 → 已安装的应用
- 无需安装 Python / pip / 任何依赖

### 方式二：源码运行

```bash
git clone <your-repo-url>
cd MarkItDownConverter
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

要求：Windows 10/11（x64），Python 3.10 ~ 3.13（开发使用 3.11）。

## 📖 使用说明

1. 启动软件，把文件/文件夹拖进窗口（或点「选择文件 / 选择文件夹」）
2. 设置输出位置与重名策略（默认：保存到原目录、自动重命名）
3. 点「开始转换」——进度条实时显示，OCR 阶段显示「正在进行 OCR」
4. 完成后查看统计（成功 / 无内容 / 失败 / 跳过），点「打开输出文件夹」
5. 双击列表行可打开该文件所在文件夹

日志位置（完整 traceback，自动轮转 10MB×3）：

```
%LOCALAPPDATA%\MarkItDownConverter\logs\app.log
```

## 🗂 支持格式

| 类别 | 格式 |
|---|---|
| 文档 | PDF、Word (.docx)、PowerPoint (.pptx)、EPUB、Outlook (.msg)、Jupyter (.ipynb) |
| 表格 | Excel (.xlsx/.xls)、CSV |
| 网页 | HTML、Bing SERP、Wikipedia |
| 文本 | TXT、Markdown、JSON、XML、RSS |
| 图片 | PNG / JPG / JPEG / GIF / BMP / WebP / TIFF / SVG（无文本时自动 OCR） |
| 扫描件 | 无文本层 PDF（自动渲染每页 + OCR） |
| 归档 | ZIP（内存安全解压，不执行内部程序，不暴露绝对路径） |
| 音频 | 元数据（转写依赖可选扩展） |

> 实际支持范围以集成的 MarkItDown 版本为准（见 `format_registry.py`，格式列表的唯一来源）。

## 🧠 技术架构

```
用户拖拽 / 选择
      ↓
format_registry.py  格式分类（支持 / 不支持 / 未知）
      ↓
converter.py        MarkItDown 优先转换
      ↓ 空内容或异常
ocr.py              RapidOCR 识别（图片） / pypdfium2 渲染 + OCR（扫描 PDF）
      ↓
ocr_postprocess.py  阅读顺序重建 / 空格恢复 / 断词合并 / 段落重建
      ↓
worker.py           QThread + ProcessPoolExecutor 并行（max_workers=4）
      ↓
gui.py              PySide6：进度条 / 状态列表 / 日志
```

关键设计：

- **MarkItDown 是核心**：原生支持的格式直接交给 MarkItDown，OCR 只是 fallback 与后处理
- **单一格式来源**：`format_registry.py` 统一管理扩展名判断，GUI 过滤 / 扫描 / 拖拽 / 转换共用，杜绝多列表漂移
- **OCR 懒加载**：首次需要 OCR 时才加载模型（约 16MB ONNX），普通文档转换不受影响；多进程内模型复用
- **OCR 模型随包分发**：完全离线，无网络请求

## 🔨 从源码构建安装包

```bash
build_installer.bat
```

自动完成：清理 → 安装依赖 → PyInstaller（onedir）→ Inno Setup。输出：

```
release\MarkItDownConverter_Setup_2.1.0.exe
```

### 安装包特性

- 固定 AppId → 旧版本自动升级替换
- 检测旧版进程（AppMutex + tasklist），运行中自动关闭后再升级
- 保留 QSettings；卸载不删除用户文件
- 图标、版本信息、桌面快捷方式齐全

## 🧪 测试

```bash
.venv\Scripts\python -m pytest tests/ -q
```

66 项测试覆盖：MarkItDown 多格式（docx/xlsx/pptx/txt/csv/json/html）、图片 OCR（中/英/西）、扫描 PDF OCR、OCR 后处理（行排序/空格/断词/多栏/竖排/段落）、XLSX NaN、ZIP 路径隐私、损坏文件分类、不支持格式拦截、中文路径、批量 worker（100 文件）、GUI 开始按钮链路。

另附双测试套件验收：15 类核心格式 + 120 文件批量 + 15 损坏文件 + 安全（zip-slip/脚本不执行）+ 稳定性 20 项 + 路径（NFC/NFD/长路径）共 236 项断言，229 通过、7 项为设计差异（未知格式按内容尝试转换），无崩溃 / 无数据丢失 / 无安全漏洞。

## 📁 项目结构

```
├── main.py              入口（GUI / --convert 自检 / 单实例互斥体）
├── gui.py               PySide6 界面（拖拽、列表、进度、日志）
├── converter.py         转换核心（MarkItDown → 空内容检测 → OCR fallback → 错误分类）
├── ocr.py               本地 OCR（RapidOCR 懒加载 + pypdfium2 渲染）
├── ocr_postprocess.py   OCR 结果重建（行排序 / 空格 / 断词 / 段落）
├── worker.py            后台线程 + 多进程并行
├── format_registry.py   统一格式注册表（唯一格式来源）
├── logger.py            文件日志（轮转 10MB×3）
├── utils.py             输出路径 / 重名策略 / .lnk 解析
├── version.py           统一版本号
├── installer/           Inno Setup 脚本
├── tests/               pytest 测试（66 项）
└── build_installer.bat  一键构建安装包
```

## 🤝 贡献

欢迎 Issue 与 PR：

- Bug 报告请附：文件类型、复现步骤、`%LOCALAPPDATA%\MarkItDownConverter\logs\app.log`
- 代码改动请保证 `pytest tests/ -q` 全绿
- 新增格式支持请同时更新 `format_registry.py` 与测试

## 🙏 致谢

- [Microsoft MarkItDown](https://github.com/microsoft/markitdown) —— 核心转换引擎
- [RapidOCR](https://github.com/RapidAI/RapidOCR) —— 离线 OCR
- [PySide6](https://doc.qt.io/qtforpython-6/) / [PyInstaller](https://pyinstaller.org/) / [Inno Setup](https://jrsoftware.org/isinfo.php)
- [wordninja](https://github.com/keredson/wordninja) —— 长粘词词典恢复

## 📄 许可证

[MIT](LICENSE)
