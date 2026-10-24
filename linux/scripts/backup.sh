#!/bin/bash
# Günlük SQLite yedeği. Elle:  ./scripts/backup.sh     Her gece 02:00:  bkz. LINUX-KURULUM.md (cron satırı)
# Yedekler data/yedekler/ altına gider, 30 günden eskileri silinir.
# İsteğe bağlı kopyalar: (1) /mnt/yedek_usb bağlıysa oraya, (2) RCLONE_REMOTE tanımlıysa buluta.
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_FILE="$APP_DIR/data/servis.db"
BACKUP_DIR="$APP_DIR/data/yedekler"
TARIH=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"
[ -f "$DB_FILE" ] || { echo "Veritabanı yok: $DB_FILE (uygulama henüz hiç çalışmamış)"; exit 1; }
sqlite3 "$DB_FILE" ".backup '$BACKUP_DIR/servis_$TARIH.db'"
# Yedek bozuksa saklama: bütünlük denetiminden geçmeyeni sil ve hata ver (eski sağlam yedekler yerinde kalır)
if [ "$(sqlite3 "$BACKUP_DIR/servis_$TARIH.db" 'PRAGMA integrity_check;' 2>/dev/null | head -1)" != "ok" ]; then
    rm -f "$BACKUP_DIR/servis_$TARIH.db"; echo "HATA: yedek bütünlük denetiminden geçmedi, silindi."; exit 1
fi
find "$BACKUP_DIR" -type f -name 'servis_*.db' -mtime +30 -delete
echo "Yedek alındı: $BACKUP_DIR/servis_$TARIH.db"

# 3-2-1 kuralı: yedeğin en az bir kopyası SD kartın DIŞINDA durmalı (SD kartlar en sık bozulan parçadır).
# (1) USB bellek: fstab'a "UUID=xxxx-xxxx /mnt/yedek_usb ext4 defaults,nofail 0 2" ekleyip bağla. Takılı değilse adım atlanır.
USB_DIR="/mnt/yedek_usb"
if mountpoint -q "$USB_DIR" 2>/dev/null; then
    cp "$BACKUP_DIR/servis_$TARIH.db" "$USB_DIR/" 2>/dev/null && echo "USB kopyası alındı." || echo "USB'ye kopyalanamadı (yedek yine de yerelde mevcut)."
    find "$USB_DIR" -type f -name 'servis_*.db' -mtime +30 -delete 2>/dev/null || true
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
