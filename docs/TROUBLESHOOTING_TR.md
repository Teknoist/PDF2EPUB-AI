# Sorun Giderme

## OCR motoru bulunamadı

```powershell
tesseract --version
tesseract --list-langs
```

Komut bulunmuyorsa Tesseract klasörünü PATH'e ekleyin ve uygulamayı yeniden başlatın.

## Türkçe dil dosyası yok

`tur.traineddata` dosyasını Tesseract `tessdata` klasörüne yerleştirin. Uygulamada
OCR dili Türkçe seçiliyken `tur` kullanılır.

## AI sunucusuna bağlanılamıyor

```powershell
ollama list
ollama serve
```

Model adının arayüzde ve `ollama list` çıktısında aynı olduğundan emin olun.

## İşlem çok yavaş

- 300 DPI kullanın.
- Çift sayfa ayırmayı yalnızca gerektiğinde açın.
- `AI olmadan` moduyla bir temel çıktı oluşturun.
- Daha küçük bir model seçin.
- `ollama ps` ile GPU kullanımını kontrol edin.

## İşlem kesildi

Aynı PDF ve çıktı yolunu seçin, `Kesilen işlemi sürdür` seçeneğini açık bırakın.
Kaynak PDF değişirse güvenli biçimde yeni önbellek oluşturulur.

## EPUB okuyucuda açılmıyor

İşlem günlüğündeki EPUB doğrulama hatasını inceleyin. Çıktıyı yeniden oluştururken
başlık ve dosya yolunda geçersiz Windows karakterleri kullanmayın.

## Günlükler

Arayüzdeki `İşlem günlüğü` sekmesi son 3000 satırı tutar. CLI için `--verbose`
seçeneğini kullanın.
