# Çok dükkânlı sürüm: dükkânlar arası izolasyon, yönetici, kullanıcı adı + şifre, geçici şifre, kapatma, yedek/geri yükleme (izole geçici kopyada)
import os, re, sys, shutil, tempfile, subprocess, sqlite3, base64
os.environ.pop('APP_PASSWORD_HASH', None); os.environ['FORCE_HTTPS_COOKIE'] = '0'
d = tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), d + '/a', ignore=shutil.ignore_patterns('data', '__pycache__')); os.chdir(d + '/a'); sys.path.insert(0, '.')
import app as A; A.app.config['CIHAZ_KAPISI'] = False      # bu testler cihaz adı kapısını sınamaz; kapı hareket_test.py'de sınanır
ok = fail = 0
def k(ad, c):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print('BAŞARISIZ:', ad)
R = {'REMOTE_ADDR': '127.0.0.1'}
YSIFRE = re.search(r'şifresi: (\S+)', open('data/ILK_SIFRE.txt', encoding='utf-8').read()).group(1)
def tok(c, y='/login'): return re.search(r'name="csrf_token" value="([^"]+)"', c.get(y, environ_overrides=R).get_data(as_text=True)).group(1)
def yeni(): return A.app.test_client()
def post(c, url, y='/login', **v): v['csrf_token'] = tok(c, y); return c.post(url, data=v, environ_overrides=R)
def get(c, url): return c.get(url, environ_overrides=R)

# --- yönetici ---
y = yeni()
k('yönetici sayfası girişsiz kapalı', get(y, '/yonetici').status_code == 302 and '/yonetici/giris' in get(y, '/yonetici').headers['Location'])
k('CSRF’siz yönetici girişi reddedilir', y.post('/yonetici/giris', data={'sifre': YSIFRE}, environ_overrides=R).status_code == 400)
post(y, '/yonetici/giris', '/yonetici/giris', sifre='yanlis'); k('yanlış yönetici şifresi', get(y, '/yonetici').status_code == 302)
post(y, '/yonetici/giris', '/yonetici/giris', sifre=YSIFRE); k('yönetici girişi', get(y, '/yonetici').status_code == 200)
r = post(y, '/yonetici/ekle', '/yonetici', ad='Ahmet Oto', kullanici='Ahmet-Oto', tel='0555 111 22 33', adres='Sanayi 1')
h = r.get_data(as_text=True); m = re.search(r'Geçici şifre: <b[^>]*>([^<]+)</b>', h)
k('dükkân açıldı, geçici şifre bir kez gösterildi', r.status_code == 200 and bool(m))
SA = m.group(1); k('geçici şifre okunur biçimde', re.fullmatch(r'[a-z2-9]{5}-[a-z2-9]{5}', SA) is not None)
k('şifre ikinci açılışta görünmez', SA not in get(y, '/yonetici').get_data(as_text=True))
r = post(y, '/yonetici/ekle', '/yonetici', ad='Başka', kullanici='ahmet-oto'); k('yinelenen kullanıcı adı reddedilir', 'zaten var' in get(y, '/yonetici').get_data(as_text=True) or r.status_code == 302)
for kötü in ('ab', 'Ahmet Oto', 'ç-ğ-ü', '-x-y', 'a' * 31):
    post(y, '/yonetici/ekle', '/yonetici', ad='X', kullanici=kötü)
k('geçersiz kullanıcı adları açılmaz', len(A.tum_dukkanlar()) == 1)
post(y, '/yonetici/ekle', '/yonetici', ad='Veli Servis', kullanici='veli-servis'); B = A.dukkan_kullanici('veli-servis'); Aa = A.dukkan_kullanici('ahmet-oto')
k('iki dükkân, iki ayrı veritabanı dosyası', os.path.exists(A.db_yolu(Aa['id'])) and os.path.exists(A.db_yolu(B['id'])) and A.db_yolu(Aa['id']) != A.db_yolu(B['id']))
k('QR kodları farklı (4 harf)', len(Aa['kod']) == 4 and Aa['kod'] != B['kod'])
k('veritabanında düz şifre yok', SA not in Aa['hash'] and Aa['hash'].startswith('pbkdf2_sha256$'))
SB = None
r = post(y, f"/yonetici/{B['id']}/sifre-sifirla", '/yonetici'); SB = re.search(r'Geçici şifre: <b[^>]*>([^<]+)</b>', r.get_data(as_text=True)).group(1)

# --- dükkân A: geçici şifre → zorunlu değişim ---
a = yeni()
r = post(a, '/login', kullanici='ahmet-oto', sifre='yanlis'); k('yanlış şifre girmez', '/panel' not in r.headers.get('Location', '') and 'hatalı' in r.get_data(as_text=True))
r2 = post(a, '/login', kullanici='yok-boyle', sifre='yanlis'); k('bilinmeyen kullanıcıda aynı mesaj', 'Kullanıcı adı veya şifre hatalı' in r2.get_data(as_text=True))
r = post(a, '/login', kullanici='AHMET-OTO', sifre=SA); k('geçici şifre ile giriş (büyük harf kullanıcı adı da olur)', r.status_code == 302)
r = get(a, '/panel'); k('geçici şifrede panel kilitli, şifre sayfasına gider', r.status_code == 302 and r.headers['Location'].endswith('/sifre'))
k('şifre sayfası açılır', get(a, '/sifre').status_code == 200)
k('QR/vitrin dışındaki sayfalar da kilitli', get(a, '/araclar').status_code == 302)
for hata, kw in (('mevcut hatalı', dict(eski='x', yeni='YeniSifre-123', yeni2='YeniSifre-123')), ('kısa', dict(eski=SA, yeni='abc', yeni2='abc')), ('uyuşmaz', dict(eski=SA, yeni='YeniSifre-123', yeni2='baskasi-1234')), ('kullanıcı adı', dict(eski=SA, yeni='ahmet-oto', yeni2='ahmet-oto'))):
    post(a, '/sifre', '/sifre', **kw); k('şifre değişimi reddedilir: ' + hata, A.dukkan_getir(Aa['id'])['gecici'] == 1)
post(a, '/sifre', '/sifre', eski=SA, yeni='AhmetYeni-2026', yeni2='AhmetYeni-2026')
k('şifre değişti, geçici bayrak kalktı', A.dukkan_getir(Aa['id'])['gecici'] == 0 and get(a, '/panel').status_code == 200)
k('eski geçici şifre artık çalışmaz', 'hatalı' in post(yeni(), '/login', kullanici='ahmet-oto', sifre=SA).get_data(as_text=True))

# --- dükkân B ---
b = yeni(); post(b, '/login', kullanici='veli-servis', sifre=SB); post(b, '/sifre', '/sifre', eski=SB, yeni='VeliYeni-2026', yeni2='VeliYeni-2026'); k('B girişli', get(b, '/panel').status_code == 200)
def P(c, url, **v): v['csrf_token'] = tok(c, '/panel'); return c.post(url, data=v, environ_overrides=R)
P(a, '/is-emirleri/hizli', plaka='35ABC123', musteri_ad='ali veli', telefon='0532 111 22 33', gelis_nedeni='Yağ değişimi', giris_km='100000')
k('A kayıt açtı', 'ABC' in get(a, '/araclar').get_data(as_text=True))
k('B, A’nın aracını göremez', all('ali veli' not in get(b, u).get_data(as_text=True).lower() and '0532 111 22 33</' not in get(b, u).get_data(as_text=True) and 'value="0532 111 22 33"' not in get(b, u).get_data(as_text=True) and 'tel:+905321112233' not in get(b, u).get_data(as_text=True) for u in ('/araclar', '/musteriler', '/is-emirleri?g=hepsi', '/panel')))
k('B arama ile de bulamaz', 'ali veli' not in get(b, '/ara?q=ali').get_data(as_text=True).lower() and 'ali veli' not in get(b, '/ara?q=ABC').get_data(as_text=True).lower())
k('B, A’nın plakasını API ile göremez', 'ali' not in get(b, '/api/plaka/35ABC123').get_data(as_text=True).lower())
P(b, '/is-emirleri/hizli', plaka='35ABC123', musteri_ad='mehmet kaya', telefon='0533 000 11 22', gelis_nedeni='Fren balatası', giris_km='5000')
k('aynı plaka iki dükkânda ayrı kayıt', 'mehmet' in get(b, '/musteriler').get_data(as_text=True).lower() and 'mehmet' not in get(a, '/musteriler').get_data(as_text=True).lower())
da = sqlite3.connect(A.db_yolu(Aa['id'])); db_ = sqlite3.connect(A.db_yolu(B['id']))
k('veri fiziksel olarak ayrı dosyalarda', da.execute('select count(*) from musteriler').fetchone()[0] == 1 and db_.execute('select count(*) from musteriler').fetchone()[0] == 1)
tokA = da.execute('select qr_token from araclar').fetchone()[0]; tokB = db_.execute('select qr_token from araclar').fetchone()[0]
k('QR kodu dükkân koduyla başlar', tokA.startswith(Aa['kod']) and tokB.startswith(B['kod']) and tokA != tokB)
k('QR kodu tahmin edilemez uzunlukta', len(tokA) >= 24)
pub = yeni(); r = get(pub, '/arac/' + tokA); h = r.get_data(as_text=True)
k('herkese açık QR sayfası A’nın verisini gösterir', r.status_code == 200 and 'Ahmet' in h and '35 ABC 123' in h and 'Veli' not in h)
k('müşteri sayfasında dükkân telefonu ve Ara düğmesi var', 'tel:+905551112233' in h and 'Ara' in h)
k('açık sayfada müşteri telefonu / iç not yok', 'tel:+90532' not in h and '905321112233' not in h and '0532 111 22 33' not in h and 'mehmet' not in h.lower())
hb = get(b, '/arac/' + tokA).get_data(as_text=True)    # B girişli iken A’nın QR’ı: usta görünümü YOK
k('B girişliyken A’nın QR sayfasında usta görünümü yok', '905321112233' not in hb and '0532 111 22 33' not in hb and 'Müşteriyi Ara' not in hb)
ha = get(a, '/arac/' + tokA).get_data(as_text=True); k('A girişliyken kendi QR’ında usta görünümü var', 'Müşteriyi Ara' in ha or '0532' in ha or 'tel:' in ha)
k('B kodlu uydurma token 404', get(pub, '/arac/' + B['kod'] + 'x' * 24).status_code == 404 and get(pub, '/arac/zzzz' + 'x' * 24).status_code == 404)
k('A’nın tokenı B kodu ile açılmaz', get(pub, '/arac/' + B['kod'] + tokA[4:]).status_code == 404)

# --- etiket (Bluetooth): yalnızca kendi araçları ---
r = P(a, '/araclar/1/tspl', adet='2'); j = r.get_json(); t = base64.b64decode(j['veri']).decode()
k('A kendi etiketini alır', r.status_code == 200 and tokA in t and tokB not in t and t.rstrip().endswith('PRINT 1,2'))
k('etikette dükkân adı yazar', '"AHMET"' in t)
k('B’nin 1 numaralı aracı B’nin etiketi', tokB in base64.b64decode(P(b, '/araclar/1/tspl', adet='1').get_json()['veri']).decode())
k('girişsiz etiket verilmez', yeni().post('/araclar/1/tspl', environ_overrides=R).status_code in (302, 400, 401))
k('USB yazdırma rotaları kaldırıldı', P(a, '/araclar/1/yazdir').status_code == 404 and get(a, '/yazici/durum').status_code == 404)
k('etiket sayfasında yalnızca Bluetooth düğmesi', 'id="bt"' in get(a, '/arac/1/qr').get_data(as_text=True) and 'id="bas"' not in get(a, '/arac/1/qr').get_data(as_text=True))

# --- yedek indir ---
r = get(a, '/yedek-indir'); k('yedek indirilir (.db)', r.status_code == 200 and r.data[:15] == b'SQLite format 3' and 'attachment' in r.headers['Content-Disposition'] and 'ahmet-oto' in r.headers['Content-Disposition'])
f = tempfile.mktemp(suffix='.db'); open(f, 'wb').write(r.data); k('indirilen yedekte A’nın verisi var, B’nin yok', sqlite3.connect(f).execute("select count(*) from musteriler where ad_soyad like '%mehmet%'").fetchone()[0] == 0 and sqlite3.connect(f).execute('select count(*) from musteriler').fetchone()[0] == 1)
k('girişsiz yedek indirilemez', get(yeni(), '/yedek-indir').status_code == 302)

# --- yedek betiği + geri yükleme ---
r = subprocess.run([sys.executable, 'scripts/backup.py'], capture_output=True, text=True); k('backup.py çalışır: ' + r.stdout[-120:] + r.stderr[-120:], r.returncode == 0)
ya = A.yedek_dizin(Aa['id']); yb = A.yedek_dizin(B['id'])
k('her dükkân kendi klasörüne yedeklendi', len([x for x in os.listdir(ya) if x.startswith('servis_')]) == 1 and len([x for x in os.listdir(yb) if x.startswith('servis_')]) == 1)
k('hesap listesi de yedeklendi', len(os.listdir('data/yonetim_yedek')) == 1)
yd = os.path.join(ya, [x for x in os.listdir(ya) if x.startswith('servis_')][0])
k('A’nın yedeğinde yalnız A verisi', sqlite3.connect(yd).execute('select count(*) from musteriler').fetchone()[0] == 1 and sqlite3.connect(yd).execute("select count(*) from musteriler where ad_soyad like '%mehmet%'").fetchone()[0] == 0)
k('panelde "Son yedek: az önce"', 'Son yedek: az önce' in get(a, '/panel').get_data(as_text=True))
# A verisini boz → geri yükle
da.execute('delete from is_emirleri'); da.execute('delete from araclar'); da.execute('delete from musteriler'); da.commit(); da.close()
r = subprocess.run([sys.executable, 'scripts/geri_yukle.py', 'ahmet-oto', yd, '--evet'], capture_output=True, text=True); k('geri_yukle.py çalışır: ' + r.stdout[-150:] + r.stderr[-150:], r.returncode == 0)
k('A verisi geri geldi', sqlite3.connect(A.db_yolu(Aa['id'])).execute('select count(*) from musteriler').fetchone()[0] == 1)
k('B etkilenmedi', sqlite3.connect(A.db_yolu(B['id'])).execute('select count(*) from musteriler').fetchone()[0] == 1)
k('eski veri saklandı', any(x.startswith('geri_yukleme_oncesi_') for x in os.listdir(ya)))
r = subprocess.run([sys.executable, 'scripts/geri_yukle.py', 'ahmet-oto', 'data/yonetim.db', '--evet'], capture_output=True, text=True); k('yanlış dosya geri yüklenmez', r.returncode != 0)
bozuk = tempfile.mktemp(suffix='.db'); open(bozuk, 'wb').write(b'SQLite format 3\x00' + os.urandom(2000))
r = subprocess.run([sys.executable, 'scripts/geri_yukle.py', 'ahmet-oto', bozuk, '--evet'], capture_output=True, text=True); k('bozuk dosya geri yüklenmez', r.returncode != 0 and sqlite3.connect(A.db_yolu(Aa['id'])).execute('select count(*) from musteriler').fetchone()[0] == 1)
k('olmayan dükkân', subprocess.run([sys.executable, 'scripts/geri_yukle.py', 'yok', yd, '--evet'], capture_output=True).returncode != 0)

# --- tüm cihazlardan çıkış / diğer cihaz ---
a2 = yeni(); post(a2, '/login', kullanici='ahmet-oto', sifre='AhmetYeni-2026'); k('ikinci cihaz girişli', get(a2, '/panel').status_code == 200)
P(a, '/cikis-hepsi'); k('çıkış-hepsi: iki cihaz da düştü', get(a, '/panel').status_code == 302 and get(a2, '/panel').status_code == 302)
k('çıkış-hepsi B’yi etkilemez', get(b, '/panel').status_code == 200)
a = yeni(); post(a, '/login', kullanici='ahmet-oto', sifre='AhmetYeni-2026')

# --- yönetici: sıfırlama, kapatma ---
r = post(y, f"/yonetici/{Aa['id']}/sifre-sifirla", '/yonetici'); SA2 = re.search(r'Geçici şifre: <b[^>]*>([^<]+)</b>', r.get_data(as_text=True)).group(1)
k('sıfırlanınca açık oturum düşer', get(a, '/panel').status_code == 302)
k('sıfırlanınca eski şifre çalışmaz', 'hatalı' in post(yeni(), '/login', kullanici='ahmet-oto', sifre='AhmetYeni-2026').get_data(as_text=True))
k('yeni geçici şifre çalışır ve değişim ister', (lambda c: (post(c, '/login', kullanici='ahmet-oto', sifre=SA2), get(c, '/panel').headers.get('Location', '').endswith('/sifre'))[1])(yeni()))
post(y, f"/yonetici/{Aa['id']}/durum", '/yonetici'); k('dükkân kapatıldı', A.dukkan_getir(Aa['id'])['aktif'] == 0)
a = yeni(); r = post(a, '/login', kullanici='ahmet-oto', sifre=SA2); k('kapalı hesap giremez ("kapalı" mesajı)', 'kapalı' in r.get_data(as_text=True) and get(a, '/panel').status_code == 302)
k('kapalı dükkânın QR sayfası 404', get(yeni(), '/arac/' + tokA).status_code == 404)
k('kapalı dükkân B’yi etkilemez', get(b, '/panel').status_code == 200 and get(yeni(), '/arac/' + tokB).status_code == 200)
post(y, f"/yonetici/{Aa['id']}/durum", '/yonetici'); k('yeniden açıldı, QR yine çalışır', A.dukkan_getir(Aa['id'])['aktif'] == 1 and get(yeni(), '/arac/' + tokA).status_code == 200)
post(y, f"/yonetici/{Aa['id']}/bilgi", '/yonetici', ad='Ahmet Oto 2', tel='0555 999 88 77', adres='Yeni adres'); k('yönetici bilgi güncelledi', A.dukkan_getir(Aa['id'])['ad'] == 'Ahmet Oto 2')
k('yönetici dükkân sayfalarına giremez', get(y, '/panel').status_code == 302)
k('dükkân yönetici sayfasına giremez', get(b, '/yonetici').status_code == 302 and b.post('/yonetici/ekle', data={'csrf_token': tok(b, '/panel'), 'ad': 'x', 'kullanici': 'xyz'}, environ_overrides=R).status_code == 302 and len(A.tum_dukkanlar()) == 2)
k('CSRF’siz yönetici işlemi reddedilir', y.post('/yonetici/ekle', data={'ad': 'x', 'kullanici': 'xyz'}, environ_overrides=R).status_code == 400)
k('GET /logout durum değiştirmez', get(b, '/logout').status_code == 302 and get(b, '/panel').status_code == 200)
r = post(b, '/logout', '/panel'); k('POST /logout çıkarır', get(b, '/panel').status_code == 302)

# --- giriş sınırı ---
z = yeni()
for _ in range(6): post(z, '/login', kullanici='ahmet-oto', sifre='hep-yanlis')
k('5 yanlış denemeden sonra sınır devreye girer', 'Çok fazla' in post(z, '/login', kullanici='ahmet-oto', sifre='hep-yanlis').get_data(as_text=True))
print(f'\n{ok} kontrol geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
