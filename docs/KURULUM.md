# Kurulum

Raspberry Pi OS / Debian / Ubuntu için. Windows/macOS'ta da `python app.py` ile denenebilir.

## 1. Kurulum
```bash
sudo apt install -y python3-venv sqlite3 libusb-1.0-0
git clone https://github.com/KULLANICI/servis-defteri.git && cd servis-defteri
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

## 4. İnternete açma
Telefondan QR okutulabilmesi için herkese açık bir adres gerekir. Öneri: **Cloudflare Tunnel** (port açmadan, ücretsiz TLS) veya Caddy/nginx ters vekil.
Adresi `.env` içinde `PUBLIC_BASE_URL` olarak ver. TLS arkasında çerez `Secure` işaretlidir; yalnızca yerel ağda `http://` denerken `FORCE_HTTPS_COOKIE=0`.

## 5. Yedek
```bash
bash scripts/backup.sh          # data/ altındaki veritabanını yedekler (30 gün saklar)
```
Otomatik: `kurulum.sh` sonunda yazdırdığı cron satırını ekle. İsteğe bağlı: USB (`/mnt/yedek_usb`) ve rclone (`RCLONE_REMOTE`).
Yeni sürüme geçerken `data/` klasörünü sürüm klasörünün **dışında** tut veya kopyala.

## 6. Güncelleme
`git pull` → `venv/bin/pip install -r requirements.txt` → `sudo systemctl restart servis-defteri`. Veritabanı otomatik güncellenir.

## 7. Demo verisi
`venv/bin/python scripts/demo_veri.py` — sahte müşteri/araç/iş emri ekler (yalnızca boş veritabanında).
