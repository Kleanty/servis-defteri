# Güvenlik

## Yerleşik önlemler
- **Varsayılan şifre yok.** İlk açılışta rastgele şifre üretilir (`data/ILK_SIFRE.txt`, izin 0600); `sifre_degistir.py` değiştirince dosyayı siler.
- Şifre **PBKDF2-SHA256, 600.000 tur** ile saklanır (`data/.password_hash`, 0600).
- `SECRET_KEY` ortamdan verilir ya da `data/.secret_key` olarak otomatik üretilir (0600).
- **CSRF** belirteci tüm POST formlarında; yanlış giriş sınırı dakikada 5/IP.
- Oturum 14 gün (9 günlük bayram tatili aşılsın diye); her girişte/kullanımda süre yeniden başlar, 14 gün hiç açılmazsa şifre sorulur. Reddedilen API isteklerinin hata kaydında (form ve JSON gövdelerinde) telefon, adres ve e-posta `***` olarak saklanır; kayıtlar giriş yapmış kullanıcıya Dış sistem > Reddedilen sekmesinde gösterilir. **"Tüm cihazlardan çıkış"** tüm oturumları geçersiz kılar. Girişliyken sayfalar `no-store`.
- **Cihaz adı ve Hareketler:** Her telefon/bilgisayar ilk girişte bir ad ister (ör. "Usta telefonu"); aynı ad birden çok cihazda kullanılabilir (ayırmak için yanında kısa kod görünür). Ad, tarayıcıda imzalı bir "cihaz kartı" olarak 400 gün saklanır. **İstatistik → Hareketler** sayfası kim/hangi cihaz/hangi IP'den ne yaptığını listeler (giriş-çıkış, iş emri, müşteri/araç ekleme-düzenleme-silme, "tüm cihazlardan çıkış"). Kayıtlarda müşteri adı ve telefon **tutulmaz**; yalnızca plaka/kayıt no. 180 gün sonra otomatik silinir. Not: bu kart tarayıcıya bağlıdır, donanım kimliği değildir; ortak şifreyi bilen biri başka ad seçebilir. Bu bir hesap verebilirlik kaydıdır, kimlik doğrulama değildir.
- **Yedek kotası (Windows/Linux):** Yerel yedek klasörü, USB ve ek yedek klasörünün her birinde yedeklerin toplamı 4 GB'ı (`YEDEK_LIMIT_GB`) aşarsa en eski yedekler tek tek silinir, toplam 3,6 GB'ın altına inince durur. En yeni 30 günün yedekleri ve `servis_SON.db` asla silinmez. Google Drive'da 30 günden eskiler silinir.
- Paketteki `.gitignore` `.env`, `data/` ve `venv/` klasörlerini dışlar; GitHub'a yüklerken sırlar yanlışlıkla gitmez.
- Başlıklar: CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`. Vitrin dışı sayfalar `noindex`.
- QR adresi tahmin edilemez token'dır; anonim sayfada müşteri adı maskelenir, **telefon gösterilmez**.

## Senin sorumluluğun
- `.env`, `data/` ve yedekleri **asla** repoya koyma.
- Üretimde HTTPS (Cloudflare Tunnel / ters vekil) kullan.
- Önüne bir ters vekil (nginx, Caddy, IIS) koyarsan `X-Forwarded-Proto` ve `CF-Connecting-IP` başlıklarını istemciden gelen hâliyle geçirme; vekilin kendisi yazsın. Uygulama bu başlıklara güvenir: istemci kendisi gönderebilirse HTTPS zorunluluğu ve yanlış deneme sınırı atlatılabilir. En güvenli yol yalnızca Cloudflare Tunnel ile yayın yapmak ve uygulamayı `127.0.0.1`'de dinletmektir.
- Bootstrap **yerel** dosyadır (`static/vendor/`, lisansı yanında); dış CDN yok, CSP yalnızca kendi alan adına ve Google Haritalar çerçevesine izin verir.
- CSV dışa aktarma verisi müşteri bilgisi içerir; indirdiğin dosyaları güvenli sakla. Hücreler `= + - @` ile başlıyorsa Excel formül enjeksiyonuna karşı başına `'` konur.
- Yedekler müşteri verisi içerir; bulut yedeğini şifreli/özel depoda tut.
- Sızıntı kontrolü (GitHub deposundaki tests klasöründe; bu Windows paketinde yoktur): `python tests/genel_test.py` repoda kişisel/marka kalıntısı arar.

## Açık bildirim
Güvenlik açığı bulursan herkese açık issue yerine depo sahibine özel mesajla bildir.
