# Denetim sonrası düzeltmeler: bozuk dükkân veritabanı, onay penceresi (kesme işareti), log sahteciliği, dosya izinleri
import os, re, sys, shutil, tempfile, subprocess, stat
os.environ.pop('APP_PASSWORD_HASH', None); os.environ['FORCE_HTTPS_COOKIE'] = '0'
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = tempfile.mkdtemp(); shutil.copytree(KOK, d + '/a', ignore=shutil.ignore_patterns('data', '__pycache__')); os.chdir(d + '/a'); sys.path.insert(0, '.')
import app as A; A.app.config['CIHAZ_KAPISI'] = False      # bu test cihaz adı kapısını sınamaz; kapı hareket_test.py'de sınanır
ok = fail = 0
def k(ad, c):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print('BAŞARISIZ:', ad)
R = {'REMOTE_ADDR': '127.0.0.1'}
def tok(c, y='/login'): return re.search(r'name="csrf_token" value="([^"]+)"', c.get(y, environ_overrides=R).get_data(as_text=True)).group(1)
def giris(kul, sif):
    c = A.app.test_client(); c.post('/login', data={'csrf_token': tok(c), 'kullanici': kul, 'sifre': sif}, environ_overrides=R); return c
YSIFRE = re.search(r'şifresi: (\S+)', open('data/ILK_SIFRE.txt', encoding='utf-8').read()).group(1)

# --- B-05: dükkân adında kesme işareti ---
i1, _ = A.dukkan_olustur('ahmet-oto', "Ahmet'in Oto", sifre='Sifre-12345!', gecici=False)
i2, _ = A.dukkan_olustur('veli-servis', 'Veli Servis', sifre='Sifre-12345!', gecici=False)
y = A.app.test_client(); y.post('/yonetici/giris', data={'csrf_token': tok(y, '/yonetici/giris'), 'sifre': YSIFRE}, environ_overrides=R)
h = y.get('/yonetici', environ_overrides=R).get_data(as_text=True)
k('yönetici sayfasında satır içi confirm(\'…\') yok', "confirm('" not in h and h.count('data-soru="') >= 4)
k('kesme işaretli ad nitelik içinde kaçırılmış', "Ahmet&#39;in Oto için yeni geçici şifre" in h and "Ahmet'in Oto için" not in h)
A.dukkan_olustur('xss-deneme', '"><script>alert(1)</script>', sifre='Sifre-12345!', gecici=False)
h2 = y.get('/yonetici', environ_overrides=R).get_data(as_text=True); k('betik içeren ad çalıştırılamaz (kaçırılır)', '<script>alert(1)</script>' not in h2)

# --- B-09: log sahteciliği ve yanlışlıkla yazılan şifre ---
c = A.app.test_client()
c.post('/login', data={'csrf_token': tok(c), 'kullanici': 'x\n2026-10-20 12:00:00 INFO in app: Giriş başarılı | dukkan=ahmet-oto | ip=1.2.3.4', 'sifre': 'a'}, environ_overrides=R)
c.post('/login', data={'csrf_token': tok(c), 'kullanici': 'BenimGizliSifrem-987', 'sifre': 'a'}, environ_overrides=R)
c.post('/login', data={'csrf_token': tok(c), 'kullanici': 'veli-servis', 'sifre': 'yanlis'}, environ_overrides=R)
log = open('data/uygulama.log', encoding='utf-8').read()
k('log: sahte satır oluşmadı', 'ip=1.2.3.4' not in log and not re.search(r'^2026-10-20 12:00:00', log, re.M))
k('log: kullanıcı adı kutusuna yazılan metin kaydedilmedi', 'BenimGizliSifrem' not in log)
k('log: bilinen kullanıcının başarısız girişi görünür', 'Giriş başarısız (kullanıcı veli-servis)' in log and 'Giriş başarısız (kullanıcı bilinmiyor)' in log)

# --- B-06: izinler ---
def mod(p): return stat.S_IMODE(os.stat(p).st_mode)
dosyalar = ['data/yonetim.db', A.db_yolu(i2), 'data/uygulama.log']
k('data klasörü 0700', mod('data') == 0o700 and mod('data/dukkanlar') == 0o700)
k('veritabanı dosyaları 0600', all(mod(p) == 0o600 for p in dosyalar))
subprocess.run([sys.executable, 'scripts/backup.py'], capture_output=True)
yd = A.yedek_dizin(i2); yb = [os.path.join(yd, x) for x in os.listdir(yd)]
k('yedek dosyaları 0600, klasörleri 0700', yb and all(mod(p) == 0o600 for p in yb) and mod(yd) == 0o700 and all(mod('data/yonetim_yedek/' + x) == 0o600 for x in os.listdir('data/yonetim_yedek')))
# eski kurulumdan kalan geniş izinler açılışta kapanır
os.chmod('data', 0o755); os.chmod('data/yonetim.db', 0o644); A.izinleri_sikilastir()
k('geniş izinler açılışta sıkılaştırılır', mod('data') == 0o700 and mod('data/yonetim.db') == 0o600)

# --- B-01: bozuk dükkân veritabanı servisi durdurmaz ---
A.dukkan_sifre_yaz(i1, 'Sifre-12345!', False)
cp = tempfile.mkdtemp(); shutil.copytree(d + '/a', cp + '/b', ignore=shutil.ignore_patterns('__pycache__')); os.chdir(cp + '/b')
open(A.db_yolu(i1).replace(d + '/a', cp + '/b'), 'wb').write(b'SQLite format 3\x00' + bytes(range(256)) * 20)
for ek in ('-wal', '-shm'):
    try: os.unlink(A.db_yolu(i1).replace(d + '/a', cp + '/b') + ek)
    except OSError: pass
kod = r'''
import os,re,sys; os.environ['FORCE_HTTPS_COOKIE']='0'; sys.path.insert(0,'.')
import app as A; A.app.config['CIHAZ_KAPISI']=False
R={'REMOTE_ADDR':'127.0.0.1'}
def giris(kul):
    c=A.app.test_client(); t=re.search(r'name="csrf_token" value="([^"]+)"',c.get('/login',environ_overrides=R).get_data(as_text=True)).group(1)
    c.post('/login',data={'csrf_token':t,'kullanici':kul,'sifre':'Sifre-12345!'},environ_overrides=R); return c
print('IMPORT_OK', sorted(A.BOZUK_DUKKAN))
print('SAGLAM', giris('veli-servis').get('/panel',environ_overrides=R).status_code)
print('BOZUK', giris('ahmet-oto').get('/panel',environ_overrides=R).status_code)
print('SAGLIK', A.app.test_client().get('/saglik',environ_overrides=R).status_code)
'''
r = subprocess.run([sys.executable, '-I', '-c', kod], capture_output=True, text=True, cwd=cp + '/b', env=dict(os.environ, PYTHONPATH='.'))
o = r.stdout
k('bozuk dükkân varken uygulama başlar: ' + (r.stderr[-150:] if 'IMPORT_OK' not in o else ''), 'IMPORT_OK' in o and f'[{i1}]' in o)
k('sağlam dükkân çalışmaya devam eder', 'SAGLAM 200' in o)
k('bozuk dükkân 503 alır, diğerleri etkilenmez, /saglik uyarır', 'BOZUK 503' in o and 'SAGLIK 503' in o)      # /saglik bozuk dükkânı da bildirir (uptime uyarısı)
print(f'\n{ok} kontrol geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
