# Dış sistem entegrasyon API'si (çok dükkânlı): dükkâna özel anahtar, izolasyon, yönetici yönetimi, eşleştirme, tekrar koruması, eşleşmeyenler.
import os, re, sys, shutil, tempfile, sqlite3, hashlib
os.environ.pop('APP_PASSWORD_HASH', None); os.environ['FORCE_HTTPS_COOKIE'] = '0'
d = tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), d + '/a', ignore=shutil.ignore_patterns('data', '__pycache__')); os.chdir(d + '/a'); sys.path.insert(0, '.')
import app as A
ok = fail = 0
def k(ad, c):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print('BAŞARISIZ:', ad)
R = {'REMOTE_ADDR': '127.0.0.1'}
YSIFRE = re.search(r'şifresi: (\S+)', open('data/ILK_SIFRE.txt', encoding='utf-8').read()).group(1)
def tok(c, y='/login'): return re.search(r'name="csrf_token" value="([^"]+)"', c.get(y, environ_overrides=R).get_data(as_text=True)).group(1)
def post(c, url, y='/login', **v): v['csrf_token'] = tok(c, y); return c.post(url, data=v, environ_overrides=R)
def get(c, url): return c.get(url, environ_overrides=R)
ia, _ = A.dukkan_olustur('ahmet-oto', 'Ahmet Oto', '0555 111 22 33', sifre='Ahmet-Sifre-1', gecici=False)
ib, _ = A.dukkan_olustur('veli-servis', 'Veli Servis', '0555 222 33 44', sifre='Veli-Sifre-12', gecici=False)
def dukkan_giris(kul, sif):
    c = A.app.test_client(); post(c, '/login', kullanici=kul, sifre=sif); return c
a = dukkan_giris('ahmet-oto', 'Ahmet-Sifre-1'); b = dukkan_giris('veli-servis', 'Veli-Sifre-12')
def hizli(c, plaka, km):
    return post(c, '/is-emirleri/hizli', '/panel', plaka=plaka, giris_km=str(km), gelis_nedeni='Bakım')
def dbx(i): return sqlite3.connect(A.db_yolu(i))
api = A.app.test_client()
def G(js, anahtar, proto='https'):
    h = {'X-Forwarded-Proto': proto}
    if anahtar: h['X-API-Key'] = anahtar
    return api.post('/api/v1/is-emirleri', json=js, headers=h, environ_overrides=R)

# --- anahtar yokken API kapalı ---
k('hiçbir dükkânın anahtarı yokken API kapalı (404)', G({'plaka': '35ABC123'}, 'sk_xxxx_' + 'a' * 30).status_code == 404 and api.get('/api/v1/saglik', environ_overrides=R).status_code == 404)

# --- yönetici anahtar üretir ---
y = A.app.test_client(); post(y, '/yonetici/giris', '/yonetici/giris', sifre=YSIFRE)
k('dükkân satırında "API anahtarı üret" düğmesi', 'API anahtarı üret' in get(y, '/yonetici').get_data(as_text=True))
anon = A.app.test_client()
k('yönetici olmayan anahtar üretemez', anon.post(f'/yonetici/{ia}/api', data={'eylem': 'uret'}, environ_overrides=R).status_code in (302, 400))
k('dükkân girişi yönetici işi yapamaz', post(a, f'/yonetici/{ia}/api', '/panel', eylem='uret').status_code in (302, 400, 401, 403))
k('anahtar üretilmediyse hâlâ kapalı', G({'plaka': '35ABC123'}, 'sk_xxxx_' + 'a' * 30).status_code == 404)
r = post(y, f'/yonetici/{ia}/api', '/yonetici', eylem='uret'); h = r.get_data(as_text=True)
m = re.search(r'API anahtarı: <b[^>]*>([^<]+)</b>', h); KA = m.group(1) if m else ''
k('anahtar üretildi, bir kez gösterildi', r.status_code == 200 and re.fullmatch(r'sk_[a-z0-9]{4}_[A-Za-z0-9_-]{30,}', KA) is not None and 'no-store' in r.headers.get('Cache-Control', ''))
Ad = A.dukkan_getir(ia)
k('anahtar dükkânın kodunu taşır', KA.startswith('sk_' + Ad['kod'] + '_'))
k('veritabanında anahtarın kendisi yok, yalnızca SHA-256 özeti', KA not in repr(A.tum_dukkanlar()) and Ad['api_hash'] == hashlib.sha256(KA.encode()).hexdigest())
k('anahtar ikinci açılışta görünmez', KA not in get(y, '/yonetici').get_data(as_text=True))
k('dükkân kendi panelinde anahtarı göremez', KA not in get(a, '/panel').get_data(as_text=True) and KA not in get(a, '/disa-aktar').get_data(as_text=True))
r = post(y, f'/yonetici/{ib}/api', '/yonetici', eylem='uret'); KB = re.search(r'API anahtarı: <b[^>]*>([^<]+)</b>', r.get_data(as_text=True)).group(1)
k('iki dükkânın anahtarı farklı', KA != KB and KB.startswith('sk_' + A.dukkan_getir(ib)['kod'] + '_'))
k('sağlık ucu açık', api.get('/api/v1/saglik', environ_overrides=R).status_code == 200)

# --- kimlik ---
k('anahtarsız istek 401', G({'plaka': '35ABC123'}, None).status_code == 401)
k('uydurma anahtar 401', G({'plaka': '35ABC123'}, 'sk_' + Ad['kod'] + '_' + 'x' * 40).status_code == 401)
k('biçimi bozuk anahtar 401', G({'plaka': '35ABC123'}, 'abc').status_code == 401)
k('Bearer ile de kabul', api.post('/api/v1/is-emirleri', json={'plaka': '35ABC123', 'kayit_no': 'BR'}, headers={'Authorization': 'Bearer ' + KA, 'X-Forwarded-Proto': 'https'}, environ_overrides=R).status_code == 202)
k('düz http reddedilir (400)', G({'plaka': '35ABC123'}, KA, proto='http').status_code == 400)
k('CSRF gerekmez (çerezsiz istemci)', G({'plaka': '35ABC123', 'kayit_no': 'C1'}, KA).status_code in (200, 202))
k('normal POST yine CSRF ister', api.post('/login', data={'kullanici': 'x', 'sifre': 'y'}, environ_overrides=R).status_code == 400)

# --- dükkânlar arası izolasyon ---
hizli(a, '34XYZ111', 100000); hizli(b, '34XYZ111', 50000); hizli(b, '06BBB222', 70000)
r = G({'plaka': '34 XYZ 111', 'km': 100010, 'kayit_no': 'K1', 'yapilan_islem': ['Yağ', 'Filtre'], 'not': 'fatura 1'}, KA); j = r.get_json()
k('A anahtarı A dükkânındaki iş emrine işler', r.status_code == 200 and j['eslesti'] is True)
ya = dbx(ia).execute("select yapilan_islem from is_emirleri where arac_id=(select id from araclar where plaka='34XYZ111')").fetchone()[0]
yb = dbx(ib).execute("select yapilan_islem from is_emirleri where arac_id=(select id from araclar where plaka='34XYZ111')").fetchone()[0]
k('aynı plakalı B dükkânı etkilenmedi', ya == 'Yağ, Filtre' and (yb or '') == '')
r = G({'plaka': '06BBB222', 'km': 70000, 'kayit_no': 'K2', 'yapilan_islem': 'Balata'}, KA)
k('A anahtarı B dükkânının aracını göremez (202, kayıtsız)', r.status_code == 202 and 'kayıtlı değil' in r.get_json()['neden'])
k('B dükkânının iş emri A anahtarıyla değişmedi', (dbx(ib).execute("select yapilan_islem from is_emirleri where arac_id=(select id from araclar where plaka='06BBB222')").fetchone()[0] or '') == '')
r = G({'plaka': '06BBB222', 'km': 70000, 'kayit_no': 'K1', 'yapilan_islem': 'Balata'}, KB)
k('aynı kayit_no iki dükkânda birbirinden bağımsız', r.status_code == 200 and r.get_json()['eslesti'] is True)
k('kayit_no çakışması dükkân dışına taşmaz', G({'plaka': '34XYZ111', 'km': 100010, 'kayit_no': 'K1', 'yapilan_islem': ['Yağ', 'Filtre'], 'not': 'fatura 1'}, KA).get_json().get('tekrar') is True)

# --- eşleşmeyenler: yalnızca kendi dükkânının kayıtları ---
ta = get(a, '/eslesmeyen-kayitlar').get_data(as_text=True); tb = get(b, '/eslesmeyen-kayitlar').get_data(as_text=True)
k('A dükkânı kendi bekleyenlerini görür', 'Kayıt no: K2' in ta and 'Kayıt no: C1' in ta)
k('B dükkânı A\'nın bekleyenlerini görmez', 'Kayıt no: K2' not in tb and 'Kayıt no: C1' not in tb)
k('menüde rozet yalnızca ilgili dükkânda', b'E\xc5\x9fle\xc5\x9fmeyen' in get(a, '/panel').data and b'E\xc5\x9fle\xc5\x9fmeyen' not in get(b, '/panel').data)
k('B dükkânı A\'nın kaydını işleyemez', post(b, '/eslesmeyen-kayitlar/K2/yoksay', '/panel').status_code == 302 and dbx(ia).execute("select durum from entegrasyon_kayit where kayit_no='K2'").fetchone()[0] == 'beklemede')
k('A dükkânı yoksay yapar', post(a, '/eslesmeyen-kayitlar/K2/yoksay', '/panel').status_code == 302 and dbx(ia).execute("select durum from entegrasyon_kayit where kayit_no='K2'").fetchone()[0] == 'yoksayildi')
k('yeni iş emri olarak aç (yalnızca A\'da)', post(a, '/eslesmeyen-kayitlar/C1/yeni', '/panel').status_code == 302 and dbx(ia).execute("select count(*) from araclar where plaka='35ABC123'").fetchone()[0] == 1 and dbx(ib).execute("select count(*) from araclar where plaka='35ABC123'").fetchone()[0] == 0)

# --- doğrulama ---
k('plaka zorunlu 422', G({'km': 1, 'kayit_no': 'V1'}, KA).status_code == 422)
k('geçersiz durum 422', G({'plaka': '34XYZ111', 'kayit_no': 'V2', 'durum': 'Bitti'}, KA).status_code == 422)
r = G({'plaka': '34XYZ111', 'km': 100020, 'kayit_no': 'V3', 'durum': 'Tamamlandı', 'gidis_zamani': '2026-10-22T14:30:00+03:00'}, KA)
k('durum Tamamlandı uygulanır', r.status_code == 200 and dbx(ia).execute("select durum from is_emirleri where arac_id=(select id from araclar where plaka='34XYZ111')").fetchone()[0] == 'Tamamlandı')

# --- anahtar yenileme / kapatma / dükkân kapatma ---
r = post(y, f'/yonetici/{ia}/api', '/yonetici', eylem='uret'); KA2 = re.search(r'API anahtarı: <b[^>]*>([^<]+)</b>', r.get_data(as_text=True)).group(1)
k('anahtar yenilenince eskisi geçersiz', KA2 != KA and G({'plaka': '34XYZ111', 'kayit_no': 'N1'}, KA).status_code == 401 and G({'plaka': '34XYZ111', 'kayit_no': 'N2'}, KA2).status_code in (200, 202))
post(y, f'/yonetici/{ia}/durum', '/yonetici')
k('kapatılan dükkânın anahtarı çalışmaz', G({'plaka': '34XYZ111', 'kayit_no': 'N3'}, KA2).status_code == 401)
post(y, f'/yonetici/{ia}/durum', '/yonetici')
k('yeniden açılınca yine çalışır', G({'plaka': '34XYZ111', 'kayit_no': 'N4'}, KA2).status_code in (200, 202))
post(y, f'/yonetici/{ia}/api', '/yonetici', eylem='kapat')
k('API kapatılınca anahtar çalışmaz', G({'plaka': '34XYZ111', 'kayit_no': 'N5'}, KA2).status_code == 401 and G({'plaka': '06BBB222', 'kayit_no': 'N6'}, KB).status_code in (200, 202))
k('geçersiz eylem reddedilir', post(y, f'/yonetici/{ia}/api', '/yonetici', eylem='sil').status_code == 400)

# --- bozuk dükkân veritabanı ---
A.BOZUK_DUKKAN[ib] = 'test'
r = G({'plaka': '06BBB222', 'kayit_no': 'Z1'}, KB)
k('bozuk dükkân JSON 503 alır, sunucu çökmez', r.status_code == 503 and r.get_json()['kod'] == 'SERVER_ERROR')
A.BOZUK_DUKKAN.pop(ib, None)

# --- hız sınırı ---
kotu = 'sk_' + A.dukkan_getir(ib)['kod'] + '_' + 'y' * 40
for _ in range(11): G({'plaka': '35ABC123'}, kotu)
k('çok yanlış anahtar -> 429', G({'plaka': '35ABC123'}, kotu).status_code == 429)

# --- belgeler ---
for f in ('docs/ENTEGRASYON-API.md', 'docs/openapi.yaml', 'docs/Servis-Defteri-Entegrasyon-API.pdf', 'docs/ornekler/ornek.py', 'docs/ornekler/ornek.sh', 'docs/ornekler/ornek.js', 'docs/ornekler/ornek.cs', 'docs/ornekler/ornek.ps1', 'disaridan_gonder/disaridan_gonder.py'):
    k('dosya var: ' + f, os.path.isfile(f))
print(f'{ok} geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
