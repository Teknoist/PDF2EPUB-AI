# Ollama ve Yerel AI Kurulumu

## Ollama

Ollama Windows uygulamasını kurun ve servisin çalıştığını doğrulayın:

```powershell
ollama --version
ollama list
```

## Önerilen modeller

```powershell
ollama pull qwen3:8b
```

16 GB RAM ve 12 GB VRAM sınıfı bir sistemde daha yüksek kalite için:

```powershell
ollama pull qwen3:14b
ollama create pdf2epub-ai -f models/Modelfile
```

Arayüzde:

- Mod: `AI ile`
- Sağlayıcı: `Ollama`
- Sunucu: `http://localhost:11434`
- Model: `pdf2epub-ai` veya `qwen3:8b`

## GPU kontrolü

Bir dönüşüm başladıktan sonra:

```powershell
ollama ps
```

`PROCESSOR` alanı GPU kullanımını gösterir. Desteklenmeyen GPU'larda Ollama CPU'ya
dönebilir; işlev değişmez, yalnızca süre uzar.

## Uzak API

`OpenAI uyumlu` sağlayıcısını seçip sunucu, model ve API anahtarını girin. Bu modda
OCR metni ilgili sunucuya gönderilir. Gizli veya lisanslı belgelerde veri politikasını
kontrol edin.

## AI güvenlik kontrolleri

Model çıktısı doğrudan EPUB'a yazılmaz. Uzunluk ve metin benzerliği, tırnak işaretleri,
özel stil belirteçleri ve Türkçe kelime frekansı denetlenir. Kontrol başarısızsa o
sayfada deterministik sonuç kullanılır.
