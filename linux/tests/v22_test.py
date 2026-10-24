import os as _os; _os.environ['APP_PASSWORD_HASH']='pbkdf2_sha256$600000$0123456789abcdef0123456789abcdef$bc43d8da4a5cfd47df54d15115d65eafe20121e09ab04ca54ddf8dd8397d4335'   # test şifresi: TestSifre-12345!
# V22: para alanları kaldırıldı; müşteri sayfası, dışa aktarma, biçimler, tüm sayfaların taraması
import os,re,sys,shutil,tempfile,csv,io
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
def G(url): return a.get(url,environ_overrides=R)
db=A.sqlite3.connect(A.DB_PATH); db.row_factory=A.sqlite3.Row
def Q(sql,*p): db.commit(); return db.execute(sql,p).fetchall()
PARA=re.compile(r'₺|Veresiye|Ödendi|Tahsilat|Borç|Alacak|veresiye|tahsil|Tutar|tutar',re.U)

# ---- BOŞ veritabanında tüm sayfalar açılıyor mu ----
for u in ('/panel','/is-emirleri','/is-emirleri?g=tamam','/is-emirleri?g=hepsi','/musteriler','/araclar','/ara?q=','/ara?q=zzz','/istatistik','/silinenler','/disa-aktar','/saglik','/'):
    r=G(u); k(f'boş DB: {u} açılır',r.status_code==200)
for t in ('musteriler','araclar','is-emirleri'):
    k(f'boş DB: {t}.csv',G(f'/disa-aktar/{t}.csv').status_code==200)

# ---- veri: 2 araçlı müşteri + zor girdiler ----
P('/is-emirleri/hizli',plaka='35ABC123',musteri_ad='ali veli',telefon='0532 111 22 33',gelis_nedeni='Yağ değişimi',giris_km='100000')
P('/is-emirleri/hizli',plaka='34XYZ789',musteri_ad='ali veli',telefon='0532 111 22 33',gelis_nedeni='Fren balatası',giris_km='50000')
P('/is-emirleri/hizli',plaka='06DEM202',musteri_ad='<script>alert(1)</script> Çağrı Ğüşöç',telefon='0555 000 11 22',gelis_nedeni='Akü, <b>x</b>',giris_km='1000',notlar='=HYPERLINK("x")')
P('/is-emirleri/hizli',plaka='YABANCI-1',ozel_plaka='1',musteri_ad='A'*60,telefon='0555 000 33 44',gelis_nedeni='Klima gazı',giris_km='5')
ids=[r[0] for r in Q('select id from is_emirleri order by id')]; mid=Q('select id from musteriler order by id')[0][0]
k('4 iş emri, aynı telefon tek müşteri',len(ids)==4 and len(Q('select id from musteriler'))==3)

# ---- teslim: tek dokunuş, para sorusu yok ----
h=G('/is-emirleri').get_data(as_text=True)
k('teslim düğmesi form onayıyla çalışır, modal/tutar yok','data-confirm="Araç teslim edildi mi?" data-olumlu="1"' in h and 'teslimModal' not in h and 'teslimTutar' not in h)
P(f'/is-emirleri/durum/{ids[0]}',durum='Tamamlandı')
x=Q('select durum,gidis_at from is_emirleri where id=?',ids[0])[0]; k('teslim edildi, teslim zamanı yazıldı',x[0]=='Tamamlandı' and bool(x[1]))
h=G('/is-emirleri?g=tamam').get_data(as_text=True); k('teslim kartında Geri aç ve WhatsApp var','Geri aç' in h and 'Araç hazır' in h)
P(f'/is-emirleri/durum/{ids[0]}',durum='Devam Ediyor'); x=Q('select durum,gidis_at from is_emirleri where id=?',ids[0])[0]; k('geri aç: teslim zamanı temizlenir',x[0]=='Devam Ediyor' and x[1] is None)
P(f'/is-emirleri/durum/{ids[0]}',durum='Tamamlandı')
# eski para rotaları kalktı
for u in (f'/is-emirleri/odeme/{ids[0]}',f'/is-emirleri/tahsilat/{ids[0]}',f'/musteriler/{mid}/tahsilat'):
    k(f'kalkmış rota yok: {u}',a.post(u,data={'csrf_token':tok(a,'/panel')},environ_overrides=R).status_code in (404,405))

# ---- tüm sayfalarda para dili yok, hata yok, XSS kaçışı ----
sayfalar=['/panel','/is-emirleri','/is-emirleri?g=tamam','/is-emirleri?g=hepsi','/musteriler',f'/araclar?musteri={mid}','/araclar','/ara?q=ali','/istatistik','/silinenler','/disa-aktar',f'/is-emirleri/duzenle/{ids[0]}',f'/musteriler/duzenle/{mid}','/araclar/duzenle/1','/arac/1/qr']
tokens=[r[0] for r in Q('select qr_token from araclar')]; sayfalar+= ['/arac/'+t for t in tokens]
for u in sayfalar:
    r=G(u); body=r.get_data(as_text=True)
    k(f'{u} 200',r.status_code==200)
    k(f'{u}: para dili yok',not PARA.search(re.sub(r'<script.*?</script>|<style.*?</style>','',body,flags=re.S)) )
    k(f'{u}: <script>alert kaçışlı','<script>alert(1)' not in body)
    k(f'{u}: Traceback yok','Traceback' not in body)
for u in ('/olmayan','/musteriler/99999','/arac/yok','/is-emirleri/duzenle/99999','/araclar/duzenle/99999','/disa-aktar/bilinmez.csv'):
    k(f'{u} 404',G(u).status_code==404)
k('404 sayfası düzgün','Sayfa bulunamadı' in G('/olmayan').get_data(as_text=True))

# ---- internetsiz çalışma: Bootstrap yerel ----
for u in ('/login','/panel','/olmayan'):
    b=(G(u) if u!='/login' else A.app.test_client().get(u,environ_overrides=R)).get_data(as_text=True)
    k(f'{u}: dış CDN yok, yerel bootstrap',('cdn.' not in b) and '/static/vendor/bootstrap.min.css' in b)
r=G('/static/vendor/bootstrap.min.css'); k('yerel bootstrap css sunulur, önbelleğe alınabilir',r.status_code==200 and len(r.get_data())>100000 and 'no-store' not in r.headers.get('Cache-Control',''))
k('yerel bootstrap js sunulur',G('/static/vendor/bootstrap.bundle.min.js').status_code==200)
k('CSP dış kaynak izni yok',all(x not in A.CSP for x in ('jsdelivr','cdnjs')))
# ---- iş emirleri sayfası: form kapalı, liste önde ----
h=G('/is-emirleri').get_data(as_text=True)
k('iş emirleri: yeni iş emri kutusu kapalı başlar','<details id="yeni" class="mb-4" >' in h or '<details id="yeni" class="mb-4" >' in h.replace('  ',' '))
k('iş emirleri: ?yeni= ile açık gelir','<details id="yeni" class="mb-4" open>' in G('/is-emirleri?yeni=35ABC123').get_data(as_text=True))
k('iş emirleri: sekmeler formdan önce',h.index('Teslim edilen')>0 and h.index('id="yeni"')<h.index('Teslim edilen'))
# ---- araç kartı kısa; sil/düzenle araç ekranında ----
h=G('/araclar').get_data(as_text=True); k('araç kartında Sil yok, ✏️ Düzenle var','>Sil<' not in h and '✏️ Düzenle' in h)
h=G('/araclar/duzenle/1').get_data(as_text=True); k('araç düzenle: Aracı sil düğmesi var','/araclar/sil/1' in h and 'Aracı sil' in h)
# ---- müşterinin araçları (ayrı müşteri sayfası yok; /musteriler/<id> bu listeye yönlenir) ----
r=G(f'/musteriler/{mid}'); k('eski müşteri bağlantısı araç listesine yönlenir',r.status_code==302 and f'/araclar?musteri={mid}' in r.headers['Location'])
h=G(f'/araclar?musteri={mid}').get_data(as_text=True)
k('müşterinin araçları: iki araç, iki "İş Emri Aç"',h.count('İş Emri Aç')==2 and '35 ABC 123' in h and '34 XYZ 789' in h)
k('müşterinin araçları: telefon biçimli, ara/WhatsApp','0532 111 22 33' in h and 'tel:' in h and 'wa.me' in h)
k('müşterinin araçları: müşteriyi düzenle var',f'/musteriler/duzenle/{mid}' in h)
h=G('/musteriler').get_data(as_text=True)
k('liste: kompakt kart, plakalar, link',f'/araclar?musteri={mid}"' in h and '35 ABC 123' in h and '>Sil<' not in h)
k('arama sonucu müşterinin araçlarına gider',f'/araclar?musteri={mid}"' in G('/ara?q=ali').get_data(as_text=True))

# ---- dışa aktarma ----
for tur,beklenen in (('musteriler','ALİ VELİ'),('araclar','35 ABC 123'),('is-emirleri','Fren balatası')):
    r=G(f'/disa-aktar/{tur}.csv'); b=r.get_data()
    k(f'csv {tur}: BOM, UTF-8, içerik, indirme başlığı',r.status_code==200 and b.startswith(b'\xef\xbb\xbf') and beklenen in b.decode('utf-8-sig') and 'attachment' in r.headers['Content-Disposition'])
    k(f'csv {tur}: para sütunu yok',not PARA.search(b.decode('utf-8-sig')))
rows=list(csv.reader(io.StringIO(G('/disa-aktar/is-emirleri.csv').get_data().decode('utf-8-sig')),delimiter=';'))
k('csv iş emirleri: başlık + 4 satır',len(rows)==5 and rows[0][:4]==['No','Geliş','Teslim','Plaka'])
raw=G('/disa-aktar/is-emirleri.csv').get_data().decode('utf-8-sig'); k('csv: formül gibi başlayan hücre korunur',"'=HYPERLINK" in raw and ';=HYPERLINK' not in raw)
k('csv formül koruması fonksiyonu',A._csv_hucre('=1+1')=="'=1+1" and A._csv_hucre('Ali')=='Ali')
k('csv oturumsuz yasak',A.app.test_client().get('/disa-aktar/musteriler.csv',environ_overrides=R).status_code in (302,401,403))

# ---- biçimler ----
h=G(f'/musteriler/duzenle/{mid}').get_data(as_text=True); k('müşteri düzenle: telefon boşluklu','value="0532 111 22 33"' in h)
P(f'/musteriler/duzenle/{mid}',ad_soyad='ali veli',telefon='0532 111 22 33',eposta='',adres='',notlar='')
k('boşluklu telefon kaydı bozulmaz',Q('select telefon from musteriler where id=?',mid)[0][0].replace(' ','')=='05321112233')
h=G('/araclar/duzenle/1').get_data(as_text=True)
k('araç düzenle: tarih gg.aa.yyyy',re.search(r'\d\d\.\d\d\.\d{4} \d\d:\d\d',h) is not None and not re.search(r'20\d\d\.\d\d\.\d\d',h))
k('panelde yedek uyarısı tek',G('/panel').get_data(as_text=True).count('Henüz hiç yedek')==1)
k('diğer sayfada yedek uyarısı var',G('/araclar').get_data(as_text=True).count('Henüz hiç yedek')==1)
h=G('/istatistik').get_data(as_text=True); k('istatistik: Özet + Bakım sekmesi, Veresiye yok','flex-nowrap' in h and '>Bakım' in h and 'Veresiye' not in h)

k('yeni kurulumda para sütunları yok',not any(c[1] in ('toplam_tutar','odeme_durumu','odeme_at') for c in Q('PRAGMA table_info(is_emirleri)')) and not Q("select name from sqlite_master where name='tahsilat'"))
# ---- eski veritabanı (V20/V21) para sütunlarıyla gelse bile uygulama sorunsuz çalışır ----
for c in ('odeme_durumu TEXT','odeme_at TEXT','toplam_tutar REAL DEFAULT 0'): db.execute('ALTER TABLE is_emirleri ADD COLUMN '+c)
db.execute("UPDATE is_emirleri SET toplam_tutar=1500,odeme_durumu='Veresiye' WHERE id=?",(ids[1],)); db.commit()
k('eski para verisi sütunlarda dursa da sayfalar açılır',all(G(u).status_code==200 for u in ('/is-emirleri','/is-emirleri?g=hepsi','/panel','/istatistik',f'/araclar?musteri={mid}')))
k('düzenleme kaydı eski para verisini bozmaz',P(f'/is-emirleri/duzenle/{ids[1]}',arac_id=Q('select arac_id from is_emirleri where id=?',ids[1])[0][0],gelis_at='2026-10-05T10:30',gidis_at='',giris_km='1',durum='Beklemede',gelis_nedeni='x',yapilan_islem='',notlar='').status_code==302 and Q('select toplam_tutar from is_emirleri where id=?',ids[1])[0][0]==1500)

# ---- silinen iş emri geri gelir ----
P(f'/is-emirleri/sil/{ids[0]}'); cid=Q('select id from cop where tablo=? order by id desc','is_emirleri')[0][0]; P(f'/silinenler/{cid}/geri')
k('silinen iş emri geri gelir',Q('select durum from is_emirleri where id=?',ids[0])[0][0]=='Tamamlandı')
# ---- güvenlik ----
anon=A.app.test_client()
k('oturumsuz: müşteri araçları korumalı',anon.get(f'/araclar?musteri={mid}',environ_overrides=R).status_code in (302,401,403))
k('oturumsuz: dışa aktar korumalı',anon.get('/disa-aktar',environ_overrides=R).status_code in (302,401,403))
print(f'{ok} kontrol geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
