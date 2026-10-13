import os as _os; _os.environ['APP_PASSWORD_HASH']='pbkdf2_sha256$600000$0123456789abcdef0123456789abcdef$bc43d8da4a5cfd47df54d15115d65eafe20121e09ab04ca54ddf8dd8397d4335'   # test şifresi: TestSifre-12345!
"""Etiket (58x40 yatay) testleri, yazıcı OLMADAN. Kullanım: python3 tests/etiket_test.py"""
import os, re, shutil, sys, tempfile, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import etiket_yazici as EY
ok = kotu = 0
def kontrol(ad, kosul):
    global ok, kotu
    if kosul: ok += 1
    else: kotu += 1; print('BAŞARISIZ:', ad)
URL = 'https://servis.example.com/arac/Ab3dEf6hIj9lMn2pQr5tUv8x'      # gerçek token uzunluğu (24 karakter)
tmp = tempfile.mkdtemp(); W, H = 464, 320

# 1) Şablon: komutlar, ASCII, etiket sınırları içinde
for ad in ('SERVIS DEFTERI', 'DENEME OTO', 'A'):
    os.environ['ETIKET_BASLIK'] = ad
    for pl in ('35ABC123', '06DEM202', '34AB1234', '1', 'YABANCI-1'):
        kom = EY.tspl_komutlari(pl, URL); b = EY.tspl_bayt(kom)
        tamam = kom[0] == 'SIZE 58 mm,40 mm' and b.decode('ascii').rstrip().endswith('PRINT 1,1') and b.startswith(b'\r\n')
        for k in kom:
            m = re.match(r'TEXT (\d+),(\d+),"(\d)",0,(\d+),(\d+),"(.*)"', k)
            if m:
                x, y, f, t = int(m[1]), int(m[2]), m[3], m[6]; cw, ch = EY._FONT[f]
                tamam &= x >= 0 and y >= 0 and x + len(t) * cw + 1 <= W and y + ch <= H
            q = re.match(r'QRCODE (\d+),(\d+),M,(\d+),A,0,"(.*)"', k)
            if q:
                x, y, hc = int(q[1]), int(q[2]), int(q[3]); v, mod = EY._qr_bilgi(URL)
                tamam &= x >= 8 and y >= 8 and x + mod * hc <= W - 8 and y + mod * hc <= H - 8       # sürüm ne olursa
                tamam &= x - 24 + (17 + 4 * (v + 1)) * hc <= W and y - 16 + (17 + 4 * (v + 1)) * hc <= H   # yazıcı bir üst sürüm seçse bile sığar (kaydırmasız)
                tamam &= mod * hc >= 24 * 8 - 40                                                       # QR en az ~21 mm
        kontrol(f'şablon ({ad!r}, {pl}) sınırlar içinde', tamam)
os.environ.pop('ETIKET_BASLIK', None)
kom = EY.tspl_komutlari('35ABC123', URL)
kontrol('varsayılan başlık: SERVIS / DEFTERI', '"SERVIS"' in '\n'.join(kom) and '"DEFTERI"' in '\n'.join(kom))
kontrol('varsayılan kaydırma: 3 mm sağ, 2 mm aşağı', any(k.startswith('QRCODE 36,36,') for k in kom))
os.environ['ETIKET_X_OFFSET'] = '0'; os.environ['ETIKET_Y_OFFSET'] = '0'
kontrol('ETIKET_X/Y_OFFSET ile ayarlanır', any(k.startswith('QRCODE 12,20,') for k in EY.tspl_komutlari('35ABC123', URL)))
os.environ.pop('ETIKET_X_OFFSET'); os.environ.pop('ETIKET_Y_OFFSET')
kontrol('plaka satır satır', all(f'"{p}"' in '\n'.join(kom) for p in ('35', 'ABC', '123')))
kontrol('Türkçe harf ASCII\'ye çevrilir', EY._ascii('Çağrı Şöför ĞÜ') == 'CAGRI SOFOR GU')
os.environ['ETIKET_BASLIK'] = 'Çok Uzun Bir İşletme Adı Burada'; kontrol('başlık 18 karakterle sınırlı', len(EY._baslik()) <= 18); os.environ.pop('ETIKET_BASLIK')
kontrol('DENSITY/GAP/DIRECTION', 'GAP 3 mm,0 mm' in kom and 'DIRECTION 1' in kom and 'DENSITY 8' in kom)

# 2) Yazma: geçici dosya (lp aygıtı gibi)
lp = os.path.join(tmp, 'lp0'); open(lp, 'wb').close(); os.environ['ETIKET_AYGIT'] = lp; EY._son_gonderim.clear()
s, m = EY.etiket_bas('35ABC123', URL, 2)
v = open(lp, 'rb').read()
kontrol('etiket_bas lp yoluna yazar', s and v.startswith(b'\r\nSIZE 58 mm,40 mm') and v.rstrip().endswith(b'PRINT 1,2'))
s2, m2 = EY.etiket_bas('35ABC123', URL); kontrol('çift dokunuş engellenir', (not s2) and '3 saniye' in m2)
EY._son_gonderim.clear(); s3, m3 = EY.etiket_bas('34XYZ789', URL, 99); kontrol('adet en çok 20', s3 and open(lp, 'rb').read().rstrip().endswith(b'PRINT 1,20'))
os.environ['ETIKET_AYGIT'] = os.path.join(tmp, 'yok'); EY._son_gonderim.clear()
s, m = EY.etiket_bas('X', URL); kontrol('yazıcı yok -> anlaşılır mesaj', (not s) and 'bağlı değil' in m)
if os.geteuid() != 0:
    os.environ['ETIKET_AYGIT'] = lp; os.chmod(lp, 0); EY._son_gonderim.clear()
    s, m = EY.etiket_bas('Y', URL); kontrol('izin yok -> mesaj', (not s) and 'izin' in m); os.chmod(lp, 0o644)
fifo = os.path.join(tmp, 'fifo'); os.mkfifo(fifo); os.environ['ETIKET_AYGIT'] = fifo; EY._son_gonderim.clear()
fd = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)           # okuyan var ama hiç okumuyor -> tampon dolunca zaman aşımı
t0 = time.monotonic(); ok_, m = EY.gonder(b'x' * 300000); kontrol('yazıcı yanıtsızsa zaman aşımı (donmaz)', (not ok_) and 'yanıt vermiyor' in m and time.monotonic() - t0 < 12); os.close(fd)

# 3) Önizleme
png = EY.onizleme_png(EY.tspl_komutlari('35ABC123', URL)); kontrol('önizleme PNG', png[:8] == b'\x89PNG\r\n\x1a\n')

# 4) Flask uçları
kaynak = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); hedef = os.path.join(tmp, 'app')
shutil.copytree(kaynak, hedef, ignore=shutil.ignore_patterns('data', '__pycache__', '.env')); sys.path.insert(0, hedef); os.chdir(hedef)
os.environ['ETIKET_AYGIT'] = lp; open(lp, 'wb').close(); EY._son_gonderim.clear()
import app as A
A.app.config['SESSION_COOKIE_SECURE'] = False
c = A.app.test_client(); R = {'REMOTE_ADDR': '127.0.0.1'}
tok = lambda h: re.search(r'name="csrf_token" value="([^"]+)"', h).group(1)
kontrol('girişsiz yazdırma reddedilir', c.post('/araclar/1/yazdir').status_code in (302, 400))
c.post('/login', data={'sifre': 'TestSifre-12345!', 'csrf_token': tok(c.get('/login').get_data(as_text=True))}, environ_overrides=R)
csrf = tok(c.get('/is-emirleri').get_data(as_text=True))
c.post('/is-emirleri/hizli', data={'csrf_token': csrf, 'plaka': '35ABC123', 'musteri_ad': 'ali', 'telefon': '0532 111 22 33', 'gelis_nedeni': 'x'})
h = c.get('/arac/1/qr').get_data(as_text=True)
kontrol('etiket ekranı: tek tür, rulo seçimi/test yok', 'Yazıcıdan Çıkart' in h and '58 × 40' in h and 'Takılı rulo' not in h and 'Test etiketi' not in h)
r = c.post('/araclar/1/yazdir', data={'csrf_token': csrf, 'adet': '2'}, headers={'X-Requested-With': 'fetch'}); j = r.get_json()
kontrol('POST /araclar/1/yazdir -> ok JSON', r.status_code == 200 and j['ok'] and j['plaka'] == '35 ABC 123' and b'PRINT 1,2' in open(lp, 'rb').read())
kontrol('CSRF’siz POST reddedilir', c.post('/araclar/1/yazdir').status_code == 400)
d = c.get('/yazici/durum').get_json(); kontrol('yazici/durum', d['durum'] == 'hazir')
r = c.get('/araclar/1/etiket_onizleme.png'); kontrol('önizleme ucu', r.status_code == 200 and r.data[:4] == b'\x89PNG')
kontrol('kaldırılan uçlar yok (rulo, test)', c.post('/yazici/rulo', data={'csrf_token': csrf}).status_code == 404 and c.post('/yazici/test', data={'csrf_token': csrf}).status_code == 404)
kontrol('oturum süresi 90 gün', A.app.config['PERMANENT_SESSION_LIFETIME'] == 90 * 86400)
shutil.rmtree(tmp, ignore_errors=True)
print(f'\n{ok} kontrol geçti, {kotu} başarısız'); sys.exit(1 if kotu else 0)
