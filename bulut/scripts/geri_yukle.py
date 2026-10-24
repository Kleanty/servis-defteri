#!/usr/bin/env python3
"""Bir dükkânın veritabanını yedekten geri yükler (yalnızca yönetici). ÖNCE servisi durdur:
    sudo systemctl stop servis-defteri
    venv/bin/python scripts/geri_yukle.py <kullanici-adi> <yedek.db>
    sudo systemctl start servis-defteri
Yedek önce bütünlük denetiminden geçer; mevcut veritabanı silinmez, yedekler/ içine geri_yukleme_oncesi_*.db olarak saklanır.
Liste için:  venv/bin/python scripts/geri_yukle.py <kullanici-adi>   (o dükkânın yedeklerini gösterir)
"""
import os, sys, sqlite3, shutil
from datetime import datetime

os.umask(0o077)      # yedekler yalnızca bu kullanıcıya açık
ANA = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); VERI = os.path.join(ANA, 'data')


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    kullanici = sys.argv[1].strip().lower()
    c = sqlite3.connect(os.path.join(VERI, 'yonetim.db')); r = c.execute('SELECT id,ad FROM dukkanlar WHERE kullanici=?', (kullanici,)).fetchone(); c.close()
    if not r: sys.exit(f'"{kullanici}" adlı dükkân yok.')
    i, ad = r; klasor = os.path.join(VERI, 'dukkanlar', str(i)); yedekler = os.path.join(klasor, 'yedekler'); hedef = os.path.join(klasor, 'servis.db')
    if len(sys.argv) < 3:
        print(f'{ad} ({kullanici}) yedekleri:')
        for f in sorted(os.listdir(yedekler)) if os.path.isdir(yedekler) else []:
            print('  ', os.path.join(yedekler, f), f'({os.path.getsize(os.path.join(yedekler, f)) // 1024} KB)')
        return
    kaynak = sys.argv[2]
    if not os.path.isfile(kaynak): sys.exit('Yedek dosyası bulunamadı: ' + kaynak)
    try:
        k = sqlite3.connect(f'file:{kaynak}?mode=ro', uri=True)
        if k.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': sys.exit('Yedek bozuk (bütünlük denetimi başarısız); geri yüklenmedi.')
        tablolar = {x[0] for x in k.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'musteriler', 'araclar', 'is_emirleri'} <= tablolar: sys.exit('Bu dosya bir Servis Defteri yedeği değil; geri yüklenmedi.')
        say = k.execute('SELECT COUNT(*) FROM musteriler').fetchone()[0]
    except sqlite3.Error as e: sys.exit(f'Yedek okunamadı: {e}')
    print(f'Dükkân: {ad} ({kullanici}) | yedekte {say} müşteri var.')
    if '--evet' not in sys.argv and input('Mevcut veri bu yedekle DEĞİŞTİRİLECEK. Servis durduruldu mu ve devam edilsin mi? (evet/hayır): ').strip().lower() != 'evet': sys.exit('İptal edildi.')
    os.makedirs(yedekler, exist_ok=True)
    if os.path.exists(hedef):
        onceki = os.path.join(yedekler, 'geri_yukleme_oncesi_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.db')
        a = sqlite3.connect(hedef); b = sqlite3.connect(onceki)
        with b: a.backup(b)
        a.close(); b.close(); print('Eski veri saklandı:', onceki)
    gecici = hedef + '.geri'; k2 = sqlite3.connect(f'file:{kaynak}?mode=ro', uri=True); h = sqlite3.connect(gecici)
    with h: k2.backup(h)
    k2.close(); h.close()
    for ek in ('-wal', '-shm'):
        try: os.unlink(hedef + ek)
        except OSError: pass
    os.replace(gecici, hedef); print('Geri yüklendi. Servisi başlat: sudo systemctl start servis-defteri')


if __name__ == '__main__':
    main()
