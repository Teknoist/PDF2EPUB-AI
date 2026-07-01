# Güvenlik Politikası

## Desteklenen sürümler

En son yayınlanan sürüm güvenlik düzeltmeleri alır.

## Güvenlik açığı bildirimi

Hassas ayrıntıları herkese açık issue olarak paylaşmayın. GitHub deposundaki
`Security` bölümünden özel güvenlik bildirimi açın. Bildirimde sürüm, yeniden
üretme adımları, etki ve mümkünse önerilen düzeltme bulunmalıdır.

## Veri güvenliği

- AI olmadan ve Ollama modlarında OCR metni yerel makinede kalır.
- Uzak API sağlayıcısında metin yapılandırılan sunucuya gönderilir.
- API anahtarları loglanmaz ve proje yapılandırmasına otomatik yazılmaz.
- PDF, EPUB, önbellek ve model dosyaları Git tarafından yok sayılır.
