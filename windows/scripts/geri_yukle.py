#!/usr/bin/env python3
"""Yedekten geri yükleme (uygulama DURMUŞ olmalı; YEDEKTEN-GERI-YUKLE.bat bunu halleder).
Kaynaklar: bu bilgisayardaki yedekler, USB bellek (SERVISYEDEK), Google Drive. Mevcut veritabanı silinmez: servis_ONCEKI_<tarih>.db olarak yanına saklanır.
Şifre dosyasına dokunmaz."""
import glob, os, shutil, sqlite3, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortam import KOK, env_yukle, utf8_cikti
import yedek


def _saat(t): return time.strftime('%d.%m.%Y %H:%M', time.localtime(t))


def _gecerli(yol):
    try:
        c = sqlite3.connect(yol)
        try: return c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok' and c.execute("select count(*) from sqlite_master where name='is_emirleri'").fetchone()[0] == 1
        finally: c.close()
    except sqlite3.Error: return False


def adaylar(kok=KOK):
    """[(etiket, yol_veya_drive_adı, kaynak)] yeniden eskiye."""
    liste = []
    for f in glob.glob(os.path.join(kok, 'data', 'yedekler', 'servis_2*.db')): liste.append((os.path.getmtime(f), 'Bu bilgisayar', f))
    usb = yedek.usb_bul()
    if usb:
        for f in glob.glob(os.path.join(usb, 'ServisDefteriYedek', 'servis_2*.db')): liste.append((os.path.getmtime(f), 'USB bellek', f))
    r = yedek._rclone(kok)
    if r:
        try:
            p = subprocess.run([r[0], 'lsf', yedek.BULUT_UZAK, '--config', r[1], '--files-only'], capture_output=True, text=True, timeout=120)
            for ad in p.stdout.split():
                if ad.startswith('servis_2') and ad.endswith('.db'):
                    liste.append((time.mktime(time.strptime(ad[7:22], '%Y%m%d_%H%M%S')), 'Google Drive', ad))
        except (OSError, subprocess.SubprocessError, ValueError): print('(Google Drive listesi alınamadı)')
    return sorted(liste, key=lambda x: x[0], reverse=True)


def yukle(kaynak, kok=KOK):
    """kaynak: yerel yol. Geçerliyse veritabanının yerine koyar, eskiyi saklar, eskinin yolunu döner.
    Sıra: geçici kopya -> doğrulama -> eskiyi yan yana sakla -> os.replace ile devreye al; hata olursa eskisi geri konur."""
    if not _gecerli(kaynak): raise RuntimeError('Seçilen yedek geçerli bir Servis Defteri veritabanı değil.')
    db = os.path.join(kok, 'data', 'servis.db'); os.makedirs(os.path.dirname(db), exist_ok=True)
    gecici = db + '.geri_yukle.tmp'
    try:
        shutil.copy2(kaynak, gecici)
        if not _gecerli(gecici): raise RuntimeError('Kopyalanan dosya doğrulanamadı (disk dolu olabilir).')
    except (OSError, RuntimeError) as e:
        try: os.remove(gecici)
        except OSError: pass
        raise RuntimeError('Yedek hazırlanamadı, mevcut kayıtlara dokunulmadı: %s' % e)
    eski = None
    try:
        if os.path.exists(db):
            eski = os.path.join(kok, 'data', 'servis_ONCEKI_%s.db' % time.strftime('%Y%m%d_%H%M%S'))
            os.replace(db, eski)
        for ek in ('-wal', '-shm'):
            try: os.remove(db + ek)
            except OSError: pass
        os.replace(gecici, db)
    except OSError as e:
        if eski and not os.path.exists(db):
            try: os.replace(eski, db)
            except OSError: pass
        try: os.remove(gecici)
        except OSError: pass
        raise RuntimeError('Geri yükleme başarısız, önceki kayıtlar yerinde bırakıldı: %s' % e)
    return eski


def main():
    utf8_cikti(); env_yukle()
    a = adaylar()
    if not a: print('Hiç yedek bulunamadı.'); return 1
    print('Geri yüklenebilecek yedekler (en yeni üstte):\n')
    for i, (t, k, y) in enumerate(a[:25], 1): print('  %2d)  %s   [%s]' % (i, _saat(t), k))
    s = input('\nKaçıncı yedek? (iptal için boş bırak): ').strip()
    if not s.isdigit() or not 1 <= int(s) <= min(25, len(a)): print('İptal edildi, hiçbir şey değişmedi.'); return 2
    t, k, y = a[int(s) - 1]
    print('\nSeçilen: %s [%s]\nBu işlem MEVCUT kayıtların yerine bu yedeği koyar (mevcut kayıtlar saklanır).' % (_saat(t), k))
    if input('Onaylamak için EVET yaz: ').strip().upper() != 'EVET': print('İptal edildi, hiçbir şey değişmedi.'); return 2
    gecici = None
    try:
        if k == 'Google Drive':
            exe, conf = yedek._rclone(KOK); gecici = tempfile.mkdtemp(prefix='servis-geri-')
            p = subprocess.run([exe, 'copy', yedek.BULUT_UZAK + '/' + y, gecici, '--config', conf], capture_output=True, text=True, timeout=600)
            y = os.path.join(gecici, y)
            if p.returncode != 0 or not os.path.exists(y): print('Drive\'dan indirilemedi:', (p.stderr or '')[-300:]); return 1
        eski = yukle(y)
    except RuntimeError as e: print('HATA:', e); return 1
    finally:
        if gecici: shutil.rmtree(gecici, ignore_errors=True)
    print('\nTamam: yedek geri yüklendi.' + ('\nÖnceki kayıtlar şurada saklandı: ' + eski if eski else ''))
    return 0


if __name__ == '__main__': sys.exit(main())
