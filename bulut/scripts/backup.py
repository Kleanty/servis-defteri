#!/usr/bin/env python3
"""Tüm dükkânların veritabanını yedekler (günlük çalıştır). Elle:  venv/bin/python scripts/backup.py
Her dükkân için data/dukkanlar/<id>/yedekler/servis_YYYYMMDD_HHMMSS.db, ayrıca hesap listesi için data/yonetim_yedek/.
SQLite yedekleme API'si kullanılır (çalışan veritabanında güvenli); bütünlük denetiminden geçmeyen yedek silinir.
30 günden eski yedekler silinir (her dükkânda en az son 3 yedek kalır).
İsteğe bağlı: RCLONE_REMOTE (ortam değişkeni ya da .env) tanımlıysa son yedekler buluta kopyalanır:  RCLONE_REMOTE=gdrive:ServisDefteri-Yedek
Uygulama kodunu İÇE AKTARMAZ (yönetici şifresi üretimi gibi yan etkiler olmasın).
"""
import os, sys, sqlite3, shutil, subprocess, time
from datetime import datetime

os.umask(0o077)      # yedekler yalnızca bu kullanıcıya açık
ANA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERI = os.path.join(ANA, 'data')
SAKLA_GUN = 30; EN_AZ = 3


def env_oku(ad):
    v = os.environ.get(ad, '').strip()
    if v: return v
    try:
        for s in open(os.path.join(ANA, '.env'), encoding='utf-8-sig').read().splitlines():
            if s.strip().startswith(ad + '='): return s.split('=', 1)[1].strip().strip('"\'')
    except OSError: pass
    return ''


def yedekle(kaynak, hedef):
    """kaynak -> hedef (SQLite yedekleme API'si) ve bütünlük denetimi. Başarısızsa hedefi siler, False döner."""
    gecici = hedef + '.tmp'
    try:
        k = sqlite3.connect(f'file:{kaynak}?mode=ro', uri=True, timeout=30); h = sqlite3.connect(gecici)
        try:
            with h: k.backup(h)
            ok = h.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        finally: k.close(); h.close()
        if not ok: raise sqlite3.DatabaseError('bütünlük denetimi başarısız')
        os.replace(gecici, hedef); return True
    except (sqlite3.Error, OSError) as e:
        print(f'  HATA ({os.path.basename(kaynak)}): {e}')
        try: os.unlink(gecici)
        except OSError: pass
        return False


def temizle(klasor, onek):
    dosyalar = sorted(f for f in os.listdir(klasor) if f.startswith(onek) and f.endswith('.db'))
    sinir = time.time() - SAKLA_GUN * 86400
    for f in dosyalar[:-EN_AZ]:
        y = os.path.join(klasor, f)
        if os.path.getmtime(y) < sinir: os.unlink(y)


def rclone(uzak, yerel, ad):
    if not uzak or not shutil.which('rclone'): return
    r = subprocess.run(['rclone', 'copyto', yerel, f'{uzak}/{ad}', '--retries', '3'], capture_output=True, text=True)
    print('  bulut:', 'tamam' if r.returncode == 0 else 'UYARI: yüklenemedi (internet/oturum?) — yerel yedek mevcut')


def main():
    yonetim = os.path.join(VERI, 'yonetim.db')
    if not os.path.exists(yonetim): sys.exit('data/yonetim.db yok (uygulama henüz hiç çalışmamış).')
    t = datetime.now().strftime('%Y%m%d_%H%M%S'); uzak = env_oku('RCLONE_REMOTE'); hata = 0
    c = sqlite3.connect(f'file:{yonetim}?mode=ro', uri=True); dukkanlar = c.execute('SELECT id,kullanici FROM dukkanlar ORDER BY id').fetchall(); c.close()
    for i, kullanici in dukkanlar:
        kaynak = os.path.join(VERI, 'dukkanlar', str(i), 'servis.db'); klasor = os.path.join(VERI, 'dukkanlar', str(i), 'yedekler')
        if not os.path.exists(kaynak): print(f'{kullanici}: veritabanı yok, atlandı'); continue
        os.makedirs(klasor, exist_ok=True); hedef = os.path.join(klasor, f'servis_{t}.db')
        if yedekle(kaynak, hedef):
            print(f'{kullanici}: yedek alındı'); temizle(klasor, 'servis_'); rclone(uzak, hedef, f'{kullanici}/servis_{t}.db')
        else: hata += 1
    # hesap listesi (kullanıcı adları, şifre özetleri) da yedeklenir
    klasor = os.path.join(VERI, 'yonetim_yedek'); os.makedirs(klasor, exist_ok=True); hedef = os.path.join(klasor, f'yonetim_{t}.db')
    if yedekle(yonetim, hedef): print('yonetim: yedek alındı'); temizle(klasor, 'yonetim_'); rclone(uzak, hedef, f'yonetim/yonetim_{t}.db')
    else: hata += 1
    sys.exit(1 if hata else 0)


if __name__ == '__main__':
    main()
