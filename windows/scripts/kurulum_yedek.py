#!/usr/bin/env python3
"""Kurulum sirasinda YEDEK VARSA kullanmak icin (SERVIS-DEFTERI-KUR.bat cagirir; uygulama henuz calismiyor).
  bul    -> en yeni gecerli yedegi bulur, "ETIKET|ZAMAN|MUSTERI|ISEMRI" yazar (yoksa cikis kodu 3)
  yukle  -> o yedegi data\\servis.db olarak yerlestirir (mevcut veritabani varsa dokunmaz: cikis kodu 4)
Sifre dosyasina dokunmaz. Yalnizca data\\servis.db YOKSA (sifirdan/format sonrasi kurulum) calisir."""
import os, shutil, sqlite3, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortam import KOK, env_yukle, utf8_cikti
import yedek, geri_yukle


def _sayilar(yol):
    c = sqlite3.connect(yol)
    try:
        sor = lambda t: c.execute('select count(*) from %s' % t).fetchone()[0] if c.execute("select count(*) from sqlite_master where name=?", (t,)).fetchone()[0] else 0
        return sor('musteriler'), sor('is_emirleri')
    finally: c.close()


def _en_yeni(kok=KOK):
    """(etiket, zaman, yerel_yol, gecici_klasor|None) ya da None."""
    for t, k, y in geri_yukle.adaylar(kok):
        gecici = None
        if k == 'Google Drive':
            r = yedek._rclone(kok)
            if not r: continue
            gecici = tempfile.mkdtemp(prefix='servis-kur-')
            p = subprocess.run([r[0], 'copy', yedek.BULUT_UZAK + '/' + y, gecici, '--config', r[1]], capture_output=True, text=True, timeout=300)
            y = os.path.join(gecici, y)
            if p.returncode != 0 or not os.path.exists(y): shutil.rmtree(gecici, ignore_errors=True); continue
        if geri_yukle._gecerli(y): return k, geri_yukle._saat(t), y, gecici
        if gecici: shutil.rmtree(gecici, ignore_errors=True)
    return None


def main():
    utf8_cikti(); env_yukle()
    if len(sys.argv) < 2 or sys.argv[1] not in ('bul', 'yukle'): print(__doc__); return 1
    if os.path.exists(os.path.join(KOK, 'data', 'servis.db')): return 4        # mevcut kayitlara ASLA dokunulmaz
    e = _en_yeni()
    if not e: return 3
    k, zaman, yol, gecici = e
    try:
        if sys.argv[1] == 'bul':
            m, i = _sayilar(yol); print('%s|%s|%d|%d' % (k, zaman, m, i)); return 0
        geri_yukle.yukle(yol); print('Yedek yuklendi: %s (%s)' % (k, zaman)); return 0
    except RuntimeError as ex: print('HATA:', ex); return 1
    finally:
        if gecici: shutil.rmtree(gecici, ignore_errors=True)


if __name__ == '__main__': sys.exit(main())
