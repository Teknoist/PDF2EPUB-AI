# Windows Kurulumu

## 1. Python

Python 3.12 veya daha yeni bir sürüm kurun. Kurulum sırasında `Add Python to PATH`
seçeneğini etkinleştirin.

```powershell
python --version
```

## 2. Tesseract OCR

Windows için Tesseract 5 kurun ve Türkçe `tur.traineddata` dil dosyasının
`tessdata` klasöründe bulunduğunu doğrulayın.

```powershell
tesseract --list-langs
```

Listede `tur` görünmelidir. Tesseract PATH üzerinde değilse uygulamayı yeniden
başlatın veya kurulum klasörünü PATH'e ekleyin.

## 3. Uygulama

```powershell
git clone https://github.com/Teknoist/PDF2EPUB-AI.git
cd pdf2epub-ai
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1
```

Script `.venv` oluşturur ve OCR ile GUI bağımlılıklarını kurar.

## 4. Başlatma

`PDF2EPUB-AI.cmd` dosyasına çift tıklayın veya:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_gui.ps1
```

## 5. AI modu

AI olmadan mod kurulumdan hemen sonra kullanılabilir. Yerel AI için
[AI kurulum rehberini](AI_SETUP_TR.md) izleyin.

## Windows EXE üretimi

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

Çıktı `dist/PDF2EPUB-AI/PDF2EPUB-AI.exe` altında oluşur. Tesseract ve Ollama harici
uygulamalardır; EXE paketine gömülmezler.
