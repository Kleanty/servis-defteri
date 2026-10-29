# Vitrin (ana sayfa): ziyaretçiye açık tanıtım, giriş yapmışı panele yollar, veri sızdırmaz, bağlantılar ve görseller çalışır.
import os, re, sys, shutil, tempfile
os.environ.pop('APP_PASSWORD_HASH', None); os.environ['FORCE_HTTPS_COOKIE'] = '0'
d = tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), d + '/a', ignore=shutil.ignore_patterns('data', '__pycache__'))
os.chdir(d + '/a'); sys.path.insert(0, d + '/a')
import app as A
ok = fail = 0
def k(ad, c):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print('BAŞARISIZ:', ad)
R = {'REMOTE_ADDR': '127.0.0.1'}
c = A.app.test_client()
r = c.get('/', environ_overrides=R); h = r.get_data(as_text=True)
k('ziyaretçi / adresinde vitrin görür (200)', r.status_code == 200 and 'Servis Defteri' in h)
k('giriş butonu /login adresine gider', 'href="/login"' in h)
k('yönetici girişi /yonetici/giris adresine gider', 'href="/yonetici/giris"' in h)
k('iletişim e-postası görünür', 'mailto:ahmet.taner.2002@hotmail.com' in h)
k('vitrin aramada çıkabilir (noindex yok)', 'noindex' not in r.headers.get('X-Robots-Tag', ''))
k('CSP var, dış kaynak yok', 'Content-Security-Policy' in r.headers and not re.search(r'(src|href)="https?://', h))
k('vitrinde giriş formu yok', '<form' not in h and 'type="password"' not in h)
for im in re.findall(r'src="(/static/vitrin/[^"]+)"', h):
    k('görsel açılır ' + im, c.get(im, environ_overrides=R).status_code == 200)
k('4 görsel var', len(re.findall(r'/static/vitrin/', h)) == 4)
k('/login hâlâ açılır', c.get('/login', environ_overrides=R).status_code == 200)
k('/yonetici/giris hâlâ açılır', c.get('/yonetici/giris', environ_overrides=R).status_code == 200)
k('/panel girişsiz vitrine değil girişe gider', c.get('/panel', environ_overrides=R).status_code == 302)
# giriş yapmış usta panele gider, vitrin görmez
YS = re.search(r'şifresi: (\S+)', open('data/ILK_SIFRE.txt', encoding='utf-8').read()).group(1)
def tok(cl, y): return re.search(r'name="csrf_token" value="([^"]+)"', cl.get(y, environ_overrides=R).get_data(as_text=True)).group(1)
y = A.app.test_client(); y.post('/yonetici/giris', data={'sifre': YS, 'csrf_token': tok(y, '/yonetici/giris')}, environ_overrides=R)
m = re.search(r'Geçici şifre: <b[^>]*>([^<]+)</b>', y.post('/yonetici/ekle', data={'ad': 'Vitrin Oto', 'kullanici': 'vitrin-oto', 'csrf_token': tok(y, '/yonetici')}, environ_overrides=R).get_data(as_text=True))
u = A.app.test_client(); u.post('/login', data={'kullanici': 'vitrin-oto', 'sifre': m.group(1), 'csrf_token': tok(u, '/login')}, environ_overrides=R)
r = u.get('/', environ_overrides=R)
k('giriş yapmış kullanıcı / adresinde panele yönlenir', r.status_code == 302 and ('/panel' in r.headers['Location'] or '/sifre' in r.headers['Location']))
k('vitrin dükkân verisi taşımaz', 'Vitrin Oto' not in c.get('/', environ_overrides=R).get_data(as_text=True))
# e-posta ayarı
A.VITRIN_EPOSTA = ''; h2 = A.app.test_client().get('/', environ_overrides=R).get_data(as_text=True)
k('e-posta kapalıyken iletişim bölümü yok', 'mailto:' not in h2 and 'id="iletisim"' not in h2)
print(f'{ok} başarılı, {fail} başarısız'); sys.exit(1 if fail else 0)
