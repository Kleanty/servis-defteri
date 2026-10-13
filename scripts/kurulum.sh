#!/bin/bash
# Raspberry Pi / Debian / Ubuntu için ilk kurulum. Kendi kullanıcınla çalıştır (sudo ile DEĞİL):
#     bash scripts/kurulum.sh
# Yaptıkları: sanal ortam + bağımlılıklar, .env şablonu, systemd servis dosyasının üretilmesi.
# sudo gerektiren adımları (servisi kurma, yazıcı izni, cron) çalıştırmaz; sonda KOMUTLARI yazar.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
DIZIN="$(pwd)"; KULLANICI="$(id -un)"
[ "$KULLANICI" = "root" ] && { echo "root ile çalıştırma; normal kullanıcınla çalıştır."; exit 1; }

echo "1/4  Gerekli paketler: sudo apt install -y python3-venv sqlite3 libusb-1.0-0   (kurulu değilse)"
command -v python3 >/dev/null || { echo "python3 yok"; exit 1; }
command -v sqlite3 >/dev/null || echo "     UYARI: sqlite3 yok -> yedek alınamaz. sudo apt install -y sqlite3"

echo "2/4  Sanal ortam ve bağımlılıklar"
[ -d venv ] || python3 -m venv venv
venv/bin/pip install --quiet --upgrade pip
venv/bin/pip install --quiet -r requirements.txt

echo "3/4  .env"
if [ ! -f .env ]; then cp .env.example .env; chmod 600 .env; echo "     .env oluşturuldu: işletme bilgilerini düzenle (nano .env)"; else echo "     .env zaten var, dokunulmadı"; fi

echo "4/4  systemd servis dosyası üretiliyor: deploy/servis-defteri.service"
while IFS= read -r satir; do
  satir="${satir//KULLANICI/$KULLANICI}"; satir="${satir//DIZIN/$DIZIN}"; printf '%s\n' "$satir"
done < deploy/servis-defteri.service.example > deploy/servis-defteri.service

cat <<EOF

Kurulum hazır. Şimdi şu komutları sırayla çalıştır:

  # 1) Servisi kur ve başlat
  sudo cp $DIZIN/deploy/servis-defteri.service /etc/systemd/system/
  sudo systemctl daemon-reload && sudo systemctl enable --now servis-defteri.service

  # 2) İLK GİRİŞ ŞİFRESİ (rastgele üretildi, bir kez gösterilir):
  sudo journalctl -u servis-defteri -n 30 --no-pager | grep -A1 "İLK KURULUM"
  #    (ya da: cat $DIZIN/data/ILK_SIFRE.txt). Girdikten sonra şifreni değiştir:
  $DIZIN/venv/bin/python $DIZIN/scripts/sifre_degistir.py && sudo systemctl restart servis-defteri

  # 3) Günlük yedek (her gece 02:00)
  (crontab -l 2>/dev/null | grep -v 'servis-defteri-yedek'; echo "0 2 * * * $DIZIN/scripts/backup.sh >> $DIZIN/data/yedekler/backup.log 2>&1 # servis-defteri-yedek") | crontab -

  # 4) USB etiket yazıcısı kullanacaksan (isteğe bağlı)
  sudo cp $DIZIN/deploy/99-etiket.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger

Uygulama http://127.0.0.1:5000 adresinde çalışır. İnternete açmak için ters vekil/tünel gerekir (docs/KURULUM.md).
EOF
