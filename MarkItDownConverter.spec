# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.hooks import collect_data_files

datas = [('assets', 'assets')]
binaries = []
hiddenimports = []
hiddenimports += collect_submodules('markitdown')
hiddenimports += collect_submodules('pdfminer')
hiddenimports += collect_submodules('pdfplumber')
hiddenimports += collect_submodules('mammoth')
hiddenimports += collect_submodules('pptx')
hiddenimports += collect_submodules('openpyxl')
hiddenimports += collect_submodules('xlrd')
hiddenimports += collect_submodules('olefile')
# 本地 OCR：rapidocr 包 + ONNX 模型文件必须一起收集
tmp_ret = collect_all('rapidocr_onnxruntime')
# OCR 粘词恢复：wordninja 在 ocr_postprocess 中懒加载，需显式收集（含词表数据）
hiddenimports += ['wordninja']
import wordninja as _wordninja_mod
import os as _os
_wordninja_words = _os.path.join(
    _os.path.dirname(_wordninja_mod.__file__), 'wordninja', 'wordninja_words.txt.gz'
)
datas += [(_wordninja_words, 'wordninja')]
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
# magika 类型识别模型
tmp_ret = collect_all('magika')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
# PDF 页面渲染（扫描版 PDF OCR）
hiddenimports += collect_submodules('pypdfium2')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MarkItDownConverter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
    version='version_info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MarkItDownConverter',
)
