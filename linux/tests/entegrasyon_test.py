import os as _os; _os.environ['APP_PASSWORD_HASH']='pbkdf2_sha256$600000$0123456789abcdef0123456789abcdef$bc43d8da4a5cfd47df54d15115d65eafe20121e09ab04ca54ddf8dd8397d4335'; _os.environ['ENTEGRASYON_API_ANAHTARI']='test-anahtar-123'   # test şifresi: TestSifre-12345!
# Dış sistem entegrasyon API'si (POST /api/v1/is-emirleri): kimlik, HTTPS, doğrulama, eşleştirme, tekrar koruması, eşleşmeyenler.
import os,re,sys,shutil,tempfile
d=tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),d+'/a',ignore=shutil.ignore_patterns('data','__pycache__')); os.chdir(d+'/a'); sys.path.insert(0,'.')
import app as A; A.app.config['CIHAZ_KAPISI'] = False      # bu testler cihaz adı kapısını sınamaz; kapı hareket_test.py'de sınanır
ok=0;fail=0
def k(ad,c):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print('BAŞARISIZ:',ad)
R={'REMOTE_ADDR':'127.0.0.1'}
H={'X-API-Key':'test-anahtar-123','X-Forwarded-Proto':'https'}
def tok(c,yol='/login'): return re.search(r'name="csrf_token" value="([^"]+)"',c.get(yol,environ_overrides=R).get_data(as_text=True)).group(1)
a=A.app.test_client(); a.post('/login',data={'csrf_token':tok(a),'sifre':'TestSifre-12345!'},environ_overrides=R)
def P(url,**v): v['csrf_token']=tok(a,'/panel'); return a.post(url,data=v,environ_overrides=R)
def db(): return A.sqlite3.connect(A.DB_PATH)
api=A.app.test_client()
def G(js,h=H): return api.post('/api/v1/is-emirleri',json=js,headers=h,environ_overrides=R)

# --- kimlik ve HTTPS ---
k('anahtarsız istek 401',G({'plaka':'35ABC123'},h={'X-Forwarded-Proto':'https'}).status_code==401)
k('yanlış anahtar 401',G({'plaka':'35ABC123'},h={'X-API-Key':'yanlis','X-Forwarded-Proto':'https'}).status_code==401)
k('Bearer anahtarı kabul (plaka kayıtsız -> 202)',G({'plaka':'35ABC123','kayit_no':'B1'},h={'Authorization':'Bearer test-anahtar-123','X-Forwarded-Proto':'https'}).status_code==202)
r=G({'plaka':'35ABC123','kayit_no':'H1'},h={'X-API-Key':'test-anahtar-123','X-Forwarded-Proto':'http'})
k('düz http reddedilir (HTTPS_REQUIRED, 400)',r.status_code==400 and r.get_json()['kod']=='HTTPS_REQUIRED')
k('Cloudflare CF-Visitor http de reddedilir',G({'plaka':'35ABC123','kayit_no':'H2'},h={'X-API-Key':'test-anahtar-123','CF-Visitor':'{"scheme":"http"}'}).status_code==400)
k('sağlık ucu açık',api.get('/api/v1/saglik',environ_overrides=R).status_code==200)
A.ENT_API_ANAHTARI=''
k('anahtar yoksa API kapalı (404)',G({'plaka':'35ABC123'}).status_code==404 and api.get('/api/v1/saglik',environ_overrides=R).status_code==404)
A.ENT_API_ANAHTARI='test-anahtar-123'
k('CSRF gerekmez (çerezsiz istemci geçti)',G({'plaka':'35ABC123','kayit_no':'B2'}).status_code in (200,202))
k('normal POST yine CSRF ister',api.post('/login',data={'sifre':'x'},environ_overrides=R).status_code==400)

# --- doğrulama ---
k('plaka zorunlu 422',G({'km':100,'kayit_no':'X'}).status_code==422)
k('geçersiz plaka 422',G({'plaka':'ABC','kayit_no':'X2'}).status_code==422)
k('özel plaka kabul',G({'plaka':'ABC','kayit_no':'X3','ozel_plaka':True}).status_code==202)
k('çok büyük km 422',G({'plaka':'35ABC123','km':'123456789','kayit_no':'X4'}).status_code==422)
k('geçersiz durum 422',G({'plaka':'35ABC123','kayit_no':'X5','durum':'Bitti'}).status_code==422)
k('geçersiz tarih 422',G({'plaka':'35ABC123','kayit_no':'X6','gelis_zamani':'dün'}).status_code==422)
k('hatalı istekler hata tablosuna yazıldı',db().execute('select count(*) from entegrasyon_hata').fetchone()[0]>=5)

# --- eşleştirme ---
P('/is-emirleri/hizli',plaka='34XYZ111',giris_km='100000',gelis_nedeni='Yağ değişimi')
k('ilk kayıt: yapılan işlem yazılır',G({'plaka':'34XYZ111','km':100000,'kayit_no':'E0','yapilan_islem':'Yağ'}).status_code==200)
r=G({'plaka':'34 XYZ 111','km':100010,'kayit_no':'E1','yapilan_islem':['Yağ','Filtre'],'not':'müşteri bekliyor','eposta':'a@b.co','marka':'Fiat','model':'Egea'})
j=r.get_json(); k('tek açık iş emri eşleşir 200',r.status_code==200 and j['durum']=='eslesti' and j['is_emri_id'])
c=db(); x=c.execute('select yapilan_islem,notlar,durum from is_emirleri where id=?',(j['is_emri_id'],)).fetchone()
k('yapılan işlem yenisiyle değişti, eskisi notta "Önceki işlem"',x and x[0]=='Yağ, Filtre' and 'Önceki işlem: Yağ' in x[1] and 'müşteri bekliyor' in x[1])
k('boş müşteri/araç alanları tamamlandı',c.execute("select a.marka,a.model,m.eposta from araclar a join musteriler m on m.id=a.musteri_id where a.plaka='34XYZ111'").fetchone()==('Fiat','Egea','a@b.co'))
k('yeni iş emri AÇILMADI',c.execute('select count(*) from is_emirleri').fetchone()[0]==1)
ayni={'plaka':'34XYZ111','km':100010,'kayit_no':'E1','yapilan_islem':['Yağ','Filtre'],'not':'müşteri bekliyor','eposta':'a@b.co','marka':'Fiat','model':'Egea'}
r2=G(ayni); k('aynı kayit_no aynı içerik: tekrar=true 200',r2.status_code==200 and r2.get_json()['tekrar'] is True)
k('aynı kayit_no farklı içerik: 409',G(dict(ayni,**{'not':'başka'})).status_code==409)
r3=G({'plaka':'34XYZ111','km':100500,'kayit_no':'E2'})
k('km uyuşmazsa beklemeye düşer 202',r3.status_code==202 and 'Km' in r3.get_json()['neden'])
r6=G({'plaka':'34XYZ111','km':100020,'kayit_no':'E5','durum':'Tamamlandı','gidis_zamani':'2026-10-22T14:30:00+03:00'})
k('durum Tamamlandı uygulanır, gidiş yazılır',r6.status_code==200 and db().execute('select durum,gidis_at from is_emirleri where id=?',(j['is_emri_id'],)).fetchone()[0]=='Tamamlandı')
k('tamamlanmış iş emrine tekrar bağlanmaz (açık iş emri yok)',G({'plaka':'34XYZ111','km':100020,'kayit_no':'E6'}).get_json()['neden']=='Bu plakanın açık iş emri yok.')
P('/is-emirleri/hizli',plaka='34XYZ111',giris_km='100005'); P('/is-emirleri/hizli',plaka='34XYZ111',giris_km='100006')
r4=G({'plaka':'34XYZ111','km':100005,'kayit_no':'E3'})
k('birden fazla açık iş emri: 202',r4.status_code==202 and 'açık iş emri var' in r4.get_json()['neden'])
r5=G({'plaka':'06NEW999','kayit_no':'E4','musteri_ad':'ali veli','telefon':'0532 111 22 33'})
k('kayıtsız plaka: 202, araç oluşmadı',r5.status_code==202 and db().execute("select count(*) from araclar where plaka='06NEW999'").fetchone()[0]==0)

# --- eşleşmeyenler sayfası ve eylemler ---
s=a.get('/eslesmeyen-kayitlar',environ_overrides=R); t=s.get_data(as_text=True)
k('eşleşmeyenler sayfası açılır, kayıtlar listelenir',s.status_code==200 and 'Kayıt no: E4' in t and 'Kayıt no: E3' in t)
k('menüde rozet görünür',b'E\xc5\x9fle\xc5\x9fmeyen' in a.get('/panel',environ_overrides=R).data)
k('girişsiz eşleşmeyenler sayfası yönlendirir',api.get('/eslesmeyen-kayitlar',environ_overrides=R).status_code in (302,401))
ac=db().execute("select id from is_emirleri where durum!='Tamamlandı' order by id").fetchall()
k('bağla: seçilen iş emrine işler',P('/eslesmeyen-kayitlar/E3/bagla',is_emri_id=ac[0][0]).status_code==302 and db().execute("select durum,is_emri_id from entegrasyon_kayit where kayit_no='E3'").fetchone()==('eslesti',ac[0][0]))
k('yeni aç: iş emri+araç oluşur',P('/eslesmeyen-kayitlar/E4/yeni').status_code==302 and db().execute("select count(*) from araclar where plaka='06NEW999'").fetchone()[0]==1 and db().execute("select kaynak from is_emirleri order by id desc limit 1").fetchone()[0]=='entegrasyon')
k('yoksay',P('/eslesmeyen-kayitlar/E2/yoksay').status_code==302 and db().execute("select durum from entegrasyon_kayit where kayit_no='E2'").fetchone()[0]=='yoksayildi')
n=db().execute("select count(*) from is_emirleri").fetchone()[0]
k('işlenmiş kayıt tekrar işlenmez',P('/eslesmeyen-kayitlar/E2/yeni').status_code==302 and db().execute("select count(*) from is_emirleri").fetchone()[0]==n)
k('bilinmeyen eylem 404',P('/eslesmeyen-kayitlar/B1/sil').status_code==404)

# --- ENTEGRASYON_YENI_KAYIT=1 ---
A.ENT_YENI_KAYIT=True
r=G({'plaka':'16AAA123','km':5000,'kayit_no':'Y1'})
k('YENI_KAYIT açıkken kayıtsız plaka yeni iş emri açar 201',r.status_code==201 and r.get_json()['durum']=='yeni_acildi')
A.ENT_YENI_KAYIT=False

# --- kayıt no zorunlu ---
A.ENT_KAYIT_NO_ZORUNLU=True
k('KAYIT_NO_ZORUNLU: kayit_no yoksa 422',G({'plaka':'35ABC123'}).status_code==422)
A.ENT_KAYIT_NO_ZORUNLU=False

# --- dış gözlemci incelemesinden gelen düzeltmeler ---
k('km ondalıklı JSON sayısı doğru okunur',A._km_rakam(45000.0)=='45000' and A._km_rakam(45000)=='45000' and A._km_rakam('45.000')=='45000' and A._km_rakam('45000,5')=='45000' and A._km_rakam(True)=='' and A._km_rakam(-5)=='' and A._km_rakam(float('nan'))=='' and A._km_rakam(None)=='')
k('ozel_plaka "false"/"0" metni doğru sayılmaz',not A._dogru('false') and not A._dogru('0') and not A._dogru(None) and A._dogru(True) and A._dogru('true') and A._dogru('1'))
k('ozel_plaka "false" metniyle geçersiz plaka 422',G({'plaka':'ABC','kayit_no':'D1','ozel_plaka':'false'}).status_code==422)
k('uç değerli tarih 500 vermez (422)',G({'plaka':'35ABC123','kayit_no':'D2','gelis_zamani':'0001-01-01T00:00:00+03:00'}).status_code==422)
k('ASCII dışı CSRF belirteci 500 değil 400',a.post('/musteriler/ekle',data={'csrf_token':'é'},environ_overrides=R).status_code==400)
G({'plaka':'06ZZZ999','kayit_no':'D3'}); G({'plaka':'06ZZZ998','kayit_no':'D4'})
P('/is-emirleri/hizli',plaka='34TST777',giris_km='1000')
_con=db(); _con.execute("update is_emirleri set durum='Tamamlandı' where arac_id=(select id from araclar where plaka='34TST777')"); _con.commit()
_tid=_con.execute("select id from is_emirleri where arac_id=(select id from araclar where plaka='34TST777')").fetchone()[0]; _con.close()
P('/eslesmeyen-kayitlar/D3/bagla',is_emri_id=_tid)
k('tamamlanmış iş emrine bağlanamaz (kayıt beklemede kalır)',db().execute("select durum from entegrasyon_kayit where kayit_no='D3'").fetchone()[0]=='beklemede')
P('/eslesmeyen-kayitlar/D4/yoksay'); P('/eslesmeyen-kayitlar/D4/yeni')
k('işlenmiş kayıt ikinci istekte değişmez (çift tıklama)',db().execute("select durum from entegrasyon_kayit where kayit_no='D4'").fetchone()[0]=='yoksayildi')

# --- hata kaydında kişi bilgisi maskelenir ---
G({'plaka':'ABC','kayit_no':'M1','telefon':'0555 111 22 33','adres':'Gizli Mah. No:5','eposta':'x@y.com','musteri_ad':'Ali Veli','yapilan_islem':'Yağ değişimi'})
_g=db().execute("select govde from entegrasyon_hata where kayit_no='M1' order by id desc limit 1").fetchone()[0]
k('hata kaydı: telefon/adres/e-posta gizli',('0555' not in _g) and ('Gizli Mah' not in _g) and ('x@y.com' not in _g) and _g.count('***')==3)
k('hata kaydı: plaka, ad ve işlem korunur (sorun aramaya yarar)',('ABC' in _g) and ('Ali Veli' in _g) and ('Yağ değişimi' in _g))
k('JSON olmayan gövdede uzun rakam dizisi gizlenir','0555' not in A._ent_maskele('tel=0555 111 22 33 plaka=ABC') and 'plaka=ABC' in A._ent_maskele('tel=0555 111 22 33 plaka=ABC'))

# --- hız sınırı ---
kotu_h={'X-API-Key':'yanlis','X-Forwarded-Proto':'https'}
for _ in range(11): G({'plaka':'35ABC123'},h=kotu_h)
k('çok yanlış anahtar -> 429',G({'plaka':'35ABC123'},h=kotu_h).status_code==429)

# --- hatalı anahtar sayacı sınırsız büyümez ---
import time as _t
A._ent_hatali.update({f'10.{i//250}.{i%250}.1':[_t.time()-1000] for i in range(600)})
G({'plaka':'35ABC123'},{'X-API-Key':'yanlis-anahtar','X-Forwarded-Proto':'https'})
k('eski hatalı-anahtar kayıtları temizlenir (sözlük büyümez)',len(A._ent_hatali)<50)
# --- belgeler ---
for f in ('docs/ENTEGRASYON-API.md','docs/openapi.yaml','docs/ornekler/ornek.py','docs/ornekler/ornek.sh','docs/ornekler/ornek.js','docs/ornekler/ornek.cs','docs/ornekler/ornek.ps1'):
    k('belge var: '+f,os.path.isfile(f))
print(f'{ok} geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
