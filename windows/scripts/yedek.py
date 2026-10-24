#!/usr/bin/env python3
"""SQLite yedeği (Windows ve Linux). Elle:  python scripts/yedek.py
Her yedek şu yerlere gider (hangisi varsa):
  1) data/yedekler/servis_YYYYMMDD_HHMMSS.db   (her zaman; 30 günden eskiler silinir)
  2) USB bellek: birim adı SERVISYEDEK olan sürücü takılıysa  <sürücü>:\\ServisDefteriYedek\\   (ad .env'de USB_YEDEK_ADI ile değişir)
  3) Google Drive: windows\\DRIVE-YEDEK-KUR.bat ile kurulduysa  Drive > ServisDefteriYedek  (rclone; yalnızca yeni dosyalar yüklenir)
  4) .env'de YEDEK_KLASORU=D:\\Yedek verilmişse o klasör
Yedek, uygulama çalışırken de güvenle alınır (SQLite yedekleme arayüzü) ve bütünlüğü doğrulanır.
Seçenekler:  --duzenli  (15 dakikada bir çalışan görev: USB takıldıysa / Drive'a gitmemiş yedek varsa gerekeni yapar)"""
import glob, os, shutil, sqlite3, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortam import KOK, env_yukle, utf8_cikti

SAKLAMA_GUN = 30
LOKAL_SAAT = 12                       # yerel yedek bu kadar saatten eskiyse 15 dk'lık kontrol yenisini alır
YENILE_SAAT = 6                       # USB/Drive için en geç bu kadar saatte bir taze yedek
USB_ADI = 'SERVISYEDEK'
BULUT_UZAK = 'servisdrive:ServisDefteriYedek'


def _log(kok, mesaj):
    """data/yedek.log: aktarım hataları burada kalır (sonraki turda yeniden denenir)."""
    try:
        yol = os.path.join(kok, 'data', 'yedek.log'); os.makedirs(os.path.dirname(yol), exist_ok=True)
        if os.path.exists(yol) and os.path.getsize(yol) > 200_000: os.replace(yol, yol + '.eski')
        with open(yol, 'a', encoding='utf-8') as f: f.write('%s  %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), mesaj))
    except OSError: pass


def _eskileri_sil(klasor):
    sinir = time.time() - SAKLAMA_GUN * 86400
    for f in os.listdir(klasor):
        if f.startswith('servis_') and f.endswith('.db') and f != 'servis_SON.db':
            yol = os.path.join(klasor, f)
            try:
                if os.path.getmtime(yol) < sinir: os.remove(yol)
            except OSError: pass


def _yas_saat(yol):
    try: return (time.time() - os.path.getmtime(yol)) / 3600
    except OSError: return 1e9


def _norm(s): return ''.join(c for c in str(s).lower() if c.isalnum())


# ----------------------------------------------------------------- USB
def usb_bul():
    """Birim adı USB_YEDEK_ADI (varsayılan SERVISYEDEK; büyük/küçük harf ve boşluk önemsiz) olan takılı sürücünün kökü, yoksa None."""
    ad = _norm(os.environ.get('USB_YEDEK_ADI') or USB_ADI)
    elle = os.environ.get('USB_YEDEK_YOLU', '').strip()                 # Linux/deneme: doğrudan klasör
    if elle: return elle if os.path.isdir(elle) else None
    if os.name == 'nt':
        try:
            import ctypes
            k32 = ctypes.windll.kernel32; k32.SetErrorMode(1)            # boş kart okuyucuda "disk tak" penceresi çıkmasın
            maske = k32.GetLogicalDrives()
            for i in range(26):
                if not (maske >> i) & 1: continue
                kok = chr(65 + i) + ':\\'
                if k32.GetDriveTypeW(kok) not in (2, 3): continue         # 2 çıkarılabilir, 3 sabit (bazı USB diskler öyle görünür)
                tampon = ctypes.create_unicode_buffer(261)
                if k32.GetVolumeInformationW(kok, tampon, 261, None, None, None, None, 0) and _norm(tampon.value) == ad: return kok
        except Exception: pass                                           # noqa: BLE001
        return None
    for yol in glob.glob('/media/*') + glob.glob('/media/*/*') + glob.glob('/run/media/*/*') + glob.glob('/Volumes/*'):
        if os.path.isdir(yol) and _norm(os.path.basename(yol)) == ad: return yol
    return None


def usb_kopyala(dosya, usb, kok=KOK):
    try: open(os.path.join(kok, 'data', 'usb_deneme.txt'), 'w').write(time.strftime('%Y-%m-%d %H:%M:%S'))
    except OSError: pass
    hedef = os.path.join(usb, 'ServisDefteriYedek'); os.makedirs(hedef, exist_ok=True)
    shutil.copy2(dosya, os.path.join(hedef, os.path.basename(dosya)))
    shutil.copy2(dosya, os.path.join(hedef, 'servis_SON.db'))           # SON en sona yazılır: tarih damgası "bitti" demektir
    _eskileri_sil(hedef)
    return hedef


# ----------------------------------------------------------------- Google Drive (rclone)
def _rclone(kok):
    klasor = os.path.join(kok, 'data', 'rclone')
    exe = os.path.join(klasor, 'rclone.exe' if os.name == 'nt' else 'rclone')
    if not os.path.exists(exe): exe = shutil.which('rclone') or ''
    conf = os.path.join(klasor, 'rclone.conf')
    try: kurulu = '[servisdrive]' in open(conf, encoding='utf-8-sig', errors='replace').read()
    except OSError as e:
        kurulu = False
        if exe: _log(kok, 'Drive ayar dosyası okunamadı (%s): %r' % (conf, e))
    if exe and not kurulu and os.path.exists(conf): _log(kok, 'rclone.conf içinde [servisdrive] bölümü yok.')
    return (exe, conf) if exe and kurulu else None


def bulut_gonder(kok=KOK):
    """Yerel yedeklerden Drive'da olmayanları yükler (artımlı), 30 günden eskileri Drive'dan siler. True/False; kurulu değilse None."""
    r = _rclone(kok)
    if not r: return None
    exe, conf = r; yerel = os.path.join(kok, 'data', 'yedekler')
    bayrak = {'creationflags': 0x08000000} if os.name == 'nt' else {}   # pencere açma
    ortak = ['--config', conf, '--retries', '2', '--low-level-retries', '3', '--contimeout', '20s', '--timeout', '90s']
    try:
        p = subprocess.run([exe, 'copy', yerel, BULUT_UZAK, '--include', 'servis_*.db', '--max-age', '%dd' % SAKLAMA_GUN] + ortak,
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1500, **bayrak)
        if p.returncode != 0:
            _log(kok, 'Drive yüklemesi BAŞARISIZ (internet yok olabilir, sonraki turda denenecek): ' + (p.stderr or p.stdout or '').strip()[-300:]); return False
        d = subprocess.run([exe, 'delete', BULUT_UZAK, '--min-age', '%dd' % SAKLAMA_GUN] + ortak, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600, **bayrak)
        if d.returncode != 0: _log(kok, 'Drive\'da eski yedekler silinemedi (yükleme başarılı): ' + (d.stderr or '').strip()[-200:])
        open(os.path.join(kok, 'data', 'bulut_son.txt'), 'w').write(time.strftime('%Y-%m-%d %H:%M:%S'))
        return True
    except Exception as e:                                               # noqa: BLE001 - Drive sorunu yedeği bozmasın
        _log(kok, 'Drive yüklemesi hata verdi: %r' % e); return False


# ----------------------------------------------------------------- ana akış
def al(kok=KOK, harici=True):
    """Yedek alır, yeni yedeğin yolunu döner. Veritabanı yoksa None. harici=False: yalnızca yerel yedek (USB/Drive/dış klasör atlanır)."""
    db = os.path.join(kok, 'data', 'servis.db')
    if not os.path.exists(db): return None
    klasor = os.path.join(kok, 'data', 'yedekler'); os.makedirs(klasor, exist_ok=True)
    hedef = os.path.join(klasor, 'servis_%s.db' % time.strftime('%Y%m%d_%H%M%S'))
    kaynak = sqlite3.connect(db); kopya = sqlite3.connect(hedef)
    try: kaynak.backup(kopya)
    finally: kopya.close(); kaynak.close()
    kontrol = sqlite3.connect(hedef)
    try: sonuc = kontrol.execute('PRAGMA integrity_check').fetchone()[0]
    finally: kontrol.close()
    if sonuc != 'ok':
        os.remove(hedef); raise RuntimeError('Yedek bütünlük denetiminden geçmedi: %s' % sonuc)
    _eskileri_sil(klasor)
    if not harici: return hedef
    dis = os.environ.get('YEDEK_KLASORU', '').strip()
    if dis:
        try:
            os.makedirs(dis, exist_ok=True)
            shutil.copy2(hedef, os.path.join(dis, os.path.basename(hedef)))
            shutil.copy2(hedef, os.path.join(dis, 'servis_SON.db'))
            h = os.path.join(kok, 'data', '.password_hash')
            if os.path.exists(h): shutil.copy2(h, os.path.join(dis, 'password_hash.txt'))
            _eskileri_sil(dis)
        except OSError as e:
            print('UYARI: dış yedek klasörüne kopyalanamadı (%s). Yerel yedek alındı.' % e); _log(kok, 'Dış klasör hatası: %r' % e)
    try:
        usb = usb_bul()
        if usb: usb_kopyala(hedef, usb, kok); _log(kok, 'USB yedeği tamam: ' + usb)
    except Exception as e:                                               # noqa: BLE001 - USB sorunu yedeği bozmasın
        print('UYARI: USB yedeği alınamadı (%s).' % e); _log(kok, 'USB yedeği hata: %r' % e)
    b = bulut_gonder(kok)
    if b: _log(kok, 'Drive yedeği tamam')
    return hedef


def duzenli(kok=KOK):
    """15 dakikada bir çalışır: USB takıldıysa ve oradaki yedek eskiyse (YENILE_SAAT) ya da Drive'a gitmemiş/eski yedek varsa gereğini yapar."""
    usb = usb_bul(); bulut = _rclone(kok)
    usb_gerek = bool(usb) and _yas_saat(os.path.join(usb, 'ServisDefteriYedek', 'servis_SON.db')) >= YENILE_SAAT and _yas_saat(os.path.join(kok, 'data', 'usb_deneme.txt')) >= 0.5
    bulut_gerek = bool(bulut) and _yas_saat(os.path.join(kok, 'data', 'bulut_son.txt')) >= YENILE_SAAT
    yerel = sorted(glob.glob(os.path.join(kok, 'data', 'yedekler', 'servis_*.db')))
    yerel_gerek = not yerel or _yas_saat(yerel[-1]) >= LOKAL_SAAT      # gece 02:00 görevi kaçarsa (bilgisayar kapalı/uykuda) bu tur telafi eder
    if not (usb_gerek or bulut_gerek or yerel_gerek): return None
    if usb_gerek or yerel_gerek: return al(kok)
    bulut_gonder(kok); return 'bulut'


if __name__ == '__main__':
    utf8_cikti(); env_yukle()
    try:
        if '--duzenli' in sys.argv: duzenli(); sys.exit(0)
        y = al()
    except Exception as e:                  # noqa: BLE001
        _log(KOK, 'Yedek alınamadı: %r' % e); sys.exit('Yedek alınamadı: %s' % e)
    print('Yedek alındı: %s' % y if y else 'Veritabanı yok (uygulama henüz hiç çalışmamış).')
