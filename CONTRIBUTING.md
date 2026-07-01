# Katkı Rehberi

## Geliştirme ortamı

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[ocr,gui,dev]"
```

## Değişiklik süreci

1. Tek bir davranışa odaklanan dal oluşturun.
2. Davranış değişiklikleri için test ekleyin.
3. OCR düzeltme kurallarını yalnızca yüksek güvenli örneklerle genişletin.
4. AI promptunda yazarın üslubunu değiştirecek talimatlar kullanmayın.
5. Aşağıdaki kontrolleri çalıştırın.

```powershell
python -m pytest
python -m ruff check src tests
python -m black --check src tests
python -m mypy src/pdf2epub_ai
```

## Pull request

PR açıklaması davranış değişikliğini, gerekçeyi, testleri ve kullanıcı etkisini
belirtmelidir. Telifli PDF/EPUB, model ağırlığı, API anahtarı veya yerel önbellek
commit etmeyin.
