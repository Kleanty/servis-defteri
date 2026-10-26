import os as _os; _os.environ['APP_PASSWORD_HASH']='pbkdf2_sha256$600000$0123456789abcdef0123456789abcdef$bc43d8da4a5cfd47df54d15115d65eafe20121e09ab04ca54ddf8dd8397d4335'   # test şifresi: TestSifre-12345!
"""Hızlı duman testi: uygulamanın GEÇİCİ bir kopyasında çalışır, gerçek veriye dokunmaz.
Kullanım:  python3 tests/smoke_test.py   (sunucuda: sudo systemctl stop gerek yok)"""
import os, re, shutil, sys, tempfile
kaynak = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); tmp = tempfile.mkdtemp()
hedef = os.path.join(tmp, 'app'); shutil.copytree(kaynak, hedef, ignore=shutil.ignore_patterns('data', '__pycache__', '.env'))
sys.path.insert(0, hedef); os.chdir(hedef)
import app as A; A.app.config['CIHAZ_KAPISI'] = False      # bu testler cihaz adı kapısını sınamaz; kapı hareket_test.py'de sınanır
A.app.config['SESSION_COOKIE_SECURE'] = False
c = A.app.test_client(); ok = 0; kotu = 0
def kontrol(ad, kosul):
    global ok, kotu
    if kosul: ok += 1
    else: kotu += 1; print('✗ BAŞARISIZ:', ad)
tok = lambda h: re.search(r'name="csrf_token" value="([^"]+)"', h).group(1)
kontrol('girişsiz /panel yönlendirir', c.get('/panel').status_code == 302)
t = tok(c.get('/login').get_data(as_text=True))
R = {'REMOTE_ADDR': '127.0.0.1'}
r = c.post('/login', data={'sifre': 'TestSifre-12345!', 'csrf_token': t}, environ_overrides=R)
kontrol('giriş', r.status_code == 302)
# oturum çerezi 14 gün geçerli ve her istekte yenilenir
from email.utils import parsedate_to_datetime as _pd
from datetime import datetime as _dt, timezone as _tz
_sc = [x for x in c.get('/panel').headers.getlist('Set-Cookie') if x.startswith('session=')]
_ex = re.search(r'Expires=([^;]+)', _sc[0]) if _sc else None
_gun = (_pd(_ex.group(1)) - _dt.now(_tz.utc)).total_seconds() / 86400 if _ex else 0
kontrol('oturum çerezi her istekte yenilenir (≈14 gün)', 13.9 < _gun < 14.1)
csrf = tok(c.get('/is-emirleri').get_data(as_text=True))
P = lambda u, **kw: c.post(u, data={'csrf_token': csrf, **kw})
G = lambda u: c.get(u)

for u in ['/panel', '/is-emirleri', '/is-emirleri?g=tamam', '/is-emirleri?g=hepsi', '/musteriler', '/araclar', '/istatistik', '/ara?q=x', '/saglik', '/']:
    kontrol('GET ' + u, G(u).status_code == 200)
kontrol('sesli rota kaldırıldı', c.post('/api/sesli_is_emri', json={'metin': 'x'}, headers={'X-CSRF-Token': csrf}).status_code == 404)
kontrol('?yeni= plakayı doldurur', 'value="35ABC123"' in G('/is-emirleri?yeni=35ABC123').get_data(as_text=True))
h = G('/is-emirleri').get_data(as_text=True)
kontrol('kategori paneli (her kategori bir kez)', h.count('class="mt-2 kat"') == len(A.ISLEM_KATEGORILERI))
kontrol('işlemler paneli 70+ chip, hızlı satır yok', h.count('data-chip=') >= 70 and 'hizli_islemler' not in h)

# yeni müşteri + araç + iş emri, çoklu işlem
P('/is-emirleri/hizli', plaka='35 abc 123', musteri_ad='ahmet yılmaz', telefon='0532 111 22 33', gelis_nedeni='Yağ değişimi, Yağ filtresi, Fren balatası', giris_km='100000')
con = A.sqlite3.connect(A.DB_PATH); con.row_factory = A.sqlite3.Row
kontrol('iş emri açıldı', con.execute("SELECT COUNT(*) FROM is_emirleri WHERE gelis_nedeni LIKE '%Fren balatası%'").fetchone()[0] == 1)
kontrol('ad büyük harf', con.execute("SELECT ad_soyad FROM musteriler").fetchone()[0] == 'AHMET YILMAZ')
# aynı plaka, telefon istenmez
P('/is-emirleri/hizli', plaka='35ABC123', gelis_nedeni='Akü', giris_km='100500')
kontrol('kayıtlı araç ikinci iş emri', con.execute('SELECT COUNT(*) FROM is_emirleri').fetchone()[0] == 2)
# hatalar büyük mesajla dönüyor
r = P('/is-emirleri/hizli', plaka='99ZZ1', musteri_ad='x', telefon='0532 111 22 33', giris_km='1'); kontrol('geçersiz plaka 400', r.status_code == 400 and 'alert-danger fs-5' in r.get_data(as_text=True))
r = P('/is-emirleri/hizli', plaka='34XYZ99', musteri_ad='ali', telefon='123', giris_km='1'); kontrol('geçersiz telefon 400', r.status_code == 400)
# arama
b = G('/ara?q=35ABC123').get_data(as_text=True); kontrol('arama: araç kartı + iş emri aç', 'İş Emri Aç' in b and 'tel:+905321112233' in b and 'wa.me/905321112233' in b)
b = G('/ara?q=55ZZZ999').get_data(as_text=True); kontrol('arama: yok -> yeni iş emri aç', 'için yeni iş emri aç' in b)
# müşteri QR sayfası: giriş yapılmış/yapılmamış herkese AYNI sade sayfa; telefon, arama, WhatsApp yok; isim maskeli
tok_=con.execute('SELECT qr_token FROM araclar').fetchone()[0]
anon=A.app.test_client(); ph=anon.get('/arac/'+tok_).get_data(as_text=True); uh=G('/arac/'+tok_).get_data(as_text=True)
kontrol('QR (herkes): telefon/arama/WhatsApp yok', all(x not in ph for x in ['5321112233','0555 000','Ustaya Sor','Ustayı Ara','wa.me','tel:','Müşteriyi Ara']))
kontrol('QR (usta girişli): Müşteriyi Ara + Müşteriye Haber Et var', all(x in uh for x in ['Müşteriyi Ara','tel:+905321112233','Müşteriye Haber Et','wa.me']))
kontrol('QR: isim maskeli (A***i V***i gibi), tam isim yok', 'ALİ VELİ' not in ph and 'Ahmet Yılmaz' not in ph and ('*' in ph))
kontrol('QR: servis geçmişi ve sağ üst site bağlantısı var', 'Servis geçmişi' in ph and 'class="sit-ust"' in ph)
# durum / teslim
iid = con.execute("SELECT id FROM is_emirleri ORDER BY id LIMIT 1").fetchone()[0]
P(f'/is-emirleri/durum/{iid}', durum='Devam Ediyor')
P(f'/is-emirleri/durum/{iid}', durum='Tamamlandı')
s = con.execute('SELECT durum,gidis_at FROM is_emirleri WHERE id=?', (iid,)).fetchone()
kontrol('teslim: durum Tamamlandı + teslim zamanı yazıldı', s[0] == 'Tamamlandı' and bool(s[1]))
# bakım hatırlatması: yalnız periyodik/yağ değişimi/yağ filtresi sayılır
kontrol('Fren balatası bakım sayılmaz', not any(k in A.fold('Fren balatası') for k in A.BAKIM_ANAHTAR) and any(k in A.fold('Yağ filtresi') for k in A.BAKIM_ANAHTAR))
kontrol('/panel + /istatistik teslim sonrası', G('/panel').status_code == 200 and G('/istatistik').status_code == 200)
# silme: bağlı kayıt varken engellenir
mid = con.execute('SELECT id FROM musteriler').fetchone()[0]; P(f'/musteriler/sil/{mid}')
kontrol('araçlı müşteri silinmez', con.execute('SELECT COUNT(*) FROM musteriler').fetchone()[0] == 1)
kontrol('CSRF’siz POST reddedilir', c.post('/is-emirleri/hizli', data={'plaka': '35ABC123'}).status_code == 400)
shutil.rmtree(tmp, ignore_errors=True)
print(f'\n{ok} kontrol geçti, {kotu} başarısız'); sys.exit(1 if kotu else 0)
