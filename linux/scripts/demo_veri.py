#!/usr/bin/env python3
"""Denemek için SAHTE müşteri / araç / iş emri üretir (ekran görüntüleri bu veriyle alındı).
    python scripts/demo_veri.py            -> data/ içine yazar (boşsa)
Gerçek verinin üstüne yazmaz: veritabanında kayıt varsa durur. Silmek için data/ klasörünü sil.
Demo girişi için şifre ayrıca ayarlanmaz; ilk kurulum şifresi data/ILK_SIFRE.txt içindedir.
"""
import os, re, sys, random
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ.setdefault('FORCE_HTTPS_COOKIE', '0')
import app as A

MUSTERILER = [  # (ad soyad, telefon, plaka, marka, model, km)
    ('Ahmet Yıldız', '0555 010 20 30', '34 ABC 101', 'Fiat', 'Egea', 112400),
    ('Ayşe Demir', '0555 010 20 31', '06 DEM 202', 'Renault', 'Clio', 87250),
    ('Mehmet Kaya', '0555 010 20 32', '35 KYA 303', 'Volkswagen', 'Passat', 189900),
    ('Fatma Çelik', '0555 010 20 33', '16 CLK 404', 'Toyota', 'Corolla', 64300),
    ('Ali Şahin', '0555 010 20 34', '41 SHN 505', 'Ford', 'Focus', 143000),
    ('Zeynep Arslan', '0555 010 20 35', '07 ARS 606', 'Hyundai', 'i20', 52100),
    ('Mustafa Öztürk', '0555 010 20 36', '34 OZT 707', 'Opel', 'Astra', 171800),
    ('Elif Aydın', '0555 010 20 37', '35 AYD 808', 'Peugeot', '208', 38900),
]
ISLER = [('Yağ değişimi, Yağ filtresi',), ('Fren balatası, Fren diski',), ('Periyodik bakım',), ('Akü',),
         ('Klima bakımı, Klima gazı',), ('Lastik değişimi, Balans',), ('Triger seti, Devirdaim',), ('Arıza tespiti',),
         ('Amortisör, Rot / rotil',), ('Genel kontrol',)]

def main():
    c = A.app.test_client(); R = {'REMOTE_ADDR': '127.0.0.1'}
    db0 = A.sqlite3.connect(A.DB_PATH)
    if db0.execute('SELECT COUNT(*) FROM musteriler').fetchone()[0]:
        sys.exit('Veritabanında kayıt var; demo verisi eklenmedi (gerçek verin korunuyor).')
    sifre = os.environ.get('DEMO_SIFRE', '')
    if not sifre:
        ilk = os.path.join(A.BASE_DIR, 'data', 'ILK_SIFRE.txt')
        sifre = re.search(r'şifresi: (\S+)', open(ilk, encoding='utf-8').read()).group(1) if os.path.exists(ilk) else sys.exit('DEMO_SIFRE verin ya da ILK_SIFRE.txt olmalı.')
    tok = lambda y: re.search(r'name="csrf_token" value="([^"]+)"', c.get(y, environ_overrides=R).get_data(as_text=True)).group(1)
    c.post('/login', data={'csrf_token': tok('/login'), 'sifre': sifre}, environ_overrides=R)
    P = lambda u, **v: c.post(u, data=dict(v, csrf_token=tok('/panel')), environ_overrides=R)
    rnd = random.Random(7); simdi = datetime.now()
    for i, (ad, tel, plaka, marka, model, km) in enumerate(MUSTERILER):
        P('/is-emirleri/hizli', plaka=plaka, musteri_ad=ad, telefon=tel, marka=marka, model=model, giris_km=str(km - 9000), gelis_nedeni=ISLER[i][0])
    db = A.sqlite3.connect(A.DB_PATH); db.row_factory = A.sqlite3.Row
    ids = [r['id'] for r in db.execute('SELECT id FROM is_emirleri ORDER BY id')]
    # geçmiş geliş tarihleri + tamamlanmış kayıtlar
    for n, iid in enumerate(ids):
        gun = 14 + n * 9; t = (simdi - timedelta(days=gun)).replace(hour=10, minute=15, second=0)
        db.execute('UPDATE is_emirleri SET gelis_at=?,tarih=? WHERE id=?', (t.strftime('%Y-%m-%d %H:%M:%S'), t.strftime('%Y-%m-%d'), iid)); db.commit()
        P(f'/is-emirleri/durum/{iid}', durum='Tamamlandı')
        db.execute('UPDATE is_emirleri SET gidis_at=? WHERE id=?', ((t + timedelta(hours=5)).strftime('%Y-%m-%d %H:%M:%S'), iid)); db.commit()
    # ikinci geliş: bazıları açık
    P('/is-emirleri/hizli', plaka='34 ABC 101', gelis_nedeni='Fren balatası', giris_km='117800')
    P('/is-emirleri/hizli', plaka='06 DEM 202', gelis_nedeni='Klima bakımı, Klima gazı', giris_km='91000')
    P('/is-emirleri/hizli', plaka='35 KYA 303', gelis_nedeni='Triger seti, Devirdaim', giris_km='194500')
    P('/is-emirleri/hizli', plaka='16 CLK 404', gelis_nedeni='Periyodik bakım', giris_km='69000')
    son = db.execute('SELECT id FROM is_emirleri ORDER BY id DESC LIMIT 4').fetchall()
    P(f'/is-emirleri/durum/{son[2]["id"]}', durum='Devam Ediyor'); P(f'/is-emirleri/durum/{son[0]["id"]}', durum='Devam Ediyor')
    # bugün bir iş teslim
    P(f'/is-emirleri/durum/{son[3]["id"]}', durum='Tamamlandı')
    print('Demo verisi eklendi: 8 müşteri, 8 araç,', db.execute('SELECT COUNT(*) FROM is_emirleri').fetchone()[0], 'iş emri.')

if __name__ == '__main__':
    main()
