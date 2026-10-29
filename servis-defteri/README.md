# 🔧 Servis Defteri

**Küçük oto servisler için tek ekranlı iş emri ve servis geçmişi uygulaması.**
Telefondan kullanılır, dükkandaki bir Windows bilgisayarda ya da Linux/Raspberry Pi'de çalışır, bulut aboneliği gerektirmez.

[English summary below](#english-summary)

> ⚠️ **Lisans: yalnızca inceleme.** Bu depodaki kodu okuyabilirsin; çalıştırmak, kullanmak, kopyalamak veya dağıtmak için izin yoktur. Ayrıntı: [LICENSE](LICENSE).

![Servis Defteri – panel (Windows, mavi tema)](docs/screenshots/windows/03-panel.png)

---

## Ne işe yarar?

Küçük bir servisin en büyük derdi **kayıt tutmak**: "Bu araç en son ne zaman geldi, ne yapıldı?" Servis Defteri bunu
**araç geldiği anda 10 saniyede** kayda alır ve müşteriye **kendi aracının servis geçmişini gösteren bir QR kartı** verir.

Tasarım ilkesi: **usta elleri yağlıyken telefonla kullanabilmeli.** Az alan, büyük düğme, ezber gerektirmeyen akış.
Yeni iş emri için **yalnızca plaka ve giriş km** zorunludur; müşteri adı, telefon, marka ve model isteğe bağlıdır.

## Depo yapısı: Windows, Linux ve çok dükkânlı (bulut) ayrı klasörler

| Klasör | Ne için | Kurulum |
|---|---|---|
| [`windows/`](windows) | Dükkandaki Windows 10/11 bilgisayar | [`WINDOWS-KURULUM.txt`](windows/WINDOWS-KURULUM.txt) — `SERVIS-DEFTERI-KUR.bat` ile tek tıkla |
| [`linux/`](linux) | Raspberry Pi / Debian / Ubuntu | [`LINUX-KURULUM.md`](linux/LINUX-KURULUM.md) — `bash scripts/kurulum.sh` |
| [`bulut/`](bulut) | **Çok dükkânlı**: internete açık tek Linux sunucu, her dükkân kendi kullanıcı adı + şifresiyle | [`BULUT-KURULUM.md`](bulut/BULUT-KURULUM.md) — `bash scripts/kurulum.sh` |

İki klasörde uygulama (`app.py`, `templates/`, `static/`) aynıdır; yalnızca kurulum, çalıştırma ve yedek betikleri
platforma göre farklıdır. Her klasör kendi başına bir pakettir. `bulut/` ise aynı uygulamanın **çok dükkânlı** halidir (aşağıda). Ayırt etmek için renk paketleri farklıdır: **Windows mavi**, **Linux yeşil**. Alan adı bağlama (Cloudflare Tunnel) için her klasörde `DOMAIN-BAGLAMA.txt` vardır.

### Çok dükkânlı sürüm (`bulut/`)

Tek sunucuda birden fazla dükkân: her dükkân **kendi kullanıcı adı ve şifresiyle** girer, verisi **tamamen ayrı** bir veritabanı dosyasındadır (başkası göremez). Hesapları yalnızca yönetici açar (`/yonetici`): geçici şifre üretilir, dükkân ilk girişte kendi şifresini seçer; unutulursa yönetici sıfırlar. Sunucu yazıcıya doğrudan bağlanmaz: etiket ya dükkândaki **Bluetooth (BLE) yazıcıya telefondan** ya da dükkân bilgisayarındaki **USB yazıcıya küçük bir yazdırma ajanı ile** basılır (ajan sunucuya dışarı doğru bağlanır; modemden port açmak gerekmez). Sunucuda dükkân başına otomatik yedek (`scripts/backup.py`), dükkân kendi yedeğini panelden indirebilir, geri yükleme yöneticidedir (`scripts/geri_yukle.py`). İsteğe bağlı **entegrasyon API'si** dükkân başınadır: anahtarı yalnızca yönetici üretir, anahtar hangi dükkânın verisine yazılacağını belirler. Vitrin sayfası ve sunucuya doğrudan USB yazıcı bu sürümde yoktur; ajanın Windows kurulum sihirbazı (`yazdirma_ajani/AJAN-KUR.bat`) yalnızca dükkân bilgisayarı içindir.

| Yönetici: dükkân aç | Dükkân girişi | İlk giriş: şifre seç | Etiket: bilgisayardan / Bluetooth ile bas |
|---|---|---|---|
| ![Yönetici](docs/screenshots/bulut/02-yonetici-yeni-dukkan.png) | ![Giriş](docs/screenshots/bulut/03-dukkan-giris.png) | ![Şifre](docs/screenshots/bulut/04-ilk-giris-sifre-sec.png) | ![Etiket](docs/screenshots/bulut/08-etiket-ekrani.png) |

| Yönetici: dükkâna API anahtarı | Dış sistem: karar bekleyen kayıtlar | Yönetici: yazdırma ajanı anahtarı |
|---|---|---|
| ![API](docs/screenshots/bulut/12-yonetici-api-anahtari.png) | ![Dış sistem](docs/screenshots/bulut/13-eslesmeyen-kayitlar.png) | ![Ajan](docs/screenshots/bulut/16-yonetici-ajan-anahtari.png) |
| ![Reddedilen](docs/screenshots/bulut/19-dis-sistem-reddedilen.png) | | |

**Bulut: ana sayfa (vitrin).** Siteyi açan ziyaretçi önce Servis Defteri'nin kısa tanıtımını görür (özellikler, nasıl çalışır, sık sorulanlar, iletişim); sağ üstteki **Usta / Dükkân girişi** düğmesi dükkân girişine, en alttaki düğme yönetici girişine götürür. Vitrinde dükkân verisi ve giriş formu yoktur; giriş yapmış usta `/` adresinde doğrudan panele gider. İletişim e-postası `.env` içindeki `VITRIN_EPOSTA` ile değişir (`-` yazarsan bölüm gizlenir).

| Ana sayfa: telefon | Ana sayfa: bilgisayar |
|---|---|
| ![Vitrin telefon](docs/screenshots/bulut/17-vitrin-telefon.png) | ![Vitrin bilgisayar](docs/screenshots/bulut/18-vitrin-bilgisayar.png) |

**Bulut: dükkân bilgisayarındaki USB yazıcı (yazdırma ajanı).** Yazıcı dükkânda bilgisayara USB ile takılıysa (Bluetooth yok) yönetici dükkân için bir *ajan anahtarı* üretir (sağdaki görüntü), dükkân bilgisayarında `bulut/yazdirma_ajani/AJAN-KUR.bat` çalıştırılır; ajan sunucuya dışarı doğru bağlanıp etiketi alır ve yazıcıya gönderir (port açmak/VPN yok). Etiket ekranında yeşil **Dükkân bilgisayarından bas** düğmesi çıkar (üstteki tablodaki dördüncü görüntü); Bluetooth düğmesi de yerinde durur. Ayrıntı: [`bulut/BULUT-KURULUM.md`](bulut/BULUT-KURULUM.md) bölüm 8.

| Bu cihaza ad ver | Hareketler |
|---|---|
| ![Cihaz adı](docs/screenshots/bulut/14-cihaz-adi.png) | ![Hareketler](docs/screenshots/bulut/15-hareketler.png) |

## Genel işleyiş

```
Araç gelir ──► Plaka + giriş km ──► Araç/müşteri otomatik bulunur (yoksa açılır)
      │
      ▼
  İşlemler seçilir (sık yapılanlar tek dokunuş) ──► İş emri açılır
      │
      ▼
  Devam Ediyor ──► "Araç hazır" WhatsApp mesajı ──► Teslim Et (= Tamamlandı)
      │
      ▼
  Araç etiketi (QR) yazdırılır ──► sonraki gelişte QR okutulur, geçmiş görünür
```

1. **Vitrin sayfası (`/`)** – Herkese açık tanıtım: açık/kapalı rozeti, ara / WhatsApp / yol tarifi. `.env` ile ayarlanır.
2. **Usta paneli** – Şifre korumalı: açık işler, müşteriler, araçlar, istatistik.
3. **QR servis kartı (`/arac/<token>`)** – Araca özel, tahmin edilemez adres. Müşteri geçmişi görür (kişisel bilgiler maskeli); usta girişliyse Ara / Haber Et / Yeni İş Emri çubuğu çıkar.
4. **Etiket yazdırma** – 58×40 mm yatay QR etiketi, USB TSPL termal yazıcıya tek dokunuşla (Xprinter XP-470B). Sunucu evde, yazıcı dükkânda ise telefondan Bluetooth (BLE) ile de basılabilir (Android Chrome + HTTPS, bkz. `docs/YAZICI.md`). Bulut sürümünde yazıcı dükkân bilgisayarında USB ile takılıysa küçük bir **yazdırma ajanı** etiketi sunucudan alıp basar.

## Özellikler

- Tek ekranda **hızlı iş emri** (plaka biçimi doğrulama, araç/müşteri otomatik bulma)
- **İşlem seçici**: sık yapılanlar öğrenilir, kategoriler, kendi işlemini ekleme ("Eklediklerim")
- Durum akışı: Beklemede → Devam Ediyor → Tamamlandı (araç teslim edilince)
- Para takibi bilinçli olarak yoktur; yalnızca servis kaydı tutulur
- İsteğe bağlı **entegrasyon API'si** (varsayılan kapalı, yalnızca HTTPS + API anahtarı): muhasebe programı plakadaki tek açık iş emrine işlem, durum ve not ekler; yeni iş emri açmaz, emin olunamayanlar "Dış sistem" sayfasında (Karar bekleyen) onay bekler, reddedilen istekler aynı sayfadaki Reddedilen sekmesinde görünür. Windows ve Linux'ta; API belgesi (PDF), OpenAPI, 5 dilde örnek kod ve dışarıdan deneme aracı `docs/` ile `DISARIDAN-GONDER` klasöründedir
- **WhatsApp şablonları**, arama, istatistik, **Excel/CSV dışa aktarma**, **Silinenler** (30 gün geri alınabilir), **Hareketler** (hangi cihaz ne yaptı; İstatistik sayfasında, 180 gün)
- **Yedek**: gece otomatik yedek; Windows'ta USB bellek ve Google Drive, Linux'ta USB ve rclone seçenekleri
- **Çevrimdışı çalışır** (Bootstrap yerel dosyadır), telefonda öncelikli arayüz, Türkçe
- **Kolay sorun giderme**: kurulum bir adımda takılırsa ekranda hangi adım olduğu ve olası çözüm yazılır; tek bir hata raporu dosyası (adım, satır, Windows/Python/disk/internet bilgisi, kayıt sonu) oluşur ve gönderilebilir (Windows: masaüstünde `SERVIS-DEFTERI-KURULUM-HATASI.txt`; Linux/bulut: `data/kurulum-hata.txt`)

## Ekran görüntüleri (Windows, mavi tema)

| | | |
|---|---|---|
| ![Vitrin](docs/screenshots/windows/01-vitrin.png) <br> Vitrin | ![Giriş](docs/screenshots/windows/02-giris.png) <br> Giriş | ![Panel](docs/screenshots/windows/03-panel.png) <br> Panel |
| ![Yeni iş emri](docs/screenshots/windows/04-yeni-is-emri.png) <br> Hızlı iş emri | ![İşlem seçici](docs/screenshots/windows/05-islem-secici.png) <br> İşlem seçici | ![İş emirleri](docs/screenshots/windows/06-is-emirleri.png) <br> İş emirleri |
| ![Araçlar](docs/screenshots/windows/07-araclar.png) <br> Araçlar | ![Müşterinin araçları](docs/screenshots/windows/08-musteri-araclari.png) <br> Müşterinin araçları | ![QR müşteri](docs/screenshots/windows/09-qr-musteri.png) <br> QR kartı (müşteri) |
| ![QR usta](docs/screenshots/windows/10-qr-usta.png) <br> QR kartı (usta girişli) | ![Etiket](docs/screenshots/windows/11-etiket-ekrani.png) <br> Etiket ekranı | ![İstatistik](docs/screenshots/windows/12-istatistik.png) <br> İstatistik |
| ![Düzenle](docs/screenshots/windows/13-is-emri-duzenle.png) <br> İş emri düzenle | ![Eklediklerim](docs/screenshots/windows/15-eklediklerim.png) <br> Eklediklerim | ![Dışa aktar](docs/screenshots/windows/16-disa-aktar.png) <br> Dışa aktarma |
| ![Dış sistem](docs/screenshots/windows/17-eslesmeyen-kayitlar.png) <br> Dış sistem: karar bekleyen kayıtlar | ![Cihaz adı](docs/screenshots/windows/18-cihaz-adi.png) <br> Bu cihaza ad ver | ![Hareketler](docs/screenshots/windows/19-hareketler.png) <br> Hareketler (hangi cihaz ne yaptı) |
| ![Reddedilen](docs/screenshots/windows/20-dis-sistem-reddedilen.png) <br> Dış sistem: reddedilen istekler | | |

Masaüstü görünümü: [14-masaustu-is-emirleri.png](docs/screenshots/windows/14-masaustu-is-emirleri.png) · Linux (yeşil tema; cihaz adı ve hareketler dahil) görüntüleri: [`docs/screenshots/linux/`](docs/screenshots/linux)

| Linux (yeşil) | | |
|---|---|---|
| ![Panel](docs/screenshots/linux/03-panel.png) | ![İş emirleri](docs/screenshots/linux/06-is-emirleri.png) | ![Etiket](docs/screenshots/linux/11-etiket-ekrani.png) |

> Ekran görüntülerindeki tüm isimler, plakalar ve telefonlar uydurmadır.

## Teknoloji

Python 3 · Flask 3 · Waitress · SQLite (WAL) · Jinja2 · Bootstrap 5.3 (yerel) · qrcode/Pillow · pyusb (Linux) / pywin32 (Windows); çok dükkânlı sürümde sunucu USB'ye yazmaz (Web Bluetooth ya da dükkân bilgisayarındaki yazdırma ajanı).
Tek dosyalık uygulama (`app.py`), veritabanı `data/` altında.

## Durum

- **Windows ve Linux sürümleri** gerçek servislerde günlük kullanımda çalışıyor (Linux: Raspberry Pi + Xprinter XP-470B ile donanımda test edildi).
- **Windows** yazdırma yolu ve kurulum betikleri otomatik testlerle (sahte yazıcı) doğrulandı; ilk gerçek yazdırma `windows\ETIKET-DENEME.bat` ile doğrulanmalıdır.
- **Çok dükkânlı sürüm** otomatik testlerle (dükkânlar arası izolasyon, yönetici, yedek/geri yükleme) doğrulandı; Bluetooth yazdırma ve yazdırma ajanı (kuyruk, kimlik, süre dolumu, ajan programı gerçek HTTP sunucusuyla) sahte yazıcıyla denendi; **gerçek yazıcıyla ilk deneme yapılmalıdır** (Bluetooth için yazıcı BLE desteklemelidir; ajan için `AJAN-DENEME.bat`; ajan kurulum sihirbazı gerçek Windows'ta denenmedi).
- Otomatik testler (`tests/`) her push'ta GitHub Actions ile üç klasör için de koşar.

## Güvenlik özeti

Şifre PBKDF2-SHA256 (600.000 tur) · CSRF koruması · yanlış giriş sınırı · "tüm cihazlardan çıkış" · cihaz adı + hareket kaydı · güvenlik başlıkları ·
panel arama motorlarına kapalı · QR sayfasında müşteri adı maskeli. İlk açılışta rastgele yönetici şifresi üretilir (sabit şifre yoktur).
**`.env` ve `data/` klasörünü asla GitHub'a yükleme** (`.gitignore` dışlar). Ayrıntı: [GUVENLIK.md](linux/docs/GUVENLIK.md).

## Testler

```bash
cd linux      # ya da: cd windows / cd bulut
pip install -r requirements.txt
for t in tests/*.py; do python "$t"; done
```

## Lisans

**Yalnızca inceleme (view-only).** Kod bu depoda okunabilir; kullanım, kopyalama, değiştirme ve dağıtım için yazılı izin gerekir. Ayrıntı: [LICENSE](LICENSE).

## İletişim
Kullanım izni, soru veya iş birliği için: **ahmet.taner.2002@hotmail.com**

---

## English summary

**Servis Defteri** ("Service Ledger") is a lightweight, self-hosted job-card and service-history app for **small independent auto repair shops**.
A mechanic opens a work order from a phone in ~10 seconds (only **plate and entry mileage are required**), tracks status, sends WhatsApp
notifications and hands the customer a **QR service card** (plus a printable 58×40 mm thermal label) showing the vehicle's service history with masked personal data.

Three self-contained packages: [`windows/`](windows) (one-click installer, scheduled task, USB/Google Drive backup), [`linux/`](linux) (systemd, Raspberry Pi) and [`bulut/`](bulut) (multi-shop: one internet-facing Linux server, each shop signs in with its own username/password and gets a fully separate database; admin creates accounts; labels are printed from the shop's phone over Bluetooth LE, or from the shop PC's USB printer via a small outbound-only print agent).
Stack: Flask 3, Waitress, SQLite, Jinja2, Bootstrap 5. UI language: Turkish.

**License: view-only.** The source is public for inspection; it is not licensed for use, copying, modification or distribution. See [LICENSE](LICENSE).

**Contact:** ahmet.taner.2002@hotmail.com (permission requests, questions, collaboration).
