@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "PDF2EPUB AI" ".venv\Scripts\pythonw.exe" -m pdf2epub_ai.ui.app
  exit /b 0
)
pythonw -m pdf2epub_ai.ui.app
if errorlevel 1 (
  echo PDF2EPUB AI baslatilamadi.
  echo Once scripts\install_windows.ps1 dosyasini calistirin.
  pause
)
