# Güvenlik

## Yerleşik önlemler
- **Dükkânlar arası ayrım:** her dükkânın veritabanı ayrı dosyadır; oturumda dükkân numarası taşınır, başka dükkânın verisine sorgu yolu yoktur (testlerle doğrulanır). Hesaplar yalnızca yönetici tarafından açılır; geçici şifre bir kez gösterilir ve ilk girişte değiştirilir.
- Veri klasörü, veritabanları ve yedekler yalnızca servisi çalıştıran kullanıcıya açıktır (0700/0600). Giriş log'una kullanıcının yazdığı metin girmez (satır sonu sahteciliği ve yanlışlıkla yazılan şifre).
- Dükkân girişi **kullanıcı adı + şifre**; bilinmeyen kullanıcıda da aynı süre ve aynı mesaj, dakikada 5 yanlış deneme sınırı (IP ve kullanıcı adı başına). Şifre değişince, sıfırlanınca, hesap kapanınca ve "tüm cihazlardan çıkış"ta açık oturumlar düşer.
- **Varsayılan şifre yok.** İlk açılışta rastgele YÖNETİCİ şifresi üretilir (`data/ILK_SIFRE.txt`, izin 0600); `sifre_degistir.py` değiştirince dosyayı siler.
- Şifre **PBKDF2-SHA256, 600.000 tur** ile saklanır (`data/.password_hash`, 0600).
- `SECRET_KEY` ortamdan verilir ya da `data/.secret_key` olarak otomatik üretilir (0600).
- **CSRF** belirteci tüm POST formlarında; yanlış giriş sınırı dakikada 5/IP.
- Oturum 14 gün (9 günlük bayram tatili aşılsın diye); her girişte/kullanımda süre yeniden başlar, 14 gün hiç açılmazsa şifre sorulur. Reddedilen API isteklerinin hata kaydında (form ve JSON gövdelerinde) telefon, adres ve e-posta `***` olarak saklanır; kayıtlar giriş yapmış kullanıcıya Dış sistem > Reddedilen sekmesinde gösterilir. **"Tüm cihazlardan çıkış"** tüm oturumları geçersiz kılar. Girişliyken sayfalar `no-store`.
- **Cihaz adı ve Hareketler:** Her telefon/bilgisayar ilk girişte bir ad ister (ör. "Usta telefonu"); aynı ad birden çok cihazda kullanılabilir (ayırmak için yanında kısa kod görünür). Ad, tarayıcıda imzalı bir "cihaz kartı" olarak 400 gün saklanır. **İstatistik → Hareketler** sayfası kim/hangi cihaz/hangi IP'den ne yaptığını listeler (giriş-çıkış, iş emri, müşteri/araç ekleme-düzenleme-silme, şifre ve ayar değişiklikleri). Kayıtlarda müşteri adı ve telefon **tutulmaz**; yalnızca plaka/kayıt no. 180 gün sonra otomatik silinir. Not: bu kart tarayıcıya bağlıdır, donanım kimliği değildir; ortak şifreyi bilen biri başka ad seçebilir. Her dükkânın kayıtları kendi veritabanında tutulur, dükkânlar birbirini göremez. Bu bir hesap verebilirlik kaydıdır, kimlik doğrulama değildir.
- Dosya izinleri: uygulama `umask 077` ile çalışır; veritabanı, log ve yedek dosyaları yalnız çalıştıran kullanıcıya açıktır. Pakette `.gitignore` bulunur (`.env`, `data/`, `venv/` dışlanır).
- Başlıklar: CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`. Yalnızca vitrin (`/`) aramada çıkabilir; diğer tüm sayfalar `noindex`. Vitrin herkese açık sabit bir tanıtımdır: dükkân verisi, giriş formu ve dış kaynak içermez (görseller sunucudan, `static/vitrin/`).
- QR adresi tahmin edilemez token'dır; anonim sayfada müşteri adı maskelenir, **telefon gösterilmez**.

## Yazdırma ajanı (dükkân bilgisayarı)
- Ajan sunucuya dışarı doğru HTTPS ile bağlanır; dükkân bilgisayarında port açılmaz. Düz `http` ile anahtar kabul edilmez.
- Ajan anahtarı (`ya_<dükkân kodu>_…`) dükkâna özeldir, yalnızca yönetici üretir, sunucuda yalnızca SHA-256 özeti saklanır, API anahtarından bağımsızdır. Yalnızca o dükkânın yazdırma kuyruğunu görür/işler; müşteri verisi okuyamaz. Hatalı deneme sınırı vardır (10 deneme / 5 dk). Dükkân kapatılınca ya da anahtar yenilenince/kapatılınca çalışmaz.
- Kuyruktaki iş yalnızca etiketin yazıcı komutunu (plaka, QR bağlantısı, dükkân adı) içerir; telefon ve müşteri adı yoktur. Kuyruk kayıtları 7 gün sonra silinir. Ajan anahtarı dükkân bilgisayarında `ajan.env` içindedir; dosya yalnızca Yönetici/SYSTEM erişimine kısıtlanır.

## Senin sorumluluğun
- `.env`, `data/` ve yedekleri **asla** repoya koyma.
- Üretimde HTTPS (Cloudflare Tunnel / ters vekil) kullan; bu sürüm internete açık çalışmak için tasarlandı, HTTPS olmadan kullanma.
- Önüne bir ters vekil (nginx, Caddy, IIS) koyarsan `X-Forwarded-Proto` ve `CF-Connecting-IP` başlıklarını istemciden gelen hâliyle geçirme; vekilin kendisi yazsın. Uygulama bu başlıklara güvenir: istemci kendisi gönderebilirse HTTPS zorunluluğu ve yanlış deneme sınırı atlatılabilir. En güvenli yol yalnızca Cloudflare Tunnel ile yayın yapmak ve uygulamayı `127.0.0.1`'de dinletmektir.
- Yedekler tüm dükkânların müşteri verisini ve hesap özetlerini (`yonetim.db`) içerir; sunucu dışındaki kopyayı (rclone) özel ve şifreli tut.
- Bootstrap **yerel** dosyadır (`static/vendor/`, lisansı yanında); dış CDN yok, CSP yalnızca kendi alan adına ve Google Haritalar çerçevesine izin verir.
- CSV dışa aktarma verisi müşteri bilgisi içerir; indirdiğin dosyaları güvenli sakla. Hücreler `= + - @` ile başlıyorsa Excel formül enjeksiyonuna karşı başına `'` konur.
- Yedekler müşteri verisi içerir; bulut yedeğini şifreli/özel depoda tut.
- Sızıntı kontrolü (GitHub deposundaki tests klasöründe; bu Windows paketinde yoktur): `python tests/genel_test.py` repoda kişisel/marka kalıntısı arar.

## Açık bildirim
Güvenlik açığı bulursan herkese açık issue yerine depo sahibine özel mesajla bildir.
