# Genel sürüm testleri: ilk kurulum şifresi, işletme bilgilerinin .env'den gelmesi, koda gömülü kişisel veri olmaması.
# Kullanım: python3 tests/genel_test.py
import os, re, sys, shutil, tempfile
os.environ.pop('APP_PASSWORD_HASH', None); os.environ.pop('PUBLIC_BASE_URL', None)
os.environ.update(ISLETME_ADI='Deneme Oto Servis', ISLETME_TEL='0555 123 45 67', ISLETME_ADRES='Test Mah. 1. Cad. No:5',
                  HARITA_LINK='https://maps.example.com/x', ETIKET_BASLIK='Deneme Oto', FORCE_HTTPS_COOKIE='0')
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = tempfile.mkdtemp(); shutil.copytree(KOK, d + '/a', ignore=shutil.ignore_patterns('data', '__pycache__', '.env', 'venv', '.git')); os.chdir(d + '/a'); sys.path.insert(0, '.')
import app as A, etiket_yazici as EY
ok = fail = 0
def k(ad, c):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print('BAŞARISIZ:', ad)
R = {'REMOTE_ADDR': '127.0.0.1'}
# --- ilk kurulum: şifre dosyası + rastgele şifre ---
ilk = open('data/ILK_SIFRE.txt', encoding='utf-8').read(); m = re.search(r'şifresi: (\S+)', ilk)
k('ilk şifre dosyası üretildi', bool(m) and len(m.group(1)) >= 14)
k('şifre dosyası yalnızca sahibine açık (0600)', oct(os.stat('data/ILK_SIFRE.txt').st_mode & 0o777) == '0o600' and oct(os.stat('data/.password_hash').st_mode & 0o777) == '0o600')
k('hash dosyasında düz şifre yok', m.group(1) not in open('data/.password_hash').read())
c = A.app.test_client()
tok = lambda y='/login': re.search(r'name="csrf_token" value="([^"]+)"', c.get(y, environ_overrides=R).get_data(as_text=True)).group(1)
r = c.post('/login', data={'csrf_token': tok(), 'sifre': 'MestanOto-2026!'}, environ_overrides=R); k('eski gömülü şifre ARTIK çalışmaz', r.status_code != 302 or '/panel' not in r.headers.get('Location', ''))
r = c.post('/login', data={'csrf_token': tok(), 'sifre': 'yanlis-sifre-123'}, environ_overrides=R); k('yanlış şifre girmez', '/panel' not in r.headers.get('Location', ''))
r = c.post('/login', data={'csrf_token': tok(), 'sifre': m.group(1)}, environ_overrides=R); k('ilk şifre ile giriş olur', r.status_code == 302 and c.get('/panel', environ_overrides=R).status_code == 200)
# --- ikinci açılışta aynı şifre kalıcı (yeniden üretilmez) ---
h1 = open('data/.password_hash').read(); h2 = A._hash_yukle(); k('yeniden başlatınca hash değişmez', h1 == h2)
# --- işletme bilgileri vitrin ve sayfalarda ---
v = A.app.test_client().get('/', environ_overrides=R).get_data(as_text=True)
k('vitrin: işletme adı .env\'den', 'Deneme Oto Servis' in v and 'Servis Defteri' not in v)
k('vitrin: telefon, WhatsApp ve adres', 'tel:+905551234567' in v and 'wa.me/905551234567' in v and 'Test Mah. 1. Cad. No:5' in v)
k('vitrin: yol tarifi bağlantısı', 'https://maps.example.com/x' in v)
k('vitrin: harita iframe yok (HARITA_EMBED_URL boş)', '<iframe' not in v)
k('vitrin: JSON-LD adı', '"name": "Deneme Oto Servis"' in v)
l = A.app.test_client().get('/login', environ_overrides=R).get_data(as_text=True); k('giriş sayfası marka adı', 'Deneme' in l)
# --- etiket başlığı ---
kom = '\n'.join(EY.tspl_komutlari('35ABC123', 'https://servis.example.com/arac/abc'))
k('etiket: iki satırlı başlık (DENEME / OTO)', '"DENEME"' in kom and '"OTO"' in kom and 'MESTAN' not in kom)
# --- kaynak kodda kişisel veri kalmadı ---
yasak = ['mestan', 'mestanoto', '0538', '538 577', 'kleanty', 'bornova', 'pınarbaşı', 'MestanOto-2026', 'fd16bf29f87534405155dbb96eb29f69']
bulunan = []
for kok, dizinler, dosyalar in os.walk('.'):
    dizinler[:] = [x for x in dizinler if x not in ('data', '__pycache__', '.git', 'venv')]
    for f in dosyalar:
        if f.endswith(('.png', '.ico', '.pyc')) or f == 'genel_test.py': continue
        try: icerik = open(os.path.join(kok, f), encoding='utf-8').read().lower()
        except Exception: continue
        for y in yasak:
            if y.lower() in icerik: bulunan.append((os.path.join(kok, f), y))
k('kaynakta kişisel veri / marka / gömülü şifre yok: %s' % bulunan[:5], not bulunan)
print(f'{ok} kontrol geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
