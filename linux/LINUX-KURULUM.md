# Kurulum

Raspberry Pi OS / Debian / Ubuntu için.

## 1. Kurulum
```bash
sudo apt install -y python3-venv sqlite3 libusb-1.0-0
# Zip'i çıkar (örn. ~/ServisDefteri) ve klasöre gir
cd ~/ServisDefteri
bash scripts/kurulum.sh
nano .env
```
Betik sudo kullanmaz; sonda çalıştırman gereken komutları yazar (servis, yazıcı izni, yedek cron'u).

## 2. Servis olarak çalıştırma (systemd)
```bash
sudo cp deploy/servis-defteri.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now servis-defteri
```
Uygulama Waitress ile `127.0.0.1:5000` üzerinde çalışır (`deploy/servis-defteri.service.example` içinde değiştirilebilir).

## 3. İlk giriş
İlk açılışta rastgele şifre üretilir: `sudo journalctl -u servis-defteri | grep -A1 "İLK KURULUM"` veya `data/ILK_SIFRE.txt`.
Hemen değiştir: `venv/bin/python scripts/sifre_degistir.py && sudo systemctl restart servis-defteri`.

**Cihaz adı:** Giriş yaptıktan sonra her telefon/bilgisayar bir kez ad ister (ör. "Usta telefonu"); kim neyi yaptığı **İstatistik → Hareketler** sayfasında 180 gün görünür. Kayıtta müşteri adı/telefonu tutulmaz. Ad sonradan aynı sayfadan değiştirilebilir.

## 4. İnternete açma
Telefondan QR okutulabilmesi için herkese açık bir adres gerekir. Öneri: **Cloudflare Tunnel** (port açmadan, ücretsiz TLS) veya Caddy/nginx ters vekil.
`alanadiniz.com` için adım adım anlatım: `DOMAIN-BAGLAMA.txt`. Adresi, site açıldıktan sonra `.env` içinde `PUBLIC_BASE_URL` olarak ver. TLS arkasında çerez `Secure` işaretlidir; yalnızca yerel ağda `http://` denerken `FORCE_HTTPS_COOKIE=0`.

## 5. Yedek
```bash
bash scripts/backup.sh          # data/ altındaki veritabanını yedekler (4 GB'ı aşınca en eskileri siler, en yeni 30 gün korunur; sınır: `YEDEK_LIMIT_GB`)
```
Otomatik: `kurulum.sh` sonunda yazdırdığı cron satırını ekle. İsteğe bağlı: USB (`/mnt/yedek_usb`) ve rclone (`RCLONE_REMOTE`).
Yeni sürüme geçerken `data/` klasörünü sürüm klasörünün **dışında** tut veya kopyala.

## 6. Güncelleme
Yeni sürümün dosyalarını klasörün üzerine kopyala (**`data/` ve `.env`'e dokunma**) → `venv/bin/pip install -r requirements.txt` → `sudo systemctl restart servis-defteri`. Veritabanı otomatik güncellenir.

## 7. Demo verisi
`venv/bin/python scripts/demo_veri.py` — sahte müşteri/araç/iş emri ekler (yalnızca boş veritabanında).

## 8. Entegrasyon API'si (isteğe bağlı)
Muhasebe programının iş emrine işlem/not/durum eklemesi için. Varsayılan **kapalıdır**. Açmak için `.env` içine uzun rastgele bir anahtar yaz ve servisi yeniden başlat:
```bash
venv/bin/python -c "import secrets;print(secrets.token_urlsafe(32))"   # çıkan değeri .env içinde ENTEGRASYON_API_ANAHTARI= satırına yaz
sudo systemctl restart servis-defteri
```
Adres: `https://alan-adin/api/v1/is-emirleri` (yalnızca HTTPS; ters vekil/tünel `X-Forwarded-Proto` göndermelidir, Cloudflare Tunnel gönderir). Belgeler: `docs/Servis-Defteri-Entegrasyon-API.pdf`, `docs/openapi.yaml`, `docs/ornekler/`. Deneme: `venv/bin/python scripts/entegrasyon_deneme.py` (demo kayıt ekler; `--temizle` siler). Başka bir bilgisayardan tek kayıt göndermek için `disaridan_gonder/disaridan_gonder.py` (yalnızca Python gerekir).
Emin olunamayan kayıtlar üst menüdeki **🔗 Eşleşmeyen** rozetinde bekler.
