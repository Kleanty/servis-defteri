#!/bin/bash
# Raspberry Pi / Debian / Ubuntu için ilk kurulum. Kendi kullanıcınla çalıştır (sudo ile DEĞİL):
#     bash scripts/kurulum.sh
# Yaptıkları: sanal ortam + bağımlılıklar, .env şablonu, systemd servis dosyasının üretilmesi.
# sudo gerektiren adımları (servisi kurma, yazıcı izni, cron) çalıştırmaz; sonda KOMUTLARI yazar.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
DIZIN="$(pwd)"; KULLANICI="$(id -un)"
[ "$KULLANICI" = "root" ] && { echo "root ile çalıştırma; normal kullanıcınla çalıştır."; exit 1; }

# ---- Hata yakalama: herhangi bir adim başarısız olursa data/kurulum-hata.txt dosyasına adım, satır, neden ve bilgisayar bilgisi yazılır.
mkdir -p data && chmod 700 data
LOG="$DIZIN/data/kurulum.log"; PIPLOG="$DIZIN/data/kurulum-pip.log"; RAPOR="$DIZIN/data/kurulum-hata.txt"
: > "$PIPLOG"; rm -f "$RAPOR"      # önceki başarısız denemenin raporu kalmasın
yaz() { printf '%s\n' "$*" | tee -a "$LOG"; }
ADIM="Başlangıç"; HATA_SATIR=""; HATA_KOMUT=""
adim() { ADIM="$*"; yaz "$*"; }
trap 'HATA_SATIR=$LINENO; HATA_KOMUT=$BASH_COMMAND' ERR
rapor_yaz() {
  local kod="$1" ipucu=() son
  son="$(tail -n 40 "$PIPLOG" 2>/dev/null || true)"
  local ham="$ADIM $HATA_KOMUT $son"
  grep -qiE 'ensurepip|python3-venv|venv kurulamad' <<<"$ham" && ipucu+=("python3-venv paketi eksik: sudo apt install -y python3-venv   (sonra betiği tekrar çalıştır)")
  grep -qiE 'Could not find a version|No matching distribution|Max retries|Connection|timed out|Temporary failure|SSL|certificate|ProxyError|Name or service not known' <<<"$ham" && ipucu+=("İnternet/bağlantı sorunu: sunucunun internete çıktığını kontrol et (ping -c1 pypi.org). Proxy varsa HTTPS_PROXY ayarla. Biraz bekleyip tekrar dene.")
  grep -qiE 'Failed building wheel|error: command .gcc|Python\.h|jpeg|zlib|Microsoft Visual|subprocess-exited-with-error' <<<"$ham" && ipucu+=("Paket derlenemedi (Pillow vb. için hazır paket yok): sudo apt install -y python3-dev build-essential libjpeg-dev zlib1g-dev   ya da Python 3.11/3.12 kullan.")
  grep -qiE 'No space left' <<<"$ham" && ipucu+=("Diskte yer yok: df -h ile bak, yer aç, tekrar dene.")
  grep -qiE 'Permission denied|PermissionError|Operation not permitted' <<<"$ham" && ipucu+=("İzin sorunu: klasör senin kullanıcına ait olmalı (ls -ld .). Daha önce sudo ile çalıştırıldıysa: sudo chown -R \$USER: . ve venv klasörünü silip tekrar dene.")
  grep -qiE 'python3 yok|Python 3.1[0-9] veya|sürüm' <<<"$ham" && ipucu+=("Python 3.10+ gerekir (3.11/3.12 önerilir): sudo apt install -y python3 python3-venv")
  [ ${#ipucu[@]} -eq 0 ] && ipucu+=("Otomatik bir neden bulunamadı. Bu raporun TAMAMINI gönder; adım, satır ve kayıt sonu çözümü bulmayı sağlar.")
  {
    echo "====================================================="
    echo " Servis Defteri kurulum hatası ($(basename "$0"))"
    echo "====================================================="
    echo "Zaman        : $(date '+%F %T')"
    echo "Çıkış kodu   : $kod"
    echo "Hata adımı   : $ADIM"
    [ -n "$HATA_SATIR" ] && echo "Betikte satır: $HATA_SATIR   komut: $HATA_KOMUT"
    echo; echo "--- OLASI NEDEN VE ÇÖZÜM ---"; printf ' * %s\n' "${ipucu[@]}"
    [ -n "$son" ] && { echo; echo "--- pip/python çıktısının sonu ---"; echo "$son"; }
    echo; echo "--- BİLGİSAYAR BİLGİSİ ---"
    echo "Sistem       : $(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-?}") ($(uname -m), çekirdek $(uname -r))"
    echo "Kullanıcı    : $(id -un)   Klasör: $DIZIN"
    echo "python3      : $(python3 -V 2>&1 || echo yok)  ($(command -v python3 || echo -))"
    echo "venv/ensurepip: $(python3 -c 'import venv, ensurepip; print("var")' 2>&1 | tail -n1)"
    echo "Disk (klasör): $(df -h "$DIZIN" 2>/dev/null | awk 'NR==2{print $4" boş / "$2" ("$5" dolu)"}')"
    echo "Bellek       : $(free -m 2>/dev/null | awk '/Mem:/{print $7" MB kullanılabilir / "$2" MB"}')"
    echo "Proxy        : ${HTTPS_PROXY:-${https_proxy:-yok}}"
    python3 - <<'PY' 2>&1
import urllib.request, urllib.error
for u in ("https://pypi.org", "https://files.pythonhosted.org"):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=8); print("İnternet     :", u, "-> OK", r.status)
    except urllib.error.HTTPError as e: print("İnternet     :", u, "-> ulaşıldı (HTTP %s)" % e.code)
    except Exception as e: print("İnternet     :", u, "-> ULAŞILAMADI", str(e)[:120])
PY
    echo; echo "--- KURULUM KAYDININ SONU ($LOG) ---"; tail -n 40 "$LOG" 2>/dev/null
    echo "====================================================="
  } > "$RAPOR" 2>&1
  echo
  echo "KURULUM TAMAMLANAMADI (çıkış kodu $kod) — hata adımı: $ADIM" | tee -a "$LOG"
  echo "Olası neden / çözüm:" | tee -a "$LOG"; printf ' * %s\n' "${ipucu[@]}" | tee -a "$LOG"
  echo "Tam rapor: $RAPOR   (çözemezsen bu dosyayı gönder)" | tee -a "$LOG"
}
trap 'k=$?; if [ $k -ne 0 ]; then rapor_yaz $k; fi' EXIT
yaz "=== Kurulum başladı $(date '+%F %T') ==="

adim "1/4  Gerekli paketler: sudo apt install -y python3-venv sqlite3 libusb-1.0-0   (kurulu değilse)"
command -v python3 >/dev/null || { yaz "python3 yok. Çalıştır: sudo apt install -y python3 python3-venv"; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { yaz "Python 3.10 veya daha yenisi gerekir (bulunan: $(python3 -V 2>&1))."; exit 1; }
python3 -c 'import sys; sys.exit(1 if sys.version_info >= (3, 13) else 0)' || yaz "     UYARI: Python 3.13+: Pillow için hazır paket yoksa derleme gerekebilir -> sudo apt install -y python3-dev libjpeg-dev zlib1g-dev. Önerilen: Python 3.11/3.12."
command -v sqlite3 >/dev/null || yaz "     UYARI: sqlite3 yok -> yedek alınamaz. sudo apt install -y sqlite3"

adim "2/4  Sanal ortam ve bağımlılıklar"
# yarım kalmış (python3-venv eksikken oluşan) venv'i yeniden kur
[ -x venv/bin/python ] || { rm -rf venv; python3 -m venv venv >>"$PIPLOG" 2>&1 || { yaz "venv kurulamadı. Çalıştır: sudo apt install -y python3-venv   sonra bu betiği tekrar çalıştır."; rm -rf venv; exit 1; }; }
venv/bin/pip install --disable-pip-version-check --quiet --upgrade pip >>"$PIPLOG" 2>&1 || yaz "     (pip güncellenemedi, önemli değil)"
if ! venv/bin/pip install --disable-pip-version-check -r requirements.txt >>"$PIPLOG" 2>&1; then
  yaz "     İlk deneme başarısız, 3 sn sonra tekrar deneniyor (ayrıntı: data/kurulum-pip.log)..."; tail -n 6 "$PIPLOG" | tee -a "$LOG"; sleep 3
  venv/bin/pip install --disable-pip-version-check -r requirements.txt >>"$PIPLOG" 2>&1
fi
venv/bin/python -c "import flask, waitress, qrcode, PIL" >>"$PIPLOG" 2>&1 || { ADIM="2/4  Paket doğrulaması (flask/waitress/qrcode/PIL yüklenemedi)"; exit 1; }

adim "3/4  .env"
if [ ! -f .env ]; then cp .env.example .env; chmod 600 .env; yaz "     .env oluşturuldu: işletme bilgilerini düzenle (nano .env)"; else yaz "     .env zaten var, dokunulmadı"; fi

adim "4/4  systemd servis dosyası üretiliyor: deploy/servis-defteri.service"
while IFS= read -r satir; do
  satir="${satir//KULLANICI/$KULLANICI}"; satir="${satir//DIZIN/$DIZIN}"; printf '%s\n' "$satir"
done < deploy/servis-defteri.service.example > deploy/servis-defteri.service

cat <<EOF | tee -a "$LOG"

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

Uygulama http://127.0.0.1:5000 adresinde çalışır. İnternete açmak için ters vekil/tünel gerekir (LINUX-KURULUM.md ve DOMAIN-BAGLAMA.txt).
EOF
