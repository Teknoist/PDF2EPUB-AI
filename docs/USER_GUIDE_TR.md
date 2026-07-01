# Kullanıcı Rehberi

## Yeni dönüşüm

1. PDF dosyasını kaynak alanına bırakın veya `PDF seç` düğmesini kullanın.
2. Kitap başlığını, yazarı ve EPUB dilini kontrol edin.
3. Üst bölümden `AI ile` veya `AI olmadan` modunu seçin.
4. OCR motorunu `auto` bırakabilir veya kurulu motoru seçebilirsiniz.
5. EPUB hedefini belirleyin ve `Dönüştür` düğmesine basın.

İşlem sırasında son sayfanın ham ve düzeltilmiş metni yan yana gösterilir. Günlük
sekmesi AI geri dönüşlerini ve OCR durumunu içerir.

## AI olmadan

Bu mod harici AI sunucusuna bağlanmaz. Büyük kitaplarda en hızlı seçenektir.
Türkçe sözlük ve güvenli kurallar kullanılır.

## AI ile

AI sağlayıcısı alanında Ollama, OpenAI uyumlu API veya lokal komut seçilebilir.
Ollama için varsayılan adres `http://localhost:11434` değeridir.

## Devam etme

`Kesilen işlemi sürdür` açık olduğunda her tamamlanan sayfa önbellekten yüklenir.
AI modu veya model değişirse OCR tekrarlanmaz; önbellekteki ham metin yeni modla
yeniden düzeltilir.

## İptal

`İptal` geçerli OCR veya AI çağrısı tamamlandıktan sonra işlemi durdurur. Önceden
tamamlanan sayfalar korunur.

## Önerilen ayarlar

| Belge | OCR | DPI | Çift sayfa |
| --- | --- | ---: | --- |
| Temiz tarama | auto / tesseract | 300 | Kapalı |
| Düşük çözünürlük | tesseract / paddleocr | 400 | Kapalı |
| İki sayfalı tarama | auto | 300 | Açık |
| Metin katmanlı PDF | auto | 300 | Kapalı |

600 DPI çoğu kitapta gereksiz bellek ve süre tüketir. Önce 300 DPI deneyin.
