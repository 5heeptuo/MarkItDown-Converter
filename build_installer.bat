@echo off
rem ============================================================
rem  MarkItDown Converter v2 一键构建
rem  1. 清理 build/dist/release
rem  2. 检查/安装依赖
rem  3. PyInstaller 构建 EXE
rem  4. 检查构建结果
rem  5. Inno Setup 生成安装包
rem ============================================================
cd /d "%~dp0"

rem 隔离外部 Python 环境（防止 Hermes/全局包污染打包）
set "PYTHONPATH="
set "PYTHONHOME="

echo ============================================
echo  MarkItDown Converter v2 build script
echo ============================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found. Please run:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo [1/5] Cleaning previous build ...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if not exist "release" mkdir release

echo [2/5] Installing dependencies ...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [3/5] Building application (PyInstaller onedir) ...
".venv\Scripts\pyinstaller.exe" --noconfirm --clean MarkItDownConverter.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo [4/5] Checking build output ...
if not exist "dist\MarkItDownConverter\MarkItDownConverter.exe" (
    echo [ERROR] Build output missing: dist\MarkItDownConverter\MarkItDownConverter.exe
    pause
    exit /b 1
)

set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo [ERROR] Inno Setup 6 not found: %ISCC%
    pause
    exit /b 1
)

echo [5/5] Building installer (Inno Setup) ...
"%ISCC%" /Q "installer\MarkItDownConverter.iss"
if errorlevel 1 (
    echo [ERROR] Installer build failed.
    pause
    exit /b 1
)

echo.
echo Build OK!
echo Output: release\MarkItDownConverter_Setup_2.0.0.exe
pause
