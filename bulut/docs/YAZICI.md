# Etiket yazdırma (Bluetooth, telefondan)

Tek etiket türü: **58 × 40 mm, yatay** (solda büyük QR, sağda dükkân adı ve plaka), TSPL dilini anlayan termal yazıcılar için (örn. Xprinter XP-470B).

Bu sürümde sunucu internette olduğu için yazıcıya **bağlanmaz**. Etiketi sunucu hazırlar (`POST /araclar/<id>/tspl`); dükkândaki **telefon**, yazıcıya Bluetooth ile gönderir.

## Gerekenler
- **Android + Chrome.** iPhone/Safari tarayıcıda Bluetooth yazdırmayı desteklemez.
- **HTTPS ile açılmış adres.** `http://` adreste Chrome Bluetooth'u kapatır (Cloudflare Tunnel: `DOMAIN-BAGLAMA.txt`).
- **BLE destekli yazıcı.** Chrome yalnızca "Bluetooth Low Energy" yazıcılarla konuşur; yalnızca klasik Bluetooth (SPP) olan yazıcılarda bu yöntem çalışmaz. Yazıcı listede görünmüyorsa veya "yazılabilir kanal bulunamadı" çıkıyorsa yazıcı BLE değildir.
- Yazıcı açık, etiket takılı; telefona başka bir uygulamayla bağlı olmamalı.

## Kullanım
Panelde araç → **Etiket** → **📲 Etiketi Bluetooth ile çıkart** → ilk seferde listeden yazıcıyı seç → etiket çıkar. Seçim sayfa açık kaldığı sürece hatırlanır. Adet düğmeleri geçerlidir.

## Nasıl gönderiyor?
Telefon yazıcıya GATT ile bağlanır, bilinen servisleri (`FF00`, `FFE0`, `18F0`, `49535343-…`) dener ve yazılabilir ilk karakteristiğe etiket komutlarını küçük parçalar halinde yazar. Gerçek bir yazıcıyla ilk deneme kullanıcı tarafından doğrulanmalıdır; yazıcı modeline göre servis farklı olabilir.

## Ayarlar (`.env`, isteğe bağlı)
Etikette dükkânın adı yazar (yönetici sayfasındaki ad; en fazla 18 karakter, Türkçe harfler ASCII'ye çevrilir).
Etiket kayık/ters çıkarsa: `ETIKET_X_OFFSET` (varsayılan 24 = 3 mm sağa), `ETIKET_Y_OFFSET` (varsayılan 16 = 2 mm aşağı), `ETIKET_YON` (0/1), `ETIKET_GAP_MM`, `ETIKET_YOGUNLUK` (1-15). 8 nokta = 1 mm.

## Alternatif: dükkân bilgisayarındaki USB yazıcı (yazdırma ajanı)
Yazıcı dükkândaki bir bilgisayara USB ile takılıysa Bluetooth gerekmez. O bilgisayarda çalışan küçük **ajan**, sunucuya kendisi bağlanıp kuyruktaki etiketi alır ve yazıcıya ham TSPL olarak gönderir (port açmak/VPN gerekmez). Kurulum ve ayrıntılar: `BULUT-KURULUM.md` bölüm 8 ve `yazdirma_ajani/AJAN-KURULUM.txt`. Etiket ekranındaki **🖨️ Dükkân bilgisayarından bas** düğmesi yalnızca yönetici o dükkân için ajan anahtarı ürettiyse görünür.
