# Xyra imzalama ve notarization

Xyra self-build olduğu için varsayılan olarak ad-hoc imzalıdır. Sonuçları: antivirüs (Bitdefender/Avast) programı virüs sanabilir, macOS her sürümde keychain/izinleri sıfırlayabilir (GitHub girişi tekrar sorulur), Gatekeeper uyarısı çıkar.

Kök çözüm: Apple Developer ID ile imzalayıp notarize etmek. Zed'in `bundle-mac` scripti bunu zaten yapıyor; sadece kimlik bilgilerini environment değişkeni olarak vermek gerekiyor.

## Gerekenler (bir kez kurulum)

1. **Apple Developer Program üyeliği** (yıllık $99): https://developer.apple.com/programs/
2. **Developer ID Application sertifikası**:
   - Xcode veya developer.apple.com üzerinden "Developer ID Application" sertifikası oluştur.
   - Anahtar Zinciri'nden `.p12` olarak dışa aktar (bir parola belirle).
   - base64'e çevir: `base64 -i sertifika.p12 | pbcopy`
3. **App Store Connect API anahtarı** (notarytool için):
   - App Store Connect > Users and Access > Integrations > App Store Connect API > yeni anahtar (`.p8`).
   - Key ID, Issuer ID ve Team ID'yi not al.
   - base64'e çevir: `base64 -i AuthKey_XXXX.p8 | pbcopy`

## Kullanım

Derlemeden önce şu env değişkenlerini ayarla (örneğin `~/.zshrc`'ye ekle ya da build öncesi export et):

```bash
export XYRA_TEAM_ID="ABCDE12345"                 # Apple Team ID
export MACOS_CERTIFICATE="<p12 base64>"          # Developer ID Application .p12
export MACOS_CERTIFICATE_PASSWORD="<p12 parola>"
export APPLE_NOTARIZATION_KEY="<p8 base64>"      # App Store Connect API .p8
export APPLE_NOTARIZATION_KEY_ID="<key id>"
export APPLE_NOTARIZATION_ISSUER_ID="<issuer id>"
```

Sonra normal derleme:

```bash
./build/build-xyra.sh
```

Bu env'ler ayarlıysa bundle-mac otomatik olarak: hardened runtime ile deep-sign eder, notarytool ile Apple'a gönderir, ticket'i staple eder. Sonuç: AV artık flag'lemez, Gatekeeper uyarısı yok, keychain/izinler kalıcı olur.

Env ayarlı değilse ad-hoc imzalı build üretilir (mevcut davranış), hiçbir şey bozulmaz.
