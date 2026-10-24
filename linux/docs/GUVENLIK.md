# Güvenlik

## Yerleşik önlemler
- **Varsayılan şifre yok.** İlk açılışta rastgele şifre üretilir (`data/ILK_SIFRE.txt`, izin 0600); `sifre_degistir.py` değiştirince dosyayı siler.
- Şifre **PBKDF2-SHA256, 600.000 tur** ile saklanır (`data/.password_hash`, 0600).
- `SECRET_KEY` ortamdan verilir ya da `data/.secret_key` olarak otomatik üretilir (0600).
- **CSRF** belirteci tüm POST formlarında; yanlış giriş sınırı dakikada 5/IP.
- Oturum 90 gün; **"Tüm cihazlardan çıkış"** tüm oturumları geçersiz kılar. Girişliyken sayfalar `no-store`.
- Başlıklar: CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`. Vitrin dışı sayfalar `noindex`.
- QR adresi tahmin edilemez token'dır; anonim sayfada müşteri adı maskelenir, **telefon gösterilmez**.

## Senin sorumluluğun
- `.env`, `data/` ve yedekleri **asla** repoya koyma.
- Üretimde HTTPS (Cloudflare Tunnel / ters vekil) kullan.
- Bootstrap **yerel** dosyadır (`static/vendor/`, lisansı yanında); dış CDN yok, CSP yalnızca kendi alan adına ve Google Haritalar çerçevesine izin verir.
- CSV dışa aktarma verisi müşteri bilgisi içerir; indirdiğin dosyaları güvenli sakla. Hücreler `= + - @` ile başlıyorsa Excel formül enjeksiyonuna karşı başına `'` konur.
- Yedekler müşteri verisi içerir; bulut yedeğini şifreli/özel depoda tut.
- Sızıntı kontrolü (GitHub deposundaki tests klasöründe; bu Windows paketinde yoktur): `python tests/genel_test.py` repoda kişisel/marka kalıntısı arar.

## Açık bildirim
Güvenlik açığı bulursan herkese açık issue yerine depo sahibine özel mesajla bildir.
