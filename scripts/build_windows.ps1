$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = if (Test-Path ".venv\Scripts\python.exe") {
    ".venv\Scripts\python.exe"
} else {
    "python"
}

& $Python -m pip install -e ".[ocr,gui,package]"
& $Python -m PyInstaller --noconfirm --clean pdf2epub-ai.spec
Write-Host "Windows paketi: dist\PDF2EPUB-AI\PDF2EPUB-AI.exe" -ForegroundColor Green
