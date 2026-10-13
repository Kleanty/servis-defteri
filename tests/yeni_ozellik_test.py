import os as _os; _os.environ['APP_PASSWORD_HASH']='pbkdf2_sha256$600000$0123456789abcdef0123456789abcdef$bc43d8da4a5cfd47df54d15115d65eafe20121e09ab04ca54ddf8dd8397d4335'   # test şifresi: TestSifre-12345!
# Yedek göstergesi, çöp kutusu, tüm cihazlardan çıkış testleri (izole geçici kopyada)
import os,re,sys,shutil,tempfile,time
d=tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),d+'/a',ignore=shutil.ignore_patterns('data','__pycache__')); os.chdir(d+'/a'); sys.path.insert(0,'.')
import app as A
ok=0;fail=0
def k(ad,c):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print('BAŞARISIZ:',ad)
R={'REMOTE_ADDR':'127.0.0.1'}
def yeni(): 
    c=A.app.test_client(); return c
def tok(c,yol='/login'): return re.search(r'name="csrf_token" value="([^"]+)"',c.get(yol,environ_overrides=R).get_data(as_text=True)).group(1)
def giris(c):
    x=tok(c); c.post('/login',data={'csrf_token':x,'sifre':'TestSifre-12345!'},environ_overrides=R)
def P(c,url,**v): 
    v['csrf_token']=tok(c,'/panel'); return c.post(url,data=v,environ_overrides=R)
a=yeni(); giris(a); b=yeni(); giris(b)
k('iki cihaz da girişli',a.get('/panel',environ_overrides=R).status_code==200 and b.get('/panel',environ_overrides=R).status_code==200)
h=a.get('/panel',environ_overrides=R).get_data(as_text=True)
k('yedek yok -> uyarı',('Henüz hiç yedek' in h))
os.makedirs(A.BACKUP_DIR,exist_ok=True); f=os.path.join(A.BACKUP_DIR,'servis_x.db'); open(f,'w').close()
h=a.get('/panel',environ_overrides=R).get_data(as_text=True); k('taze yedek -> "az önce", uyarı yok','Son yedek: az önce' in h and 'Yedekleme çalışmıyor' not in h)
os.utime(f,(time.time()-5*3600,)*2); h=a.get('/panel',environ_overrides=R).get_data(as_text=True); k('5 saat önce yazılır','Son yedek: 5 saat önce' in h and 'Yedekleme çalışmıyor' not in h)
os.utime(f,(time.time()-3*86400,)*2); h=a.get('/panel',environ_overrides=R).get_data(as_text=True); k('3 gün -> kırmızı uyarı','3 gün önce' in h and 'Yedekleme çalışmıyor' in h)
# çöp kutusu: müşteri+araç+iş emri
P(a,'/is-emirleri/hizli',plaka='35ABC123',musteri_ad='ali veli',telefon='0532 111 22 33',gelis_nedeni='Yağ değişimi')
db=A.sqlite3.connect(A.DB_PATH); db.row_factory=A.sqlite3.Row
n=lambda t:db.execute(f'select count(*) from {t}').fetchone()[0]
k('kayıt oluştu',n('is_emirleri')==1 and n('araclar')==1)
iid=db.execute('select id from is_emirleri').fetchone()[0]
P(a,f'/is-emirleri/sil/{iid}'); k('iş emri silindi',n('is_emirleri')==0 and n('cop')==1)
h=a.get('/silinenler',environ_overrides=R).get_data(as_text=True); k('silinenler listesi','35 ABC 123' in h and 'Geri getir' in h)
cid=db.execute('select id from cop').fetchone()[0]
P(a,f'/silinenler/{cid}/geri'); k('iş emri geri geldi',n('is_emirleri')==1 and n('cop')==0)
k('geri gelen kayıt aynı veri',db.execute('select gelis_nedeni,durum from is_emirleri').fetchone()[0]=='Yağ değişimi')
# iş emri + araç sil, önce araç geri getirmeye çalış sırayı bozarak
P(a,f'/is-emirleri/sil/{iid}'); aid=db.execute('select id from araclar').fetchone()[0]
P(a,f'/araclar/sil/{aid}'); k('araç silindi',n('araclar')==0 and n('cop')==2)
cop=db.execute('select id,tablo from cop order by id').fetchall(); ie=[r for r in cop if r['tablo']=='is_emirleri'][0]['id']; ar=[r for r in cop if r['tablo']=='araclar'][0]['id']
r=P(a,f'/silinenler/{ie}/geri'); k('araç yokken iş emri geri gelmez (hata verir, çökmez)',n('is_emirleri')==0 and n('cop')==2)
P(a,f'/silinenler/{ar}/geri'); P(a,f'/silinenler/{ie}/geri'); k('önce araç sonra iş emri geri gelir',n('araclar')==1 and n('is_emirleri')==1 and n('cop')==0)
k('QR token korunur',db.execute('select qr_token from araclar').fetchone()[0] is not None)
# 30 gün sonrası temizlenir
db.execute("insert into cop(tablo,kayit_id,ozet,veri,silindi_at) values('musteriler',99,'eski','{}','2020-01-01 00:00:00')"); db.commit()
a.get('/silinenler',environ_overrides=R); k('30 günden eski çöp temizlenir',db.execute("select count(*) from cop where ozet='eski'").fetchone()[0]==0)
k('geçersiz çöp id 404',P(a,'/silinenler/9999/geri').status_code==404)
k('çöp girişsiz erişilmez',yeni().get('/silinenler',environ_overrides=R).status_code==302)
# tüm cihazlardan çıkış
r=P(a,'/cikis-hepsi'); k('çıkış-hepsi yönlendirir',r.status_code==302)
k('çıkış yapan cihaz atıldı',a.get('/panel',environ_overrides=R).status_code==302)
k('DİĞER cihaz da atıldı',b.get('/panel',environ_overrides=R).status_code==302)
k('API de 401',b.get('/api/plaka/35ABC123',environ_overrides=R).status_code==401)
k('QR sayfasında usta görünümü kapandı','Müşteriyi Ara' not in b.get('/arac/'+db.execute('select qr_token from araclar').fetchone()[0],environ_overrides=R).get_data(as_text=True))
c=yeni(); giris(c); k('yeniden giriş çalışır',c.get('/panel',environ_overrides=R).status_code==200)
k('CSRF’siz çıkış-hepsi reddedilir',c.post('/cikis-hepsi',environ_overrides=R).status_code==400)
print(f'\n{ok} kontrol geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
