$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.12 veya daha yeni bir surum bulunamadi. https://python.org adresinden kurun."
}

$Version = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$Parts = $Version.Split('.')
if ([int]$Parts[0] -lt 3 -or ([int]$Parts[0] -eq 3 -and [int]$Parts[1] -lt 12)) {
    throw "Python 3.12+ gerekli. Bulunan surum: $Version"
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install -e ".[ocr,gui]"

Write-Host ""
Write-Host "PDF2EPUB AI kuruldu." -ForegroundColor Green
if (-not (Get-Command tesseract -ErrorAction SilentlyContinue)) {
    Write-Warning "Tesseract bulunamadi. docs/INSTALLATION_TR.md belgesindeki kurulumu tamamlayin."
}
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Warning "AI modu icin Ollama bulunamadi. AI olmadan mod hemen kullanilabilir."
}
Write-Host "Uygulamayi PDF2EPUB-AI.cmd ile baslatin."
