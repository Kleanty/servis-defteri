import os as _os; _os.environ['APP_PASSWORD_HASH']='pbkdf2_sha256$600000$0123456789abcdef0123456789abcdef$bc43d8da4a5cfd47df54d15115d65eafe20121e09ab04ca54ddf8dd8397d4335'   # test şifresi: TestSifre-12345!
# Telefondan Bluetooth etiket basımı: sunucu TSPL üretir, tarayıcı gönderir (izole geçici kopyada)
import os,re,sys,shutil,tempfile,base64
d=tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),d+'/a',ignore=shutil.ignore_patterns('data','__pycache__')); os.chdir(d+'/a'); sys.path.insert(0,'.')
import app as A
ok=0;fail=0
def k(ad,c):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print('BAŞARISIZ:',ad)
R={'REMOTE_ADDR':'127.0.0.1'}
def tok(c,yol='/login'): return re.search(r'name="csrf_token" value="([^"]+)"',c.get(yol,environ_overrides=R).get_data(as_text=True)).group(1)
a=A.app.test_client(); a.post('/login',data={'csrf_token':tok(a),'sifre':'TestSifre-12345!'},environ_overrides=R)
def P(url,**v): v['csrf_token']=tok(a,'/panel'); return a.post(url,data=v,environ_overrides=R)
P('/is-emirleri/hizli',plaka='35ABC123',musteri_ad='ali veli',telefon='0532 111 22 33',gelis_nedeni='Yağ değişimi',giris_km='100000')
db=A.sqlite3.connect(A.DB_PATH); aid=db.execute('select id from araclar').fetchone()[0]
k('girişsiz TSPL verilmez',A.app.test_client().post(f'/araclar/{aid}/tspl',environ_overrides=R).status_code in (302,400,401))
k('CSRF’siz reddedilir',a.post(f'/araclar/{aid}/tspl',environ_overrides=R).status_code==400)
r=P(f'/araclar/{aid}/tspl',adet='3'); j=r.get_json()
k('200 ve ok',r.status_code==200 and j and j['ok'])
raw=base64.b64decode(j['veri']); t=raw.decode('ascii')
k('TSPL SIZE var','SIZE 58 mm,40 mm' in t); k('QR var','QRCODE' in t); k('PRINT 1,3',t.rstrip().endswith('PRINT 1,3'))
k('plaka etikette','35' in t and 'ABC' in t and '123' in t)
k('adet sınırı 20',base64.b64decode(P(f'/araclar/{aid}/tspl',adet='999').get_json()['veri']).decode().rstrip().endswith('PRINT 1,20'))
k('bozuk adet 1',base64.b64decode(P(f'/araclar/{aid}/tspl',adet='x').get_json()['veri']).decode().rstrip().endswith('PRINT 1,1'))
k('olmayan araç 404',P('/araclar/9999/tspl').status_code==404)
h=a.get(f'/arac/{aid}/qr',environ_overrides=R).get_data(as_text=True)
k('sayfada Bluetooth düğmesi','id="bt"' in h and 'navigator.bluetooth' in h and 'requestDevice' in h)
k('USB düğmesi duruyor','id="bas"' in h)
print(f'\n{ok} kontrol geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
