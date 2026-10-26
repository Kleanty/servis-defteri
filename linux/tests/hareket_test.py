import os as _os; _os.environ['APP_PASSWORD_HASH']='pbkdf2_sha256$600000$0123456789abcdef0123456789abcdef$bc43d8da4a5cfd47df54d15115d65eafe20121e09ab04ca54ddf8dd8397d4335'; _os.environ['ENTEGRASYON_API_ANAHTARI']='test-anahtar-123'   # test şifresi: TestSifre-12345!
# Cihaz adı kapısı ve hareket kaydı: ilk girişte ad zorunlu, aynı ad serbest, kart 400 gün, kayıtlar kişi bilgisi içermez, 180 gün sonra silinir.
import os,re,sys,shutil,tempfile,sqlite3
from datetime import datetime,timedelta
d=tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),d+'/a',ignore=shutil.ignore_patterns('data','__pycache__')); os.chdir(d+'/a'); sys.path.insert(0,'.')
import app as A          # NOT: CIHAZ_KAPISI burada AÇIK (varsayılan)
ok=0;fail=0
def k(ad,c):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print('BAŞARISIZ:',ad)
R={'REMOTE_ADDR':'127.0.0.1'}
def csrf(c):
    for y in ('/panel','/cihaz-adi'):
        m=re.search(r'name="csrf_token" value="([^"]+)"',c.get(y,environ_overrides=R,follow_redirects=True).get_data(as_text=True))
        if m: return m.group(1)
def yeni_istemci():
    c=A.app.test_client(); t=re.search(r'name="csrf_token" value="([^"]+)"',c.get('/login',environ_overrides=R).get_data(as_text=True)).group(1)
    c.post('/login',data={'csrf_token':t,'sifre':'TestSifre-12345!'},environ_overrides=R); return c
def P(c,url,**v): v['csrf_token']=csrf(c); return c.post(url,data=v,environ_overrides=R)
def db(): return sqlite3.connect(A.DB_PATH)
def ad_ver(c,ad,**ek): return P(c,'/cihaz-adi',ad=ad,**ek)

# --- kapı ---
a=yeni_istemci()
r=a.get('/panel',environ_overrides=R); k('adsız cihaz /panel yerine ad sayfasına yönlenir',r.status_code==302 and '/cihaz-adi' in r.headers['Location'])
r=a.get('/is-emirleri',environ_overrides=R); k('gidilen sayfa geri parametresiyle hatırlanır',r.status_code==302 and 'geri=' in r.headers['Location'] and 'is-emirleri' in r.headers['Location'])
h=a.get('/cihaz-adi',environ_overrides=R).get_data(as_text=True); k('ad sayfası: giriş kutusu ve hazır adlar',('name="ad"' in h) and ('Usta telefonu' in h) and ('Ofis bilgisayarı' in h))
P(a,'/cihaz-adi',ad='x'); k('1 karakterlik ad reddedilir (hâlâ adsız)',a.get('/panel',environ_overrides=R).status_code==302 and db().execute('select count(*) from cihazlar').fetchone()[0]==0)
r=P(a,'/is-emirleri/hizli',plaka='34TST111',giris_km='1000',gelis_nedeni='Bakım'); k('adsız cihaz POST ile iş emri açamaz',r.status_code==302 and '/cihaz-adi' in r.headers['Location'] and db().execute('select count(*) from is_emirleri').fetchone()[0]==0)
rj=a.post('/api/islem-ekle',json={'ad':'Deneme'},headers={'X-CSRF-Token':csrf(a)},environ_overrides=R); k('adsız cihaz JSON ucuna 403 alır',rj.status_code==403)
r=P(a,'/cihaz-adi',ad='Usta telefonu',geri='//kotu.example/x'); k('ad verilince kayıt oluşur, güvensiz geri adresi yok sayılır',r.status_code==302 and 'kotu.example' not in r.headers['Location'] and db().execute("select count(*) from cihazlar where ad='Usta telefonu'").fetchone()[0]==1)
sc=[x for x in r.headers.getlist('Set-Cookie') if x.startswith('cihaz=')]
k('cihaz kartı 400 gün, HttpOnly, SameSite',bool(sc) and f'Max-Age={400*86400}' in sc[0] and 'HttpOnly' in sc[0] and 'SameSite=Lax' in sc[0])
k('ad verince panel açılır',a.get('/panel',environ_overrides=R).status_code==200)
k('adı olan cihaz /cihaz-adi\'den panele döner',a.get('/cihaz-adi',environ_overrides=R).status_code==302)

# --- aynı ad serbest, kodlar farklı ---
b=yeni_istemci(); ad_ver(b,'Usta telefonu')
s=db().execute("select count(*),count(distinct kod) from cihazlar where ad='Usta telefonu'").fetchone(); k('aynı ad ikinci cihaza verilebilir (kodlar farklı)',s==(2,2))

# --- çıkış / yeniden giriş ad sormaz ---
P(a,'/logout'); t=re.search(r'name="csrf_token" value="([^"]+)"',a.get('/login',environ_overrides=R).get_data(as_text=True)).group(1)
a.post('/login',data={'csrf_token':t,'sifre':'TestSifre-12345!'},environ_overrides=R); k('çıkış-giriş sonrası ad yeniden sorulmaz',a.get('/panel',environ_overrides=R).status_code==200)
k('bozuk/sahte cihaz kartı kabul edilmez',(lambda c:(c.set_cookie('cihaz','sahte-deger'),c.get('/panel',environ_overrides=R).status_code)[1])(yeni_istemci())==302)

# --- hareketler ---
P(a,'/is-emirleri/hizli',plaka='34TST111',giris_km='1000',gelis_nedeni='Bakım',musteri_ad='Gizli Kisi',telefon='0555 111 22 33')
P(a,'/musteriler/ekle',ad_soyad='Ali Veli',telefon='0555 999 88 77')
cid=db().execute("select id,kod from cihazlar where ad='Usta telefonu' order by id").fetchone()
satir=db().execute("select cihaz,olay from hareketler").fetchall(); olaylar=' | '.join(x[1] for x in satir)
k('yeni iş emri kaydı: cihaz adı + kod ile',any(x[1].startswith('İş emri açıldı: 34 TST 111') and x[0]==f'Usta telefonu · #{cid[1]}' for x in satir))
k('müşteri ekleme kaydı',any(x[1]=='Müşteri eklendi' for x in satir))
k('giriş ve çıkış kayıtlı',any(x[1]=='Giriş başarılı' for x in satir) and any(x[1]=='Çıkış' for x in satir))
k('hareket kaydında telefon ve müşteri adı YOK',all(z not in olaylar for z in ('0555','Gizli','Ali Veli')))
g1=a.get('/hareketler',environ_overrides=R); h=g1.get_data(as_text=True)
k('hareketler sayfası açılır, cihaz ve olay görünür',g1.status_code==200 and 'Usta telefonu' in h and 'İş emri açıldı' in h and 'Bu cihaz' in h)
k('cihaza göre süzme',a.get(f'/hareketler?cihaz={cid[0]}',environ_overrides=R).status_code==200)
k('İstatistik sayfasında Hareketler düğmesi',"/hareketler" in a.get('/istatistik',environ_overrides=R).get_data(as_text=True))
k('üst çubuğa yeni düğme eklenmedi',"/hareketler" not in a.get('/panel',environ_overrides=R).get_data(as_text=True).split('</nav>')[0])
k('girişsiz /hareketler giriş ister',A.app.test_client().get('/hareketler',environ_overrides=R).status_code==302)

# --- saldırı denemeleri veritabanına yazılmaz; API olayı 'Dış sistem (API)' ---
n0=db().execute('select count(*) from hareketler').fetchone()[0]
api=A.app.test_client(); H={'X-API-Key':'test-anahtar-123','X-Forwarded-Proto':'https'}
api.post('/api/v1/is-emirleri',json={'plaka':'35ABC123','kayit_no':'Y1'},headers={'X-API-Key':'yanlis','X-Forwarded-Proto':'https'},environ_overrides=R)
c0=A.app.test_client(); c0.post('/login',data={'csrf_token':re.search(r'name="csrf_token" value="([^"]+)"',c0.get('/login',environ_overrides=R).get_data(as_text=True)).group(1),'sifre':'yanlis'},environ_overrides=R)
k('yanlış anahtar ve yanlış şifre veritabanı kaydına girmez',db().execute('select count(*) from hareketler').fetchone()[0]==n0)
api.post('/api/v1/is-emirleri',json={'plaka':'35ABC123','kayit_no':'Y2'},headers=H,environ_overrides=R)
k('API olayı "Dış sistem (API)" olarak kayıtlı',db().execute("select count(*) from hareketler where cihaz='Dış sistem (API)' and olay like 'ENTEGRASYON%'").fetchone()[0]>=1)

# --- yeniden adlandırma geçmişe de yansır ---
r=P(a,f'/hareketler/cihaz/{cid[0]}',ad='Ofis'); h=a.get('/hareketler',environ_overrides=R).get_data(as_text=True)
k('cihaz yeniden adlandırılır, eski kayıtlar da yeni adla görünür',r.status_code==302 and f'Ofis · #{cid[1]}' in h)
P(a,f'/hareketler/cihaz/{cid[0]}',ad='a'); k('geçersiz yeni ad reddedilir',db().execute('select ad from cihazlar where id=?',(cid[0],)).fetchone()[0]=='Ofis')

# --- 180 gün sonra silinir ---
eski=(datetime.now()-timedelta(days=181)).strftime('%Y-%m-%d %H:%M:%S'); yeni=(datetime.now()-timedelta(days=179)).strftime('%Y-%m-%d %H:%M:%S')
con=db(); con.execute("insert into hareketler(zaman,cihaz,ip,olay) values(?,?,?,?)",(eski,'x','1.1.1.1','ESKI-181')); con.execute("insert into hareketler(zaman,cihaz,ip,olay) values(?,?,?,?)",(yeni,'x','1.1.1.1','YENI-179')); con.commit(); con.close()
A._hareket_temizlendi.clear(); P(a,'/musteriler/ekle',ad_soyad='Temizlik Tetik')
k('181 günlük kayıt silinir, 179 günlük kalır',db().execute("select count(*) from hareketler where olay='ESKI-181'").fetchone()[0]==0 and db().execute("select count(*) from hareketler where olay='YENI-179'").fetchone()[0]==1)

# --- kart ömrü yenilenir ---
con=db(); con.execute("update cihazlar set son_gorulme_at='2000-01-01 00:00:00' where id=?",(cid[0],)); con.commit(); con.close()
r=a.get('/panel',environ_overrides=R); sc=[x for x in r.headers.getlist('Set-Cookie') if x.startswith('cihaz=')]
k('günde bir kart ömrü yenilenir ve son görülme güncellenir',bool(sc) and db().execute('select son_gorulme_at from cihazlar where id=?',(cid[0],)).fetchone()[0][:4]==str(datetime.now().year))

# --- sağlamlaştırma ---
k('?s= çok büyük sayı 500 vermez', a.get('/hareketler?s=99999999999999999999',environ_overrides=R).status_code==200)
tok_a=a.get_cookie('cihaz').value
con=db(); con.execute("update cihazlar set kod='ZZZZ' where id=?",(cid[0],)); con.commit(); con.close()
k('cihaz kodu değişince (veritabanı geri yüklendi) eski kart geçersiz olur', a.get('/panel',environ_overrides=R).status_code==302)
con=db(); con.execute("update cihazlar set kod=? where id=?",(cid[1],cid[0])); con.commit(); con.close()
k('kod geri gelince kart yine geçerli', a.get('/panel',environ_overrides=R).status_code==200)
eski2=(datetime.now()-timedelta(days=200)).strftime('%Y-%m-%d %H:%M:%S')
con=db(); con.execute("insert into cihazlar(ad,kod,olusturuldu_at,son_gorulme_at) values('Eski','ABCD',?,?)",(eski2,eski2)); con.commit(); con.close()
A._hareket_temizlendi.clear(); P(a,'/musteriler/ekle',ad_soyad='Temizlik 2')
k('180 gündür görünmeyen ve kaydı olmayan cihaz silinir, kayıtlı olan kalır', db().execute("select count(*) from cihazlar where ad='Eski'").fetchone()[0]==0 and db().execute('select count(*) from cihazlar where id=?',(cid[0],)).fetchone()[0]==1)
P(a,'/cikis-hepsi'); k('"tüm cihazlardan çıkış" olayı cihaz adıyla kaydedilir', db().execute("select count(*) from hareketler where olay='TÜM CİHAZLARDAN ÇIKIŞ' and cihaz like 'Ofis%'").fetchone()[0]==1)

# --- herkese açık sayfalar kapıdan etkilenmez ---
tok_=db().execute('select qr_token from araclar limit 1').fetchone()[0]
k('müşteri QR sayfası adsız, girişsiz açılır',A.app.test_client().get('/arac/'+tok_,environ_overrides=R).status_code==200 and A.app.test_client().get('/',environ_overrides=R).status_code==200)
print(f'{ok} geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
