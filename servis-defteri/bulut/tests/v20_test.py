import os as _os; _os.environ['APP_PASSWORD_HASH']='pbkdf2_sha256$600000$0123456789abcdef0123456789abcdef$bc43d8da4a5cfd47df54d15115d65eafe20121e09ab04ca54ddf8dd8397d4335'   # test şifresi: TestSifre-12345!
# V20: QR sayfasından iş emri aç, servis kaydı düzenleme, geri dönüş, çoklu geliş testleri
import os,re,sys,shutil,tempfile
d=tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),d+'/a',ignore=shutil.ignore_patterns('data','__pycache__')); os.chdir(d+'/a'); sys.path.insert(0,'.')
import app as A; A.app.config['CIHAZ_KAPISI'] = False      # bu testler cihaz adı kapısını sınamaz; kapı hareket_test.py'de sınanır
_i,_=A.dukkan_olustur('test','Test Servis','0555 000 00 00',sifre='TestSifre-12345!',gecici=False); A.DB_PATH=A.db_yolu(_i); A.BACKUP_DIR=A.yedek_dizin(_i)
ok=0;fail=0
def k(ad,c):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print('BAŞARISIZ:',ad)
R={'REMOTE_ADDR':'127.0.0.1'}
def tok(c,yol='/login'): return re.search(r'name="csrf_token" value="([^"]+)"',c.get(yol,environ_overrides=R).get_data(as_text=True)).group(1)
a=A.app.test_client(); a.post('/login',data={'csrf_token':tok(a),'kullanici':'test','sifre':'TestSifre-12345!'},environ_overrides=R)
def P(url,**v): v['csrf_token']=tok(a,'/panel'); return a.post(url,data=v,environ_overrides=R)
P('/is-emirleri/hizli',plaka='35ABC123',musteri_ad='ali veli',telefon='0532 111 22 33',gelis_nedeni='Yağ değişimi',giris_km='100000')
db=A.sqlite3.connect(A.DB_PATH); db.row_factory=A.sqlite3.Row
ar=db.execute('select id,qr_token from araclar').fetchone(); qt=ar['qr_token']; aid=ar['id']
i1=db.execute('select id from is_emirleri').fetchone()[0]
anon=A.app.test_client()
# usta, açık iş emri var -> "Açık İş Emri"
h=a.get('/arac/'+qt,environ_overrides=R).get_data(as_text=True)
k('usta: tek buton "Yeni İş Emri Aç" (açık iş emri olsa da)','Yeni İş Emri Aç' in h and 'Açık İş Emri' not in h)
k('usta: kayıt Düzenle bağlantısı','✏️ Düzenle' in h)
k('usta: ara ve haber et yanında',('Müşteriyi Ara' in h) and ('Haber Et' in h))
# anonim: hiçbiri yok
h2=anon.get('/arac/'+qt,environ_overrides=R).get_data(as_text=True)
k('anonim: buton/düzenle yok','İş Emri' not in h2 and 'Düzenle' not in h2 and '/is-emirleri/' not in h2 and 'class="alt"' not in h2)
# teslim et -> açık yok -> "İş Emri Aç"
P(f'/is-emirleri/durum/{i1}',durum='Tamamlandı')
h=a.get('/arac/'+qt,environ_overrides=R).get_data(as_text=True)
m=re.search(r'href="([^"]+)">➕<br>Yeni İş Emri Aç',h); k('usta: Yeni İş Emri Aç butonu',bool(m))
k('buton plakayı taşır','yeni=35ABC123' in m.group(1) if m else False)
f=a.get(m.group(1).split('#')[0],environ_overrides=R).get_data(as_text=True)
k('form plaka dolu geldi','value="35 ABC 123"' in f or 'value="35ABC123"' in f)
# ikinci geliş
P('/is-emirleri/hizli',plaka='35 ABC 123',gelis_nedeni='Fren balatası',giris_km='105000')
rows=db.execute('select id,gelis_nedeni,giris_km from is_emirleri order by id').fetchall()
k('iki ayrı geliş kaydı',len(rows)==2 and rows[0]['gelis_nedeni']=='Yağ değişimi' and rows[1]['giris_km']==105000)
i2=rows[1]['id']
# düzenleme: ikinci gelişin tarihi + işlem değişir, birincisi değişmez
r=P(f'/is-emirleri/duzenle/{i2}?geri=/arac/{qt}',arac_id=aid,gelis_at='2026-10-05T10:30',gidis_at='',giris_km='105500',durum='Devam Ediyor',gelis_nedeni='Fren balatası',yapilan_islem='Balata değişti',notlar='',geri='/arac/'+qt)
k('kayıttan sonra QR sayfasına döner',r.status_code==302 and r.headers['Location'].endswith('/arac/'+qt))
db2=A.sqlite3.connect(A.DB_PATH); db2.row_factory=A.sqlite3.Row
x=db2.execute('select gelis_at,giris_km,yapilan_islem from is_emirleri where id=?',(i2,)).fetchone()
y=db2.execute('select gelis_nedeni,giris_km,durum from is_emirleri where id=?',(i1,)).fetchone()
k('ikinci geliş güncellendi',x['gelis_at'].startswith('2026-10-05 10:30') and x['giris_km']==105500 and x['yapilan_islem']=='Balata değişti')
k('ilk geliş aynı kaldı',y['gelis_nedeni']=='Yağ değişimi' and y['giris_km']==100000 and y['durum']=='Tamamlandı')
# açık yönlendirme engeli
r=P(f'/is-emirleri/duzenle/{i2}?geri=//evil.com',arac_id=aid,gelis_at='2026-10-05T10:30',gidis_at='',giris_km='1',durum='Devam Ediyor',gelis_nedeni='x',yapilan_islem='',notlar='',geri='//evil.com')
k('dış adrese yönlendirme yok','evil' not in r.headers['Location'])
r=P(f'/is-emirleri/duzenle/{i2}',arac_id=aid,gelis_at='2026-10-05T10:30',gidis_at='',giris_km='1',durum='Devam Ediyor',gelis_nedeni='x',yapilan_islem='',notlar='',geri='/arac/x/../..')
k('geri parametresi normal sayfaya düşer or güvenli','evil' not in r.headers['Location'])
# anonim düzenleyemez
k('anonim düzenleyemez',anon.get(f'/is-emirleri/duzenle/{i2}',environ_overrides=R).status_code in (302,401,403))
# araç düzenle ekranı: iki geliş listelenir
h=a.get(f'/araclar/duzenle/{aid}',environ_overrides=R).get_data(as_text=True)
k('araç ekranında 2 servis kaydı','Servis kayıtları' in h and f'duzenle/{i1}' in h and f'duzenle/{i2}' in h)
k('geliş tarihleri görünür','05.10.2026 10:30' in h)
# düzenleme ekranında Vazgeç
h=a.get(f'/is-emirleri/duzenle/{i2}?geri=/arac/{qt}',environ_overrides=R).get_data(as_text=True)
k('vazgeç QR sayfasına','href="/arac/'+qt+'"' in h)
# --- Ne yapılacak: sık kullanılanlar + özel işlem ---
h=a.get('/is-emirleri',environ_overrides=R).get_data(as_text=True)
sik=re.search(r'class="sik-serit[^>]*>(.*?)</div>',h,re.S).group(1)
k('sık şeridi var, 8 düğme',sik.count('data-chip=')==8)
k('geçmişte yapılan işlem şeritte (Yağ değişimi/Fren balatası)','Yağ değişimi' in sik and 'Fren balatası' in sik)
k('kategoriler kapalı gelir, dokununca açılır',h.count('<details class="mt-2 kat">')==len(A.ISLEM_KATEGORILERI) and 'ozel-kat' in h)
def api(ad): 
    return a.post('/api/islem-ekle',json={'ad':ad},headers={'X-CSRF-Token':tok(a,'/panel')},environ_overrides=R)
r=api('lpg tank değişimi'); j=r.get_json(); k('özel işlem eklendi',r.status_code==200 and j['ok'] and j['yeni'] and j['ad']=='Lpg tank değişimi')
r=api('lpg TANK değişimi'); k('aynı işlem tekrar eklenmez',not r.get_json()['yeni'])
r=api('yağ değişimi'); k('katalogdakini yenisi saymaz, doğru yazımı döner',(not r.get_json()['yeni']) and r.get_json()['ad']=='Yağ değişimi')
k('çok kısa reddedilir',api('a').status_code==400)
n_ozel=db2.execute('select count(*) from ozel_islem').fetchone()[0]; k('veritabanında 1 özel işlem',n_ozel==1)
h=a.get('/is-emirleri',environ_overrides=R).get_data(as_text=True)
k('özel işlem formda görünür','data-chip="Lpg tank değişimi"' in h and 'Eklediklerim' in h)
k('API oturumsuz 401',anon.post('/api/islem-ekle',json={'ad':'xx'},environ_overrides=R).status_code in (401,400,403))
# en çok yapılan öne geçer
for _ in range(3): P('/is-emirleri/hizli',plaka='35ABC123',gelis_nedeni='Akü',giris_km='106000')
sik=re.search(r'class="sik-serit[^>]*>(.*?)</div>',a.get('/is-emirleri',environ_overrides=R).get_data(as_text=True),re.S).group(1)
k('en çok yapılan (Akü) şeridin başında',sik.index('data-chip="Akü"')<sik.index('data-chip="Yağ değişimi"'))
# --- düzenleme sayfasında da aynı seçici ---
h=a.get(f'/is-emirleri/duzenle/{i2}',environ_overrides=R).get_data(as_text=True)
k('düzenleme: tek seçici (geliş nedeni) + yapılan işlem yazı kutusu',h.count('class="islem-secici"')==1 and 'id="gelis_nedeni"' in h and '<input class="form-control" id="yapilan_islem"' in h)
k('düzenleme: kategoriler kapalı, sık şerit var',h.count('<details class="mt-2 kat">')==len(A.ISLEM_KATEGORILERI) and h.count('class="sik-serit')==1)
k('düzenleme: ortak JS bir kez yüklü',h.count('data-islem-secici]')==1)
k('düzenleme: Eklediklerim görünür','data-chip="Lpg tank değişimi"' in h)
k('düzenleme: mevcut değer kutuda (son kayıt gelis_nedeni=x)','id="gelis_nedeni" name="gelis_nedeni" class="form-control form-control-lg is-input" value="x"' in h)
r=P(f'/is-emirleri/duzenle/{i2}',arac_id=aid,gelis_at='2026-10-05T10:30',gidis_at='',giris_km='105500',durum='Devam Ediyor',gelis_nedeni='Fren balatası, Fren diski',yapilan_islem='Fren balatası, Fren diski, Rot balans',notlar='',geri='')
x=A.sqlite3.connect(A.DB_PATH).execute('select gelis_nedeni,yapilan_islem,1 from is_emirleri where id=?',(i2,)).fetchone()
k('düzenleme kaydı çok seçimle çalışır',x[0]=='Fren balatası, Fren diski' and x[1].endswith('Rot balans'))
q=anon.get('/arac/'+qt,environ_overrides=R).get_data(as_text=True)
k('QR sayfasında her işlem ayrı etiket','>Rot balans<' in q and '>Fren diski<' in q)
# --- sayfa tutarlılığı ---
mid=db2.execute('select musteri_id from araclar where id=?',(aid,)).fetchone()[0]
h=a.get(f'/musteriler/duzenle/{mid}',environ_overrides=R).get_data(as_text=True)
k('müşteri düzenle: etiketler',all(x in h for x in ['>Ad soyad<','>Telefon<','>E-posta<','>Adres<','>Not<']) and '👤 Müşteri Düzenle' in h)
k('müşteri düzenle: Kaydet + Vazgeç','btn-lg flex-fill">Kaydet' in h and 'Vazgeç' in h)
r=P(f'/musteriler/duzenle/{mid}',ad_soyad='ali veli',telefon='0532 111 22 33',eposta='a@b.com',adres='Örnek Mah.',notlar='iyi müşteri')
y=A.sqlite3.connect(A.DB_PATH).execute('select ad_soyad,adres,notlar,eposta from musteriler where id=?',(mid,)).fetchone()
k('müşteri düzenle: kayıt çalışır',r.status_code==302 and y==('ALİ VELİ','Örnek Mah.','iyi müşteri','a@b.com'))
h=a.get(f'/araclar/duzenle/{aid}',environ_overrides=R).get_data(as_text=True)
k('araç düzenle: emoji başlık + Not etiketi + büyük Kaydet','🚗 Araç Düzenle' in h and '>Not<' in h and 'btn-lg flex-fill">Kaydet' in h)
h=a.get(f'/is-emirleri/duzenle/{i2}',environ_overrides=R).get_data(as_text=True)
k('iş emri düzenle: emoji başlık + etiketler + büyük Kaydet','📋 İş Emri Düzenle' in h and '>Not<' in h and '>Araç<' in h and 'btn-lg flex-fill">Kaydet' in h)
t=a.get('/araclar',environ_overrides=R).get_data(as_text=True)+a.get('/ara?q=35',environ_overrides=R).get_data(as_text=True)+a.get('/is-emirleri',environ_overrides=R).get_data(as_text=True)
k('yazım birleşik: "İş Emri Aç" her yerde, eski yazımlar yok','İş Emri Aç' in t and 'İş emri aç' not in t and 'İş Emrini Aç' not in t)
# --- inceleme düzeltmeleri ---
k('eski etiket.png adresi kaldırıldı',a.get(f'/araclar/{aid}/etiket.png',environ_overrides=R).status_code==404)
k('eski PNG üretici kodu yok',not hasattr(A,'etiket_png') and not hasattr(A,'ETIKET_BOYUTLAR'))
for _ in range(32): P('/is-emirleri/hizli',plaka='35ABC123',gelis_nedeni='Kontrol',giris_km='107000')
toplam=db2.execute('select count(*) from is_emirleri where arac_id=?',(aid,)).fetchone()[0]
h=anon.get('/arac/'+qt,environ_overrides=R).get_data(as_text=True)
k('QR: 30 sınırı yok, gerçek toplam yazıyor',toplam>30 and f'{toplam} kayıt' in h and h.count('class="k"')==toplam)
k('QR anonim: telefon sayfada yok','0532 111 22 33' not in h and '05321112233' not in h and 'tel:+90532' not in h)
h=a.get('/arac/'+qt,environ_overrides=R).get_data(as_text=True)
k('QR usta: telefon düğmeleri hâlâ var','tel:' in h and 'wa.me' in h)
# eklenen işlemi silme
def sil(ad): return a.post('/api/islem-sil',json={'ad':ad},headers={'X-CSRF-Token':tok(a,'/panel')},environ_overrides=R)
h=a.get('/is-emirleri',environ_overrides=R).get_data(as_text=True)
k('Listemi düzenle düğmesi var','ozel-duzenle' in h)
r=sil('lpg TANK değişimi'); k('eklenen işlem silinir',r.status_code==200 and r.get_json()['silindi'])
h=a.get('/is-emirleri',environ_overrides=R).get_data(as_text=True)
k('silinen işlem formda yok','data-chip="Lpg tank değişimi"' not in h)
k('silinen işlem yeniden eklenebilir',api('lpg tank değişimi').get_json()['yeni'])
k('katalogdaki işlem silinemez (kayıt yok)',sil('Yağ değişimi').get_json()['silindi'] is False and 'data-chip="Yağ değişimi"' in a.get('/is-emirleri',environ_overrides=R).get_data(as_text=True))
k('silme oturumsuz reddedilir',anon.post('/api/islem-sil',json={'ad':'x'},environ_overrides=R).status_code in (401,400,403))
print(f'{ok} kontrol geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
