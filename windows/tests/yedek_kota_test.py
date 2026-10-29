# Yedek kotası: toplam limiti aşınca en eski yedekler tek tek silinir (%90'a inene dek); yeni 30 gün ve servis_SON.db korunur.
import os, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import yedek as Y
ok = fail = 0
def k(ad, c):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print('BAŞARISIZ:', ad)
MB = 1024 * 1024; GUN = 86400; simdi = time.time()
def klasor(gunler, boyut=MB, son=True):
    d = tempfile.mkdtemp()
    for g in gunler:
        p = os.path.join(d, 'servis_%d.db' % g); open(p, 'wb').write(b'x' * boyut); os.utime(p, (simdi - g * GUN,) * 2)
    if son: open(os.path.join(d, 'servis_SON.db'), 'wb').write(b'x' * boyut)
    return d
def kalan(d): return sorted(int(f[7:-3]) for f in os.listdir(d) if f[7:-3].isdigit())

d = klasor(range(1, 11)); s = Y._eskileri_sil(d, limit=20 * MB, simdi=simdi)
k('limit altındaysa hiçbir şey silinmez', s == [] and len(kalan(d)) == 10)
d = klasor(range(1, 401)); s = Y._eskileri_sil(d, limit=100 * MB, simdi=simdi)
k('limit aşılınca en eskiden başlayıp tek tek silinir', s[0] == 'servis_400.db' and kalan(d)[-1] < 400)
toplam = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d))
k("silme %90'ın altında durur (limite yapışmaz, sürekli silmez)", toplam <= 90 * MB and toplam > 85 * MB)
k('en yeni yedekler yerinde (silinenler hep en eskiler)', kalan(d) == list(range(1, 400 - len(s) + 1)))
k('servis_SON.db silinmez', os.path.exists(os.path.join(d, 'servis_SON.db')))
d = klasor(range(1, 31)); s = Y._eskileri_sil(d, limit=5 * MB, simdi=simdi)
k('son 30 günün yedekleri limit aşılsa bile korunur', s == [] and len(kalan(d)) == 30)
d = klasor(list(range(1, 31)) + [60, 90], son=False); Y._eskileri_sil(d, limit=31 * MB, simdi=simdi)
k('korumalı olmayanlar en eskiden gider, korumalılara dokunulmaz', kalan(d) == list(range(1, 31)))
k('klasörde başka dosyalara dokunulmaz', (lambda d: (open(os.path.join(d, 'not.txt'), 'w').write('a'), Y._eskileri_sil(d, limit=1, simdi=simdi), os.path.exists(os.path.join(d, 'not.txt')))[2])(klasor(range(40, 60))))
os.environ['YEDEK_LIMIT_GB'] = '2,5'; k('YEDEK_LIMIT_GB virgüllü değer', Y._limit_bayt() == int(2.5 * 1024 ** 3))
os.environ['YEDEK_LIMIT_GB'] = 'abc'; k('geçersiz değer varsayılan 4 GB', Y._limit_bayt() == 4 * 1024 ** 3)
os.environ.pop('YEDEK_LIMIT_GB'); k('değişken yoksa 4 GB', Y._limit_bayt() == 4 * 1024 ** 3)
os.environ['YEDEK_LIMIT_GB'] = 'inf'; k('inf varsayılan 4 GB (çökmez)', Y._limit_bayt() == 4 * 1024 ** 3)
os.environ['YEDEK_LIMIT_GB'] = '1e999'; k('1e999 varsayılan 4 GB', Y._limit_bayt() == 4 * 1024 ** 3); os.environ.pop('YEDEK_LIMIT_GB')
d = klasor([100, 200, 300, 400, 500], son=False); Y._eskileri_sil(d, limit=1, simdi=simdi)
k('kota ne olursa olsun en yeni 3 yedek kalır', kalan(d) == [100, 200, 300])
d = tempfile.mkdtemp(); src = os.path.join(d, 'a.db'); open(src, 'wb').write(b'abc'); Y._guvenli_kopya(src, os.path.join(d, 'b.db'))
k('güvenli kopya içeriği doğru, geçici dosya kalmaz', open(os.path.join(d, 'b.db'), 'rb').read() == b'abc' and not [f for f in os.listdir(d) if f.endswith('.tmp')])
try: Y._guvenli_kopya(os.path.join(d, 'yok.db'), os.path.join(d, 'c.db'))
except OSError: pass
k('kaynak yoksa hedef ve geçici dosya oluşmaz', not os.path.exists(os.path.join(d, 'c.db')) and not [f for f in os.listdir(d) if f.endswith('.tmp')])
import sqlite3
kok = tempfile.mkdtemp(); os.makedirs(os.path.join(kok, 'data')); c = sqlite3.connect(os.path.join(kok, 'data', 'servis.db')); c.execute('create table t(a)'); c.commit(); c.close()
h = Y.al(kok, harici=False); fl = os.listdir(os.path.join(kok, 'data', 'yedekler'))
k('al(): yedek oluşur, .tmp kalmaz', os.path.exists(h) and len(fl) == 1 and not fl[0].endswith('.tmp'))
print(f'{ok} geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
