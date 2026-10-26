# backup.sh kota_uygula(): toplam limiti aşınca en eski yedekler tek tek silinir (%90'a inene dek); yeni 30 gün ve başka dosyalar korunur.
import os, subprocess, sys, tempfile, time
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
betik = open(os.path.join(KOK, 'scripts', 'backup.sh'), encoding='utf-8').read()
fn = betik[betik.index('kota_uygula() {'):]; fn = fn[:fn.index('\n}\n') + 3]
ok = fail = 0
def k(ad, c):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print('BAŞARISIZ:', ad)
KB = 1024; GUN = 86400; simdi = time.time()
def klasor(gunler, boyut=KB):
    d = tempfile.mkdtemp()
    for g in gunler:
        p = os.path.join(d, 'servis_2%04d.db' % g); open(p, 'wb').truncate(boyut); os.utime(p, (simdi - g * GUN,) * 2)
    return d
def calistir(d, limit_gb):
    env = dict(os.environ, APP_DIR=tempfile.mkdtemp(), YEDEK_LIMIT_GB=limit_gb)
    return subprocess.run(['bash', '-c', fn + '\nkota_uygula "$1"', 'x', d], env=env, capture_output=True, text=True)
def kalan(d): return sorted(int(f[8:-3]) for f in os.listdir(d) if f.startswith('servis_2'))
d = klasor(range(1, 21)); r = calistir(d, '1')
k('limit altındaysa hiçbir şey silinmez', r.returncode == 0 and len(kalan(d)) == 20)
d = klasor(range(41, 81), boyut=40 * 1024 * 1024); r = calistir(d, '1')
k('limit aşılınca (toplam 1,6 GB > 1 GB) en eskiden silinir', len(kalan(d)) < 40 and 80 not in kalan(d))
tpl = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d))
k("silme %90'ın altında durur", tpl <= 0.9 * 1024 ** 3 and tpl > 0.8 * 1024 ** 3)
k('en yeni yedekler yerinde, silinenler hep en eskiler', kalan(d) == list(range(41, 41 + len(kalan(d)))))
d = klasor(range(1, 31), boyut=50 * 1024 * 1024); calistir(d, '1')
k('son 30 günün yedekleri limit aşılsa bile korunur', len(kalan(d)) == 30)
d = klasor(range(40, 60), boyut=60 * 1024 * 1024); open(os.path.join(d, 'not.txt'), 'w').write('a'); calistir(d, '1')
k('başka dosyalara dokunulmaz', os.path.exists(os.path.join(d, 'not.txt')))
d = klasor(range(40, 140), boyut=60 * 1024 * 1024); r = calistir(d, 'abc')
k('geçersiz limit varsayılan 4 GB olur (6 GB aşıldı → silme olur, hata yok)', r.returncode == 0 and len(kalan(d)) < 100 and sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d)) <= 3.6 * 1024 ** 3)
d = klasor(range(40, 140), boyut=60 * 1024 * 1024); r = calistir(d, 'inf')
k('inf limit varsayılan 4 GB olur, hata yok', r.returncode == 0 and sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d)) <= 3.6 * 1024 ** 3)
d = klasor([100, 200, 300, 400, 500], boyut=1024 * 1024); r = calistir(d, '0.0001')
k('limit çok küçük olsa da en yeni 3 yedek kalır', kalan(d) == [100, 200, 300])
print(f'{ok} geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
