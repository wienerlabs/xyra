<p align="center">
  <img src="assets/xyra-icon.png" width="128" alt="Xyra">
</p>

<h1 align="center">Xyra</h1>

<p align="center">Wiener Labs'ın dahili kod editörü. Zed tabanlı, Grok Build ve Claude Code entegre, yapay zeka öncelikli.</p>

## Ne kurar

`install.sh` hiçbir binary dağıtmaz; her şeyi resmi kaynaklardan kurar ve üzerine Wiener yapılandırmasını giydirir:

- Zed editörü (resmi Homebrew cask), Xyra adı ve simgesiyle
- Grok Build CLI (xAI resmi cask) ve Zed agent paneline ACP entegrasyonu
- JetBrains Mono Nerd Font, VSCode tuş düzeni, Zeta tab tamamlama ayarı
- `xyra` terminal komutu

Kurulum sonrası tek panelde üç katman kullanılır: Grok Build (abonelik kotası, 8 paralel agent), Claude Code (yerleşik) ve istenirse yerel Ollama modelleri.

## Gereksinimler

- macOS ve [Homebrew](https://brew.sh)
- Grok Build için kişisel SuperGrok veya X Premium+ aboneliği
- İsteğe bağlı: Claude Code hesabı, Ollama

## Kurulum

```bash
git clone https://github.com/wienerlabs/xyra.git
cd xyra
./install.sh
```

macOS ilk çalıştırmada Terminal için "Uygulama Yönetimi" izni isteyebilir; izin verip scripti tekrar çalıştırmak yeterlidir.

## İlk açılış

1. Terminalde `grok login --oauth` çalıştırın ve kendi X hesabınızla giriş yapın. Kota aboneliğinizden düşer, API anahtarı gerekmez.
2. Xyra'yı açın, sağ üstten GitHub ile giriş yapın. Bu, Zeta tab tamamlamayı etkinleştirir.
3. Agent panelini açın (cmd+?), + menüsünden Grok Build'i seçin. Claude Code da aynı menüde yerleşik gelir.

Kota takibi için Grok Build içinde `/usage` komutunu kullanın.

## Güncelleme

Xyra kendi içinden otomatik güncellenir; Homebrew'a bağlı değildir (kurulum scripti brew kaydını bilinçli olarak kaldırır, böylece `brew upgrade` yanlışlıkla ikinci bir Zed.app kuramaz).

Temiz yeniden kurulum gerekirse:

```bash
./update.sh
```

## İsteğe bağlı: yerel modeller

Makinede Ollama varsa `~/.config/zed/settings.json` içine şu blok eklenerek yerel modeller inline asistan ve commit mesajı üretiminde kullanılabilir:

```json
{
  "agent": {
    "inline_assistant_model": { "provider": "ollama", "model": "qwen2.5-coder:32b" },
    "commit_message_model": { "provider": "ollama", "model": "qwen2.5-coder:32b" }
  },
  "language_models": {
    "ollama": {
      "api_url": "http://localhost:11434",
      "available_models": [
        {
          "name": "qwen2.5-coder:32b",
          "display_name": "Qwen2.5 Coder 32B (lokal)",
          "max_tokens": 32768,
          "supports_tools": true
        }
      ]
    }
  }
}
```

## Sorun giderme

- **Simge veya yeniden adlandırma engellendi**: Sistem Ayarları > Gizlilik ve Güvenlik > Uygulama Yönetimi altında Terminal'e izin verin, scripti tekrar çalıştırın. Simge için manuel yol: uygulamayı Finder'da seçip cmd+I, sol üstteki küçük simgeye tıklayın, `assets/xyra-icon.png` dosyasını Önizleme'de açıp cmd+A cmd+C ile kopyalayın ve Get Info penceresinde cmd+V ile yapıştırın.
- **Menü çubuğunda "Zed" yazması**: normaldir. Uygulama imzasını bozmamak için bundle içine dokunulmaz; yalnızca ad, simge ve yapılandırma değiştirilir.
- **Grok modeli görünmüyor**: `grok models` çalıştırın; aboneliğinizin aktif olduğunu doğrulayın.
- **Font görünmüyor**: `brew install --cask font-jetbrains-mono-nerd-font` sonrası Xyra'yı yeniden başlatın.

## Lisans ve dağıtım notu

Bu repo Zed veya Grok Build binary'si içermez ve dağıtmaz; kurulum resmi kaynaklardan yapılır. Zed, [zed-industries/zed](https://github.com/zed-industries/zed) deposunda GPLv3 ile lisanslanmış açık kaynak bir projedir; Xyra bu projenin markasız yerel bir kurulumudur ve Zed Industries ile bir bağlantısı yoktur. Grok Build, xAI'nin resmi dağıtımıdır ve kullanımı xAI'nin koşullarına tabidir. Bu repodaki script ve yapılandırma dosyaları MIT lisanslıdır.
