# MarkItDown Converter

> Drag PDF / Word / Excel / PowerPoint / HTML / images / scanned documents into the window and batch-convert them to Markdown with one click.  
> Built on [Microsoft MarkItDown](https://github.com/microsoft/markitdown), **runs entirely locally and never uploads your data**.

**MarkItDown Converter** is a Windows desktop tool that converts files to Markdown by drag-and-drop. Built on Microsoft MarkItDown with a fully offline OCR engine (RapidOCR + ONNX) and an OCR post-processing layer that reconstructs reading order, spacing, and paragraphs. Everything runs locally — no cloud, no login.

## ✨ Features

- **Core engine: Microsoft MarkItDown** (0.1.7) — supported formats follow MarkItDown itself, without reinventing existing functionality
- **Local OCR (fully offline)**: images and scanned PDFs are automatically recognized when MarkItDown produces no output
  - Supports Simplified Chinese, English, and Spanish (RapidOCR / ONNX, models bundled with the installer)
- **OCR output reconstruction** (`ocr_postprocess.py`, a key feature of this project):
  - Reconstructs reading order from text-box coordinates: left column → right column on multi-column pages, with wide header lines placed first
  - Restores camel-case word sticking: `METAandTESLA` → `META and TESLA`
  - Restores long concatenated words using a dictionary: `Noselectabletextlayershould` → `No selectable text layer should`
  - Merges words split at line endings: `ap-` + `plications` → `applications` (without breaking compound hyphenation such as `state-of-the-art`)
  - Applies Chinese-English mixed-text spacing rules (no spaces between Chinese characters, normal spacing between Chinese and English)
  - Isolates vertical text blocks and reconstructs paragraphs based on larger line gaps
- **Smart format detection**: files are checked as soon as they are dropped in — supported → queued; clearly unsupported formats (such as exe/dll) → skipped with a consolidated warning; unknown formats → passed to MarkItDown for content-based detection
- **Empty-content detection**: empty conversion results are shown as “No Content” and are never falsely reported as successful
- **Error classification**: corrupted file / permission denied / output not writable / no content each have clear user-facing messages; full traceback is written to the log
- **Reliable edge-case handling**: empty XLSX cells do not output `NaN` (while literal user-entered `NaN` text is preserved); ZIP conversion does not expose local absolute paths; Chinese / Spanish filenames are preserved
- **Batch conversion**: multi-process parallel conversion (measured at roughly 2× faster), and one failed file does not interrupt the queue
- **Drag-and-drop interaction**: single file / multiple files / entire folders (optional recursive scan) / `.lnk` shortcuts
- **Output strategies**: save next to the original file or to a selected output directory; on filename conflicts, automatically rename / overwrite / skip
- **Settings persistence**: output directory, filename conflict strategy, window size and position (QSettings); settings are preserved across upgrades

## 📸 Screenshots

<!-- Suggested: add two screenshots here — main window and conversion-complete summary -->

## 🚀 Quick Start

### Option 1: Installer (Recommended)

Download `MarkItDownConverter_Setup_2.1.0.exe` from **Releases** and run the installer:

- Automatically detects older versions and **upgrades/replaces them** (fixed AppId, so duplicate installations are avoided)
- Preserves user settings (QSettings)
- Start Menu shortcut + optional desktop shortcut
- Standard uninstall: Settings → Apps → Installed apps
- No need to install Python / pip / any dependencies

### Option 2: Run from Source

```bash
git clone <your-repo-url>
cd MarkItDownConverter
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Requirements: Windows 10/11 (x64), Python 3.10 ~ 3.13 (developed with 3.11).

## 📖 Usage

1. Launch the application and drag files/folders into the window (or click “Select Files / Select Folder”)
2. Choose the output location and filename conflict strategy (default: save next to original file, auto-rename on conflict)
3. Click “Start Conversion” — the progress bar updates in real time, and OCR stages show “Running OCR”
4. After completion, review the summary (success / no content / failed / skipped), then click “Open Output Folder”
5. Double-click a row in the list to open the file’s containing folder

Log location (full traceback, automatically rotated at 10 MB × 3):

```text
%LOCALAPPDATA%\MarkItDownConverter\logs\app.log
```

## 🗂 Supported Formats

| Category | Formats |
|---|---|
| Documents | PDF, Word (.docx), PowerPoint (.pptx), EPUB, Outlook (.msg), Jupyter (.ipynb) |
| Spreadsheets | Excel (.xlsx/.xls), CSV |
| Web | HTML, Bing SERP, Wikipedia |
| Text | TXT, Markdown, JSON, XML, RSS |
| Images | PNG / JPG / JPEG / GIF / BMP / WebP / TIFF / SVG (automatic OCR when no text is extracted) |
| Scanned documents | PDFs without a text layer (automatically render each page + OCR) |
| Archives | ZIP (memory-safe extraction, does not execute internal programs, does not expose absolute paths) |
| Audio | Metadata (transcription requires optional extensions) |

> The actual supported formats depend on the bundled MarkItDown version (see `format_registry.py`, the single source of truth for the format list).

## 🧠 Architecture

```text
User drag-and-drop / selection
      ↓
format_registry.py  Format classification (supported / unsupported / unknown)
      ↓
converter.py        MarkItDown-first conversion
      ↓ Empty content or exception
ocr.py              RapidOCR (images) / pypdfium2 rendering + OCR (scanned PDFs)
      ↓
ocr_postprocess.py  Reading-order reconstruction / spacing recovery / dehyphenation / paragraph reconstruction
      ↓
worker.py           QThread + ProcessPoolExecutor parallelism (max_workers=4)
      ↓
gui.py              PySide6: progress bar / status list / logs
```

Key design decisions:

- **MarkItDown is the core**: natively supported formats go directly through MarkItDown; OCR is only a fallback and post-processing layer
- **Single format source**: `format_registry.py` centrally manages extension detection, and is shared by GUI filters / scanning / drag-and-drop / conversion to prevent format-list drift
- **Lazy OCR loading**: OCR models are loaded only when OCR is first needed (about 16 MB ONNX), so normal document conversion is unaffected; models are reused across processes
- **OCR models bundled with the app**: fully offline, with no network requests

## 🔨 Build the Installer from Source

```bash
build_installer.bat
```

This automatically performs: cleanup → dependency installation → PyInstaller (onedir) → Inno Setup. Output:

```text
release\MarkItDownConverter_Setup_2.1.0.exe
```

### Installer Features

- Fixed AppId → automatically upgrades/replaces older versions
- Detects running older versions (AppMutex + tasklist) and closes them before upgrading
- Preserves QSettings; uninstall does not delete user files
- Includes application icon, version information, and desktop shortcuts

## 🧪 Testing

```bash
.venv\Scripts\python -m pytest tests/ -q
```

66 tests cover: multiple MarkItDown formats (docx/xlsx/pptx/txt/csv/json/html), image OCR (Chinese/English/Spanish), scanned PDF OCR, OCR post-processing (line ordering/spacing/dehyphenation/multi-column/vertical text/paragraphs), XLSX NaN handling, ZIP path privacy, corrupted-file classification, unsupported-format blocking, Chinese paths, batch worker behavior (100 files), and the GUI start-button flow.

An additional dual test-suite acceptance run covers: 15 core format classes + 120-file batch + 15 corrupted files + security tests (zip-slip/script non-execution) + 20 stability checks + path handling (NFC/NFD/long paths), for a total of 236 assertions: 229 passed, with 7 intentional design differences (unknown formats are attempted via content-based detection), and no crashes / data loss / security vulnerabilities.

## 📁 Project Structure

```text
├── main.py              Entry point (GUI / --convert self-test / single-instance mutex)
├── gui.py               PySide6 UI (drag-and-drop, file list, progress, logs)
├── converter.py         Conversion core (MarkItDown → empty-content detection → OCR fallback → error classification)
├── ocr.py               Local OCR (RapidOCR lazy loading + pypdfium2 rendering)
├── ocr_postprocess.py   OCR reconstruction (line ordering / spacing / dehyphenation / paragraphs)
├── worker.py            Background thread + multi-process parallelism
├── format_registry.py   Central format registry (single source of truth)
├── logger.py            File logging (rotated at 10 MB × 3)
├── utils.py             Output paths / conflict strategy / .lnk resolution
├── version.py           Centralized version number
├── installer/           Inno Setup scripts
├── tests/               pytest test suite (66 tests)
└── build_installer.bat  One-click installer build
```

## 🤝 Contributing

Issues and PRs are welcome:

- For bug reports, please include: file type, reproduction steps, and `%LOCALAPPDATA%\MarkItDownConverter\logs\app.log`
- Code changes should keep `pytest tests/ -q` fully passing
- New format support should update both `format_registry.py` and the relevant tests

## 🙏 Acknowledgements

- [Microsoft MarkItDown](https://github.com/microsoft/markitdown) — core conversion engine
- [RapidOCR](https://github.com/RapidAI/RapidOCR) — offline OCR
- [PySide6](https://doc.qt.io/qtforpython-6/) / [PyInstaller](https://pyinstaller.org/) / [Inno Setup](https://jrsoftware.org/isinfo.php)
- [wordninja](https://github.com/keredson/wordninja) — long concatenated-word recovery

## 📄 License

[MIT](LICENSE)
