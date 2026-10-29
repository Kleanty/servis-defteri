#!/bin/bash
# Günlük SQLite yedeği. Elle:  ./scripts/backup.sh     Her gece 02:00:  bkz. LINUX-KURULUM.md (cron satırı)
# Yedekler data/yedekler/ altına gider. Klasördeki yedeklerin toplamı YEDEK_LIMIT_GB'ı (varsayılan 4) aşarsa
# en eski yedekler tek tek silinir (toplam %90'ın altına inene dek); en yeni 30 günlük yedekler asla silinmez.
# İsteğe bağlı kopyalar: (1) /mnt/yedek_usb bağlıysa oraya, (2) RCLONE_REMOTE tanımlıysa buluta.
set -euo pipefail
umask 077     # yedekler yalnız çalıştıran kullanıcıya açık
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_FILE="$APP_DIR/data/servis.db"
BACKUP_DIR="$APP_DIR/data/yedekler"
TARIH=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

# Kota: $1 klasöründeki servis_*.db toplamı limiti aşarsa en eskiyi tek tek sil (%90'a inene dek); 30 günden yeniler ve servis_SON.db korunur.
kota_uygula() {
    local dir="$1" limit_gb toplam limit hedef f boyut
    limit_gb="${YEDEK_LIMIT_GB:-$(grep -E '^YEDEK_LIMIT_GB=' "$APP_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)}"
    limit_gb="${limit_gb//,/.}"
    awk -v g="$limit_gb" 'BEGIN{exit !(g+0>0 && g+0<=100000)}' || limit_gb=4          # inf, 0, eksi, saçma değer → 4
    limit=$(awk -v g="$limit_gb" 'BEGIN{printf "%d", g*1024*1024*1024}')
    hedef=$(( limit * 9 / 10 ))
    toplam=$(find "$dir" -maxdepth 1 -type f -name 'servis_*.db' -printf '%s\n' 2>/dev/null | awk '{s+=$1} END{printf "%d", s}')
    [ "$toplam" -gt "$limit" ] || return 0
    while IFS= read -r f; do
        [ "$toplam" -gt "$hedef" ] || break
        boyut=$(stat -c %s "$f"); rm -f "$f" && toplam=$(( toplam - boyut )) && echo "Kota: eski yedek silindi: $(basename "$f")"
    done < <(find "$dir" -maxdepth 1 -type f -name 'servis_2*.db' -mtime +30 -printf '%T@ %p\n' 2>/dev/null | sort -n | head -n -3 | cut -d' ' -f2-)      # en yeni 3 yedek her zaman kalır
}
[ -f "$DB_FILE" ] || { echo "Veritabanı yok: $DB_FILE (uygulama henüz hiç çalışmamış)"; exit 1; }
GECICI="$BACKUP_DIR/servis_$TARIH.db.$$.tmp"; trap 'rm -f "$GECICI"' EXIT      # yarım yedek asla son adıyla görünmez
sqlite3 "$DB_FILE" ".backup '$GECICI'"
# Yedek bozuksa saklama: bütünlük denetiminden geçmeyeni sil ve hata ver (eski sağlam yedekler yerinde kalır)
if [ "$(sqlite3 "$GECICI" 'PRAGMA integrity_check;' 2>/dev/null | head -1)" != "ok" ]; then
    echo "HATA: yedek bütünlük denetiminden geçmedi, silindi."; exit 1
fi
mv "$GECICI" "$BACKUP_DIR/servis_$TARIH.db"
kota_uygula "$BACKUP_DIR"
echo "Yedek alındı: $BACKUP_DIR/servis_$TARIH.db"

# 3-2-1 kuralı: yedeğin en az bir kopyası SD kartın DIŞINDA durmalı (SD kartlar en sık bozulan parçadır).
# (1) USB bellek: fstab'a "UUID=xxxx-xxxx /mnt/yedek_usb ext4 defaults,nofail 0 2" ekleyip bağla. Takılı değilse adım atlanır.
USB_DIR="/mnt/yedek_usb"
if mountpoint -q "$USB_DIR" 2>/dev/null; then
    kota_uygula "$USB_DIR" || true          # önce yer aç: bellek dolmuşsa yeni yedek yine sığsın
    if cp "$BACKUP_DIR/servis_$TARIH.db" "$USB_DIR/.servis_$TARIH.tmp" 2>/dev/null && mv "$USB_DIR/.servis_$TARIH.tmp" "$USB_DIR/servis_$TARIH.db"; then echo "USB kopyası alındı."; else rm -f "$USB_DIR/.servis_$TARIH.tmp"; echo "USB'ye kopyalanamadı (yedek yine de yerelde mevcut)."; fi
    kota_uygula "$USB_DIR" || true
fi

# (2) Bulut (rclone): RCLONE_REMOTE ortam değişkeni veya .env içinde. Örn: RCLONE_REMOTE=gdrive:ServisDefteri-Yedek
RCLONE_REMOTE="${RCLONE_REMOTE:-$(grep -E '^RCLONE_REMOTE=' "$APP_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)}"
if [ -n "$RCLONE_REMOTE" ] && command -v rclone >/dev/null 2>&1; then
    if rclone copyto "$BACKUP_DIR/servis_$TARIH.db" "$RCLONE_REMOTE/servis_$TARIH.db" --retries 3 \
       && rclone copyto "$BACKUP_DIR/servis_$TARIH.db" "$RCLONE_REMOTE/servis_SON.db" --retries 3; then
        rclone delete "$RCLONE_REMOTE" --include 'servis_2*.db' --min-age 30d || true
        echo "Bulut yedeği alındı: $RCLONE_REMOTE"
    else
        echo "UYARI: Buluta yüklenemedi (internet/oturum?). Yedek yine de yerelde mevcut."
    fi
fi
