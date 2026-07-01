# PDF2EPUB AI

PDF2EPUB AI, taranmış veya görüntü tabanlı PDF kitapları temiz EPUB 3 dosyalarına
dönüştüren yerel bir masaüstü uygulamasıdır. Yeni bir OCR motoru geliştirmez;
Tesseract, OCRmyPDF, PaddleOCR veya EasyOCR çıktısını analiz eder ve isteğe bağlı
AI katmanıyla yalnızca OCR hatalarını düzeltir.

## Temel özellikler

- PySide6 masaüstü arayüzü ve PDF sürükle-bırak
- Açık **AI ile** / **AI olmadan** çalışma modları
- Türkçe karakter, tireleme, boşluk ve noktalama onarımı
- Ollama, OpenAI uyumlu API ve lokal komut sağlayıcıları
- AI başarısız olduğunda güvenli kural tabanlı geri dönüş
- Kesintiden sonra sayfa bazında devam etme
- AI modu değiştiğinde OCR yapmadan ham metni yeniden düzeltme
- Ham OCR / düzeltilmiş metin canlı karşılaştırması
- EPUB 3 içindekiler, metadata, CSS ve XHTML doğrulaması
- CLI, Windows başlatıcısı ve PyInstaller paketi

## Hızlı başlangıç - Windows

Kurulum gerektirmeyen paket için [Releases](https://github.com/Teknoist/PDF2EPUB-AI/releases/latest)
sayfasından `PDF2EPUB-AI-Windows-x64.zip` dosyasını indirin. ZIP'i çıkarıp
`PDF2EPUB-AI.exe` dosyasını çalıştırın. Tesseract OCR ve Türkçe dil verisi pakete
dahildir. AI'sız mod doğrudan çalışır; AI modu için Ollama ayrıca kurulmalıdır.

Kaynak koddan kurulum gereksinimleri: Python 3.12+, Tesseract OCR ve isteğe bağlı Ollama.

```powershell
git clone https://github.com/Teknoist/PDF2EPUB-AI.git
cd pdf2epub-ai
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1
```

Kurulumdan sonra `PDF2EPUB-AI.cmd` dosyasına çift tıklayın veya:

```powershell
scripts\run_gui.ps1
```

Ayrıntılı adımlar: [Windows kurulumu](docs/INSTALLATION_TR.md)

## Kullanım modları

### AI olmadan

Harici model gerektirmez. Türkçe sözlük, kelime frekansı, boşluk, noktalama,
paragraf ve satır sonu tireleme kurallarını kullanır. Hızlıdır ve düşük donanımlı
bilgisayarlarda çalışır.

### AI ile

Önce aynı deterministik kuralları uygular, ardından yerel veya uzak modele yalnızca
OCR düzeltmesi yaptırır. Model çıktısı uzunluk, benzerlik, tırnak biçimi ve sözlük
kontrollerinden geçmezse otomatik olarak kural tabanlı sonuca dönülür.

Yerel model kurulumu: [Ollama ve AI](docs/AI_SETUP_TR.md)

## CLI

```powershell
pdf2epub-ai input.pdf output.epub --ocr-engine tesseract --ai-provider rule --resume
```

AI ile:

```powershell
pdf2epub-ai input.pdf output.epub --config pdf2epub-ai.toml --resume
```

Kullanılabilir seçenekler:

```text
--ocr-engine  auto | ocrmypdf | paddleocr | tesseract | easyocr
--ai-provider rule | ollama | openai-compatible | local
--language    OCR dil kodu; Türkçe için tur
--resume      Kesilen işleme önbellekten devam et
--gpu         GPU destekli OCR motorunu tercih et
--verbose     Ayrıntılı günlük
--keep-temp   Ara görüntüleri koru
```

## Yapılandırma

`pdf2epub-ai.toml`:

```toml
[ocr]
engine = "tesseract"
language = "tur"
dpi = 300
split_double_pages = false

[ai]
provider = "ollama"
base_url = "http://localhost:11434"
model = "pdf2epub-ai"
timeout_seconds = 90

[epub]
title = "Kitap adı"
author = "Yazar"
language = "tr"
```

AI kullanmak istemiyorsanız `provider = "rule"` seçin.

## Geliştirme

```powershell
python -m pip install -e ".[ocr,gui,dev]"
python -m pytest
python -m ruff check src tests
python -m black --check src tests
python -m mypy src/pdf2epub_ai
```

Windows paketi:

```powershell
scripts\build_windows.ps1
```

## Belgeler

- [Kullanıcı rehberi](docs/USER_GUIDE_TR.md)
- [Windows kurulumu](docs/INSTALLATION_TR.md)
- [AI kurulumu](docs/AI_SETUP_TR.md)
- [Sorun giderme](docs/TROUBLESHOOTING_TR.md)
- [Katkı rehberi](CONTRIBUTING.md)
- [Güvenlik politikası](SECURITY.md)

## Gizlilik ve telif

AI olmadan ve Ollama ile kullanım tamamen yereldir. OpenAI uyumlu uzak bir API
seçildiğinde OCR metni yapılandırılan sunucuya gönderilir. Kullanıcı, dönüştürdüğü
belgelerin kullanım ve çoğaltma haklarından sorumludur. PDF ve EPUB dosyaları Git
tarafından varsayılan olarak yok sayılır.

## Lisans

[MIT](LICENSE)
