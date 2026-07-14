# Xyra Agent talimatları

## Dil
Kullanıcıyla **Türkçe** konuş. Açıklamalar, özetler ve sohbet Türkçe olsun. Kod, kod içi tanımlayıcılar, commit mesajları ve teknik dosya adları İngilizce kalır. Türkçe yazarken tüm diakritik işaretleri doğru kullan (ç, ğ, ı, ö, ş, ü).

## Kod kuralları
- Asla kod yorumu yazma. Ne `//`, `#`, `/* */`, docstring ne de JSX yorumu. Gerekçe commit mesajına veya PR açıklamasına gider, koda değil.
- Em dash karakterini (—) hiçbir çıktıda kullanma: ne kodda, ne metinde, ne commit'te. Normal tire, virgül veya cümleyi yeniden kur.
- TypeScript öncelikli. Web için Next.js App Router ve Tailwind v4; Solana için web3.js ve Anchor.

## UI metni
- UI'da ALL-CAPS kelime yok. Sadece cümle düzeni (ilk harf büyük). Tailwind'de `uppercase` sınıfı ekleme, mevcutsa kaldır.

## Next.js
- i18n Dictionary nesnesini (interpolator fonksiyonları taşıyan) Server Component'ten Client Component'e prop olarak geçirme. Prod'da digest 500 verir. Client component'ler çeviriyi context'ten `useT()` ile alır.

## Para ve Solana
- Para her zaman en küçük birimde integer: TRY için kuruş, SOL için lamport, USDC için 10^6 birim. Para üzerinde float aritmetiği kritik hatadır.
- Solana'da hedef adresi asla işlem geçmişinden kopyalama (address-poisoning). Adresler yalnızca kanonik config, environment değişkeni veya doğrulanmış sabitten gelir.

## Çalışma tarzı
- Yeni bir şey yazmadan önce mevcut bir çözümü ara ve uyarla. Battle-tested kütüphaneleri el yapımı yardımcılara tercih et.
- Diff'i minimal ve odaklı tut. Görevin gerektirmediği kodu yeniden biçimlendirme veya yeniden adlandırma.
