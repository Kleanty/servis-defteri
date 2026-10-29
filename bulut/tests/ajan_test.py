# Yazdırma ajanı (dükkân bilgisayarındaki USB yazıcı): kuyruk, dükkâna özel ajan anahtarı, izolasyon, süre dolumu, ajan programı.
import os, re, sys, shutil, tempfile, sqlite3, base64, threading, time, socket
os.environ.pop('APP_PASSWORD_HASH', None); os.environ['FORCE_HTTPS_COOKIE'] = '0'
d = tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), d + '/a', ignore=shutil.ignore_patterns('data', '__pycache__')); os.chdir(d + '/a'); sys.path.insert(0, '.')
import app as A; A.app.config['CIHAZ_KAPISI'] = False
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
def giris(kul, sif):
    c = A.app.test_client(); post(c, '/login', kullanici=kul, sifre=sif); return c
a = giris('ahmet-oto', 'Ahmet-Sifre-1'); b = giris('veli-servis', 'Veli-Sifre-12')
def dbx(i): return sqlite3.connect(A.db_yolu(i))
def arac(c, plaka):
    post(c, '/is-emirleri/hizli', '/panel', plaka=plaka, giris_km='1000', gelis_nedeni='Bakım')
    return int(dbx(ia if c is a else ib).execute('select id from araclar where plaka=?', (plaka,)).fetchone()[0])
aa = arac(a, '34AJN101'); bb = arac(b, '06AJN202')

# --- ajan anahtarı yokken kapalı ---
j = lambda c, y, **kw: c.post(y, json=kw.pop('json', {}), headers={'X-Forwarded-Proto': 'https', **kw.pop('headers', {})}, environ_overrides=R)
ajan = A.app.test_client()
k('anahtar yokken ajan uç noktası 401', j(ajan, '/api/v1/ajan/sonraki', headers={'X-API-Key': 'ya_xxxx_' + 'a' * 30}).status_code == 401)
k('ajan kapalıyken etiket sayfasında düğme yok', 'id="aj"' not in get(a, f'/arac/{aa}/qr').get_data(as_text=True))
r = post(a, f'/araclar/{aa}/yazdir', f'/arac/{aa}/qr', adet='1'); k('ajan kapalıyken kuyruğa alınmaz (400)', r.status_code == 400 and not r.get_json()['ok'])

# --- yönetici üretir ---
y = A.app.test_client(); post(y, '/yonetici/giris', '/yonetici/giris', sifre=YSIFRE)
k('yönetici satırında ajan düğmesi', 'Ajan anahtarı üret' in get(y, '/yonetici').get_data(as_text=True))
k('dükkân girişi anahtar üretemez', post(a, f'/yonetici/{ia}/ajan', '/panel', eylem='uret').status_code in (302, 400, 401, 403))
k('yönetici olmayan anahtar üretemez', A.app.test_client().post(f'/yonetici/{ia}/ajan', data={'eylem': 'uret'}, environ_overrides=R).status_code in (302, 400))
r = post(y, f'/yonetici/{ia}/ajan', '/yonetici', eylem='uret'); h = r.get_data(as_text=True)
m = re.search(r'Ajan anahtarı: <b[^>]*>([^<]+)</b>', h); KA = m.group(1) if m else ''
k('anahtar ya_<kod>_ biçiminde ve yalnız bir kez gösterilir', re.fullmatch(r'ya_[a-z0-9]{4}_[A-Za-z0-9_-]{30,64}', KA) is not None and KA not in get(y, '/yonetici').get_data(as_text=True))
c = A.yonetim_db(); sat = c.execute('select ajan_hash from dukkanlar where id=?', (ia,)).fetchone()[0]; c.close()
k('anahtarın kendisi değil özeti saklanır', bool(sat) and KA not in sat and len(sat) == 64)
r = post(y, f'/yonetici/{ib}/ajan', '/yonetici', eylem='uret'); KB = re.search(r'Ajan anahtarı: <b[^>]*>([^<]+)</b>', r.get_data(as_text=True)).group(1)
k('geçersiz eylem reddedilir', post(y, f'/yonetici/{ia}/ajan', '/yonetici', eylem='sil').status_code == 400)
k('API anahtarı ile ajan anahtarı ayrı: ajan anahtarı API\'yi açmaz', ajan.post('/api/v1/is-emirleri', json={'plaka': '34AJN101'}, headers={'X-API-Key': KA, 'X-Forwarded-Proto': 'https'}, environ_overrides=R).status_code in (401, 404))

# --- kimlik / HTTPS ---
k('http ile ajan anahtarı kabul edilmez', ajan.post('/api/v1/ajan/ping', json={}, headers={'X-API-Key': KA, 'X-Forwarded-Proto': 'http'}, environ_overrides=R).status_code == 400)
r = j(ajan, '/api/v1/ajan/ping', headers={'X-API-Key': KA}); k('ping: anahtar doğru, dükkân adı döner', r.status_code == 200 and r.get_json()['dukkan'] == 'Ahmet Oto')
k('Bearer ile de kabul', j(ajan, '/api/v1/ajan/ping', headers={'Authorization': 'Bearer ' + KA}).status_code == 200)
k('ping kuyruğa dokunmaz / hareket yazmaz', dbx(ia).execute('select count(*) from hareketler where olay like "%ajan%" or cihaz like "%ajan%"').fetchone()[0] == 0)

# --- sayfa düğmesi + kuyruğa alma ---
h = get(a, f'/arac/{aa}/qr').get_data(as_text=True)
k('ajan açıkken etiket sayfasında düğme (Bluetooth düğmesi de durur)', 'id="aj"' in h and 'Etiketi Bluetooth ile çıkart' in h)
k('B dükkânı da kendi anahtarını aldığı için düğmesi var', 'id="aj"' in get(b, f'/arac/{bb}/qr').get_data(as_text=True))   # B de anahtar aldı
r = post(a, f'/araclar/{aa}/yazdir', f'/arac/{aa}/qr', adet='2'); js = r.get_json(); I1 = js['is_id']
k('kuyruğa alınır, ajan henüz bağlı değil bilgisi', r.status_code == 200 and js['ok'] and I1 > 0)
r = post(a, f'/araclar/{aa}/yazdir', f'/arac/{aa}/qr', adet='2'); k('çift dokunuş aynı işi döndürür (çift kuyruk yok)', r.get_json()['is_id'] == I1 and dbx(ia).execute('select count(*) from yazdirma_isleri').fetchone()[0] == 1)
r = post(a, '/araclar/99999/yazdir', f'/arac/{aa}/qr', adet='1'); k('olmayan araç için iş açılamaz (404)', r.status_code == 404)
k('oturumsuz kuyruğa alınamaz', A.app.test_client().post(f'/araclar/{aa}/yazdir', data={'adet': '1'}, environ_overrides=R).status_code in (302, 400, 401))
k('durum: bekliyor', get(a, f'/yazdirma/{I1}/durum').get_json()['durum'] == 'bekliyor')
k('başka dükkân bu işin durumunu göremez (404)', get(b, f'/yazdirma/{I1}/durum').status_code == 404)
k('oturumsuz durum 401 JSON', A.app.test_client().get(f'/yazdirma/{I1}/durum', environ_overrides=R).status_code == 401)

# --- ajan alır ---
r = j(ajan, '/api/v1/ajan/sonraki', headers={'X-API-Key': KA}); iş = r.get_json()['is']
k('ajan işi alır: TSPL, plaka, adet', iş and iş['id'] == I1 and iş['plaka'] == '34AJN101' and iş['adet'] == 2)
raw = base64.b64decode(iş['veri']); k('baytlar geçerli TSPL (SIZE .. PRINT 1,2)', b'SIZE' in raw and raw.rstrip().endswith(b'PRINT 1,2'))
k('ikinci sorgu aynı işi vermez (çift basım yok)', j(ajan, '/api/v1/ajan/sonraki', headers={'X-API-Key': KA}).get_json()['is'] is None)
IB = post(b, f'/araclar/{bb}/yazdir', f'/arac/{bb}/qr', adet='7').get_json()['is_id']
r_ = j(ajan, '/api/v1/ajan/sonraki', headers={'X-API-Key': KA}).get_json()['is']
k('izolasyon: B\'nin kuyruğunda iş varken A\'nın anahtarı onu ALAMAZ', r_ is None and dbx(ib).execute('select durum from yazdirma_isleri where id=?', (IB,)).fetchone()[0] == 'bekliyor')
r_ = j(ajan, '/api/v1/ajan/sonraki', headers={'X-API-Key': KB}).get_json()['is']; k('B\'nin anahtarı kendi işini alır', r_ and r_['id'] == IB and r_['adet'] == 7)
c = dbx(ib); c.execute('delete from yazdirma_isleri'); c.commit(); c.close()
k('durum: alındı', get(a, f'/yazdirma/{I1}/durum').get_json()['durum'] == 'alindi')
k('ajan bağlı görünür', get(a, f'/yazdirma/{I1}/durum').get_json()['bagli'] is True and A.ajan_bagli(ia))
k('başka dükkânın anahtarı bu işe sonuç yazamaz', j(ajan, '/api/v1/ajan/sonuc', headers={'X-API-Key': KB}, json={'id': I1, 'ok': True}).status_code == 404)
k('sonuç: id geçersiz 400', j(ajan, '/api/v1/ajan/sonuc', headers={'X-API-Key': KA}, json={'id': 'x'}).status_code == 400)
j(ajan, '/api/v1/ajan/sonuc', headers={'X-API-Key': KA}, json={'id': I1, 'ok': True})
k('durum: basıldı', get(a, f'/yazdirma/{I1}/durum').get_json()['durum'] == 'basildi')
j(ajan, '/api/v1/ajan/sonuc', headers={'X-API-Key': KA}, json={'id': I1, 'ok': False, 'mesaj': 'x'})
k('bitmiş iş sonradan değişmez', get(a, f'/yazdirma/{I1}/durum').get_json()['durum'] == 'basildi')

# --- hata bildirimi ---
I2 = post(a, f'/araclar/{aa}/yazdir', f'/arac/{aa}/qr', adet='1').get_json()['is_id']
j(ajan, '/api/v1/ajan/sonraki', headers={'X-API-Key': KA}); j(ajan, '/api/v1/ajan/sonuc', headers={'X-API-Key': KA}, json={'id': I2, 'ok': False, 'mesaj': 'Yazıcı çevrimdışı\n' + 'x' * 500})
r = get(a, f'/yazdirma/{I2}/durum').get_json(); k('hata mesajı iletilir, kısaltılır, satır sonu yok', r['durum'] == 'hata' and 'çevrimdışı' in r['mesaj'] and len(r['mesaj']) <= 200 and '\n' not in r['mesaj'])

# --- süre dolumu ---
I3 = post(a, f'/araclar/{aa}/yazdir', f'/arac/{aa}/qr', adet='3').get_json()['is_id']
eski = (A.datetime.now() - A.timedelta(seconds=A.AJAN_BEKLEYEN_SN + 60)).strftime('%Y-%m-%d %H:%M:%S')
c = dbx(ia); c.execute('update yazdirma_isleri set olusturuldu_at=? where id=?', (eski, I3)); c.commit(); c.close()
r = get(a, f'/yazdirma/{I3}/durum').get_json(); k('alınmayan eski etiket "süresi doldu" olur, sonradan basılmaz', r['durum'] == 'hata' and 'Süresi doldu' in r['mesaj'] and j(ajan, '/api/v1/ajan/sonraki', headers={'X-API-Key': KA}).get_json()['is'] is None)
I4 = post(a, f'/araclar/{aa}/yazdir', f'/arac/{aa}/qr', adet='4').get_json()['is_id']
j(ajan, '/api/v1/ajan/sonraki', headers={'X-API-Key': KA})
alinma = (A.datetime.now() - A.timedelta(seconds=A.AJAN_ALINAN_SN + 30)).strftime('%Y-%m-%d %H:%M:%S')
c = dbx(ia); c.execute('update yazdirma_isleri set alindi_at=? where id=?', (alinma, I4)); c.commit(); c.close()
r = get(a, f'/yazdirma/{I4}/durum').get_json(); k('alınıp sonuç gelmeyen iş tekrar BASILMAZ, "emin değil" olur', r['durum'] == 'hata' and 'yanıt gelmedi' in r['mesaj'] and j(ajan, '/api/v1/ajan/sonraki', headers={'X-API-Key': KA}).get_json()['is'] is None)
c = dbx(ia); c.execute("update yazdirma_isleri set olusturuldu_at='2020-01-01 00:00:00' where id=?", (I1,)); c.commit(); c.close()
A._ajan_sil_son.clear(); get(a, f'/yazdirma/{I2}/durum'); k('7 günden eski kayıtlar silinir', dbx(ia).execute('select count(*) from yazdirma_isleri where id=?', (I1,)).fetchone()[0] == 0)

# --- eşzamanlı alım: tek iş, 8 ajan aynı anda -> yalnız biri alır ---
IT = post(a, f'/araclar/{aa}/yazdir', f'/arac/{aa}/qr', adet='6').get_json()['is_id']
alan = []
def al_():
    cc = A.app.test_client(); rr = cc.post('/api/v1/ajan/sonraki', json={}, headers={'X-Forwarded-Proto': 'https', 'X-API-Key': KA}, environ_overrides=R).get_json()
    if rr and rr.get('is'): alan.append(rr['is']['id'])
ths = [threading.Thread(target=al_) for _ in range(8)]; [t.start() for t in ths]; [t.join() for t in ths]
k('8 eşzamanlı ajan: iş tam bir kez verilir (çift basım yok)', alan == [IT])
j(ajan, '/api/v1/ajan/sonuc', headers={'X-API-Key': KA}, json={'id': IT, 'ok': True})

# --- sonuç ucu sağlamlığı ---
IW = post(a, f'/araclar/{aa}/yazdir', f'/arac/{aa}/qr', adet='8').get_json()['is_id']          # bekliyor (alınmadı)
n0 = dbx(ia).execute("select count(*) from hareketler where olay like 'Etiket%dükkân bilgisayarı%'").fetchone()[0]
r = j(ajan, '/api/v1/ajan/sonuc', headers={'X-API-Key': KA}, json={'id': IW, 'ok': True})
k('alınmamış işe sonuç gelirse değişmez ve hareket YAZILMAZ', r.get_json()['uygulandi'] is False and get(a, f'/yazdirma/{IW}/durum').get_json()['durum'] == 'bekliyor' and dbx(ia).execute("select count(*) from hareketler where olay like 'Etiket%dükkân bilgisayarı%'").fetchone()[0] == n0)
j(ajan, '/api/v1/ajan/sonraki', headers={'X-API-Key': KA}); j(ajan, '/api/v1/ajan/sonuc', headers={'X-API-Key': KA}, json={'id': IW, 'ok': 'false', 'mesaj': 'x'})
k('"false" metni başarı sayılmaz', get(a, f'/yazdirma/{IW}/durum').get_json()['durum'] == 'hata')
k('id=Infinity 500 vermez', A.app.test_client().post('/api/v1/ajan/sonuc', data='{"id": Infinity, "ok": true}', content_type='application/json', headers={'X-Forwarded-Proto': 'https', 'X-API-Key': KA}, environ_overrides=R).status_code == 400)
k('gövde JSON listesi 500 vermez', A.app.test_client().post('/api/v1/ajan/sonuc', json=[1, 2], headers={'X-Forwarded-Proto': 'https', 'X-API-Key': KA}, environ_overrides=R).status_code == 400)
# aynı araç+adet bekleyen iş varken yeni iş açılmaz (bilgisayar kapalıyken art arda dokunuş)
c = dbx(ia); c.execute("update yazdirma_isleri set olusturuldu_at='2020-01-01 00:00:00' where durum='bekliyor'"); c.commit(); c.close()
I9 = post(a, f'/araclar/{aa}/yazdir', f'/arac/{aa}/qr', adet='9').get_json()['is_id']; I9b = post(a, f'/araclar/{aa}/yazdir', f'/arac/{aa}/qr', adet='9').get_json()['is_id']
k('bekleyen aynı etiket varken tekrar dokunuş yığılmaz', I9 == I9b and dbx(ia).execute("select count(*) from yazdirma_isleri where adet=9").fetchone()[0] == 1)
# muhasebe API'si ile ajan hız sınırı sayacı ayrı
for _ in range(11): A.app.test_client().post('/api/v1/is-emirleri', json={'plaka': '34AJN101'}, headers={'X-API-Key': 'sk_zzzz_' + 'q' * 30, 'X-Forwarded-Proto': 'https'}, environ_overrides={'REMOTE_ADDR': '10.7.7.7'})
k('muhasebe API\'sinde kilitlenen IP ajanı kilitlemez', A.app.test_client().post('/api/v1/ajan/ping', json={}, headers={'X-API-Key': KA, 'X-Forwarded-Proto': 'https'}, environ_overrides={'REMOTE_ADDR': '10.7.7.7'}).status_code == 200)

# --- kuyruk sınırı ---
c = dbx(ib); [c.execute("insert into yazdirma_isleri(olusturuldu_at,arac_id,plaka,adet,veri) values(?,?,?,?,?)", (A.now(), bb, '06AJN202', 1, 'AA==')) for _ in range(A.AJAN_SINIR)]; c.commit(); c.close()
r = post(b, f'/araclar/{bb}/yazdir', f'/arac/{bb}/qr', adet='5'); k('kuyruk dolunca 429', r.status_code == 429)

# --- hareketler ---
hr = [r_[0] for r_ in dbx(ia).execute('select cihaz from hareketler where olay like "Etiket %"')]
k('hareket kaydı: kuyruğa alındı + basıldı/BASILAMADI, ajan olayı "Yazdırma ajanı" adıyla', any('Yazdırma ajanı' in (x or '') for x in hr) and dbx(ia).execute("select count(*) from hareketler where olay like '%dükkân bilgisayarı%'").fetchone()[0] >= 3)
n0 = dbx(ia).execute('select count(*) from hareketler').fetchone()[0]
for _ in range(5): j(ajan, '/api/v1/ajan/sonraki', headers={'X-API-Key': KA})
k('boş sorgular hareketler tablosunu şişirmez', dbx(ia).execute('select count(*) from hareketler').fetchone()[0] == n0)

# --- hatalı anahtar sınırı + kapatma ---
rl = A.app.test_client()
kodlar = [rl.post('/api/v1/ajan/ping', json={}, headers={'X-API-Key': 'ya_zzzz_' + 'b' * 30, 'X-Forwarded-Proto': 'https'}, environ_overrides={'REMOTE_ADDR': '10.9.9.9'}).status_code for _ in range(12)]
k('çok hatalı anahtar denemesi 429 verir', 429 in kodlar and kodlar[0] == 401)
post(y, f'/yonetici/{ia}/ajan', '/yonetici', eylem='kapat')
k('ajan kapatılınca anahtar çalışmaz, düğme kalkar', j(ajan, '/api/v1/ajan/ping', headers={'X-API-Key': KA}).status_code == 401 and 'id="aj"' not in get(a, f'/arac/{aa}/qr').get_data(as_text=True))
post(y, f'/yonetici/{ia}/ajan', '/yonetici', eylem='uret'); r = post(y, f'/yonetici/{ia}/ajan', '/yonetici', eylem='uret'); KA2 = re.search(r'Ajan anahtarı: <b[^>]*>([^<]+)</b>', r.get_data(as_text=True)).group(1)
k('anahtar yenilenince eskisi geçersiz', j(ajan, '/api/v1/ajan/ping', headers={'X-API-Key': KA}).status_code == 401 and j(ajan, '/api/v1/ajan/ping', headers={'X-API-Key': KA2}).status_code == 200)
post(y, f'/yonetici/{ia}/durum', '/yonetici')
k('kapatılan dükkânın ajanı çalışmaz', j(ajan, '/api/v1/ajan/ping', headers={'X-API-Key': KA2}).status_code == 401)
post(y, f'/yonetici/{ia}/durum', '/yonetici'); a = giris('ahmet-oto', 'Ahmet-Sifre-1')      # kapatma oturumları düşürür

# --- ajan programı (gerçek HTTP sunucusuyla) ---
sys.path.insert(0, 'yazdirma_ajani'); import yazdirma_ajani as AJ
def bos_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
from waitress import create_server
P = bos_port(); srv = create_server(A.app, host='127.0.0.1', port=P); threading.Thread(target=srv.run, daemon=True).start(); time.sleep(0.5)
ist = AJ.Istemci(f'http://127.0.0.1:{P}', KA2)
alinan = []
def sahte(bayt): alinan.append(bayt); return True, 'Etiket yazıcıya gönderildi.'
os.environ['ENTEGRASYON_HTTPS_ZORUNLU'] = '0'; A.ENT_HTTPS_ZORUNLU = False
k('ajan: iş yokken "bos"', AJ.bir_tur(ist, sahte) == 'bos' and not alinan)
I5 = post(a, f'/araclar/{aa}/yazdir', f'/arac/{aa}/qr', adet='3').get_json()['is_id']
k('ajan: işi alır, yazıcıya gönderir, sonucu bildirir', AJ.bir_tur(ist, sahte) == 'is' and len(alinan) == 1 and alinan[0].rstrip().endswith(b'PRINT 1,3') and get(a, f'/yazdirma/{I5}/durum').get_json()['durum'] == 'basildi')
I6 = post(a, f'/araclar/{aa}/yazdir', f'/arac/{aa}/qr', adet='1').get_json()['is_id']
AJ.bir_tur(ist, lambda b: (False, 'Yazıcı çevrimdışı.')); r = get(a, f'/yazdirma/{I6}/durum').get_json()
k('ajan: yazıcı hatası sunucuya iletilir', r['durum'] == 'hata' and 'çevrimdışı' in r['mesaj'])
I7 = post(a, f'/araclar/{aa}/yazdir', f'/arac/{aa}/qr', adet='1').get_json()['is_id']
def patla(b): raise RuntimeError('boom')
AJ.bir_tur(ist, patla); k('ajan: gönderme istisnası da hata olarak bildirilir', get(a, f'/yazdirma/{I7}/durum').get_json()['durum'] == 'hata')
try: AJ.bir_tur(AJ.Istemci(f'http://127.0.0.1:{P}', 'ya_zzzz_' + 'c' * 30), sahte); yanlis = False
except AJ.AnahtarHatasi: yanlis = True
k('ajan: yanlış anahtar AnahtarHatasi (yerel PermissionError ile karışmaz)', yanlis and not issubclass(AJ.AnahtarHatasi, OSError))
try: AJ.bir_tur(AJ.Istemci(f'http://127.0.0.1:{bos_port()}', KA2), sahte); kopuk = False
except OSError: kopuk = True
k('ajan: sunucu yoksa OSError (tekrar denenir)', kopuk)
class Sahte:        # sonuç bildirimi 503 -> 200: yeniden denenir, iş kaybolmaz
    def __init__(s, yanitlar): s.y = list(yanitlar); s.cagri = []
    sunucu = 'https://x.example.com'
    def istek(s, yol, govde=None):
        s.cagri.append(yol)
        if yol.endswith('/sonraki'): return 200, {'ok': True, 'is': {'id': 5, 'plaka': 'X', 'adet': 1, 'veri': base64.b64encode(b'PRINT 1,1').decode()}}
        return s.y.pop(0)
AJ.time.sleep = lambda *_: None
sh = Sahte([(503, {}), (429, {}), (200, {'ok': True})]); AJ.bir_tur(sh, sahte)
k('ajan: sonuç bildirimi 503/429 alınca yeniden dener, 200 ile biter', sh.cagri.count('/api/v1/ajan/sonuc') == 3)
sh = Sahte([(404, {})]); AJ.bir_tur(sh, sahte); k('ajan: kalıcı red (404) tekrar denenmez', sh.cagri.count('/api/v1/ajan/sonuc') == 1)
for kotu in ('http://localhost.evil.com', 'http://127.0.0.1.evil.com', 'https://user:pw@x.example.com', 'https://x.example.com/?a=1'):
    try: AJ.adres_kontrol(kotu); gecti = True
    except ValueError: gecti = False
    k('ajan: sahte yerel/kötü adres reddedilir ' + kotu, not gecti)
k('ajan: gerçek yerel adres serbest', AJ.adres_kontrol('http://localhost:5000') == 'http://localhost:5000')
k('ajan: yönlendirme izlenmez', AJ._YonlendirmeYok().redirect_request(None, None, 302, 'x', {}, 'http://evil') is None)
k('ajan: https zorunlu (yerel hariç)', all(_t for _t in [AJ.adres_kontrol('https://servis.ornek.com/') == 'https://servis.ornek.com', AJ.adres_kontrol('http://127.0.0.1:5000') == 'http://127.0.0.1:5000']))
for kotu in ('http://servis.ornek.com', 'servis.ornek.com', 'ftp://x.example.com', ''):
    try: AJ.adres_kontrol(kotu); gecti = True
    except ValueError: gecti = False
    k('ajan: kötü adres reddedilir ' + kotu, not gecti)
dosya = tempfile.mkdtemp() + '/ajan.env'; open(dosya, 'w', encoding='utf-8').write('# yorum\nSUNUCU = https://x.example.com # not\nANAHTAR="ya_abcd_123"\nETIKET_YAZICI_ADI=Zebra\n')
cfg = AJ.ayar_oku(dosya); k('ajan.env okunur, yorum/tırnak temizlenir, ETIKET_* ortama geçer', cfg['SUNUCU'] == 'https://x.example.com' and cfg['ANAHTAR'] == 'ya_abcd_123' and os.environ.get('ETIKET_YAZICI_ADI') == 'Zebra')
k('ajan: deneme etiketi geçerli TSPL', AJ.DENEME_TSPL.startswith(b'\r\nSIZE 58 mm,40 mm') and AJ.DENEME_TSPL.rstrip().endswith(b'PRINT 1,1'))
srv.close()
print(f'{ok} geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
