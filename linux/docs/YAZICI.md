# Etiket yazıcı

Tek etiket türü: **58 × 40 mm, yatay** (solda büyük QR, sağda işletme adı ve plaka). TSPL dilini anlayan USB termal yazıcılar için.

> ✅ **Gerçek donanımda test edildi: Xprinter XP-470B** (203 dpi, USB, TSPL) — Raspberry Pi 4B üzerinde, uygulamadan tek dokunuşla.

## Kurulum
1. Yazıcıyı Pi'ye USB ile bağla, aç, 58×40 mm etiket rulosunu tak.
2. Paketler: `sudo apt install -y libusb-1.0-0` (kurulum betiği `pyusb`'ı sanal ortama kurar).
3. İzin kuralı: `sudo cp deploy/99-etiket.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger`, sonra yazıcıyı çıkarıp tak ve servisi yeniden başlat.
4. Panelde araç → **Etiket** → **🖨️ Yazıcıdan Çıkart (USB)**. Sağ üstteki rozet yazıcının "Hazır" olup olmadığını gösterir.

## Nasıl gönderiyor?
1. **Doğrudan USB (pyusb):** Yazıcı bulunur (varsayılan kimlik XP-470B için `2d37:82c5`, `ETIKET_USB_ID` ile değiştirilebilir; yoksa yazıcı/üretici sınıflı ilk USB aygıtı aranır). Linux'un `usblp` sürücüsü gerekirse ayrılır ve ham TSPL gönderilir. Bazı yazıcılar `/dev/usb/lp0` üzerinden yazıyı kabul edip yanıt vermez; bu yüzden bu yol önceliklidir.
2. **Yedek yol:** USB izni yok ya da pyusb kurulu değilse `/dev/etiket` veya `/dev/usb/lp*` denenir.
3. `.env` içinde `ETIKET_AYGIT=/dev/xxx` verirsen yalnızca o aygıt kullanılır.

Yazıcı kapalı, kapak açık ya da kâğıt bitmişse uygulama donmaz; 8 saniye içinde anlaşılır bir hata gösterir. Art arda çift dokunuş 3 saniye engellenir.

## Telefondan Bluetooth ile yazdırma (sunucu evde, yazıcı dükkânda)

Sunucu (bilgisayar) evde, yazıcı dükkânda ise etiket sayfasındaki **“📲 Telefondan Bluetooth ile çıkart”** düğmesi kullanılır. Etiketi sunucu hazırlar; telefon (dükkânda, yazıcının yanında) yazıcıya doğrudan Bluetooth ile gönderir. Yazıcının sunucuya bağlı olması gerekmez.

Gerekenler:

- **Android + Chrome.** iPhone/Safari tarayıcıda Bluetooth yazdırmayı desteklemez.
- **HTTPS ile açılmış adres** (alan adı / Cloudflare tüneli; bkz. `DOMAIN-BAGLAMA.txt`). `http://` adreste Chrome Bluetooth’u kapatır.
- **BLE destekli yazıcı.** Chrome yalnızca “Bluetooth Low Energy” yazıcılarla konuşur; yalnızca klasik Bluetooth (SPP) olan yazıcılarda bu yöntem çalışmaz. Düğmeye basınca yazıcı listede görünmüyorsa veya “yazılabilir kanal bulunamadı” çıkıyorsa yazıcı BLE değildir; USB kullan.
- Yazıcı açık ve telefona başka bir uygulamayla bağlı olmamalı.

Kullanım: düğmeye bas → listeden yazıcıyı seç (ilk seferde) → etiket çıkar. Seçim sayfa açık kaldığı sürece hatırlanır. Adet düğmeleri Bluetooth için de geçerlidir.

Bu yöntem etiketi `58x40 mm` TSPL komutlarıyla gönderir; yazıcı ayarları (`.env`) USB ile aynıdır. Yaygın BLE servisleri (`FF00`, `FFE0`, `18F0`, `49535343…`) otomatik denenir. Gerçek yazıcıyla ilk deneme kullanıcı tarafından doğrulanmalıdır.

## Başka bir yazıcı kullanıyorsan
`lsusb` çıktısındaki `xxxx:yyyy` kimliğini `.env` içine `ETIKET_USB_ID=xxxx:yyyy` olarak yaz. Yazıcı TSPL konuşmuyorsa (yalnızca ESC/POS ya da ZPL) etiket çıkmaz.

## Ayar (`.env`)
| Değişken | Anlamı | Varsayılan |
|---|---|---|
| `ETIKET_BASLIK` | Etikette yazan ad (en fazla 18 karakter, Türkçe harfler ASCII'ye çevrilir; ilk kelime üst satıra, kalanı alta) | `SERVIS DEFTERI` |
| `ETIKET_X_OFFSET` | Sağa(+)/sola(−) kaydırma, nokta (8 nokta = 1 mm) | `24` (3 mm sağa) |
| `ETIKET_Y_OFFSET` | Aşağı(+)/yukarı(−) kaydırma, nokta | `16` (2 mm aşağı) |
| `ETIKET_YON` | `DIRECTION` 0 veya 1 (etiket ters çıkarsa değiştir) | `1` |
| `ETIKET_GAP_MM` | Etiketler arası boşluk | `3` |
| `ETIKET_YOGUNLUK` | Koyuluk 1–15 | `8` |
| `ETIKET_USB_ID` | Yazıcının USB kimliği | `2d37:82c5` |
| `ETIKET_AYGIT` | Elle aygıt yolu (USB yolu devre dışı kalır) | otomatik |

Varsayılan kaydırma XP-470B + 58×40 mm rulo için ayarlanmıştır. Kendi yazıcında etiket kayık çıkarsa önce `ETIKET_X_OFFSET` ve `ETIKET_Y_OFFSET` değerlerini değiştir.
Plaka uzun ya da yabancıysa yazı tipi otomatik küçülür, etiketten taşmaz.

Bluetooth ile telefondan yazdırma ve QR indirme seçenekleri ekrandan kaldırıldı; etiket yalnızca USB etiket yazıcısından çıkar.
