import os as _os; _os.environ['APP_PASSWORD_HASH']='pbkdf2_sha256$600000$0123456789abcdef0123456789abcdef$bc43d8da4a5cfd47df54d15115d65eafe20121e09ab04ca54ddf8dd8397d4335'   # test şifresi: TestSifre-12345!
# Zorunlu alanlar: PLAKA, GİRİŞ KM (araç formlarında ayrıca müşteri seçimi). Marka ve model zorunlu DEĞİL.
import os,re,sys,shutil,tempfile,glob
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
def db(): return A.sqlite3.connect(A.DB_PATH)

# --- şablonlarda yalnızca plaka, giriş km (ve giriş şifresi) "required" ---
gerekli=set()
for f in glob.glob('templates/*.html'):
    for m in re.finditer(r'<(?:input|select|textarea)\b[^>]*\brequired\b[^>]*>',open(f,encoding='utf-8').read()):
        ad=re.search(r'name="([^"]+)"',m.group(0)); gerekli.add(ad.group(1) if ad else '?')
k('formlarda zorunlu alan yalnızca plaka / giriş km / müşteri seçimi / şifre',gerekli<={'plaka','giris_km','musteri_id','sifre'})
k('marka, model, isim zorunlu değil',not ({'marka','model','ad_soyad','musteri_ad','telefon'}&gerekli))

# --- hızlı iş emri: yalnızca plaka + giriş km ---
r=P('/is-emirleri/hizli',plaka='35ABC123',giris_km='120000')
k('plaka + km yeterli (marka/model/isim/telefon yok)',r.status_code in (200,302))
c=db(); m=c.execute('select ad_soyad from musteriler').fetchone(); ar=c.execute('select plaka,marka,model,kilometre from araclar').fetchone()
k('isim boşsa İSİMSİZ yazılır',bool(m) and m[0]==A.ISIMSIZ_ON_EK)
k('marka/model boş kaydedilir, km yazılır',bool(ar) and ar[0]=='35ABC123' and not (ar[1] or '') and not (ar[2] or '') and ar[3]==120000)
k('iş emri oluştu',c.execute('select count(*) from is_emirleri').fetchone()[0]==1)
r=P('/is-emirleri/hizli',plaka='34XYZ99'); k('giriş km yoksa reddedilir (400)',r.status_code==400)
r=P('/is-emirleri/hizli',giris_km='100'); k('plaka yoksa reddedilir (400)',r.status_code==400)
k('reddedilenler kayıt açmadı',db().execute('select count(*) from araclar').fetchone()[0]==1)

# --- araç ekle: plaka + müşteri zorunlu; marka/model/yıl vb. değil ---
mid=db().execute('select id from musteriler').fetchone()[0]
P('/araclar/ekle',plaka='06ABC12',musteri_id=str(mid)); c=db()
k('araç plaka + müşteriyle eklenir (marka/model yok)',c.execute("select count(*) from araclar where plaka='06ABC12' and (marka is null or marka='') and (model is null or model='')").fetchone()[0]==1)
P('/araclar/ekle',plaka='',musteri_id=str(mid)); k('plakasız araç eklenmez',db().execute('select count(*) from araclar').fetchone()[0]==2)
P('/araclar/ekle',plaka='07DEF34'); k('müşterisiz araç eklenmez',db().execute("select count(*) from araclar where plaka='07DEF34'").fetchone()[0]==0)
P('/araclar/ekle',plaka='08GHI56',musteri_id='99999'); k('olmayan müşteri reddedilir',db().execute("select count(*) from araclar where plaka='08GHI56'").fetchone()[0]==0)

# --- araç düzenle: marka/model boş olabilir; Kilometre kutusu yok ---
aid=db().execute("select id from araclar where plaka='06ABC12'").fetchone()[0]
h=a.get(f'/araclar/duzenle/{aid}',environ_overrides=R).get_data(as_text=True)
k('araç düzenle: Kilometre kutusu yok','Kilometre' not in h)
P(f'/araclar/duzenle/{aid}',plaka='06ABC12',musteri_id=str(mid),marka='',model='')
k('araç düzenle: marka/model boş kaydedilir',db().execute('select count(*) from araclar where id=?',(aid,)).fetchone()[0]==1)
P(f'/araclar/duzenle/{aid}',plaka='',musteri_id=str(mid))
k('araç düzenle: plaka boşsa reddedilir',db().execute('select plaka from araclar where id=?',(aid,)).fetchone()[0]=='06ABC12')

# --- iş emri düzenle: giriş km zorunlu kalır ---
iid=db().execute('select id from is_emirleri').fetchone()[0]
aid1=db().execute("select id from araclar where plaka='35ABC123'").fetchone()[0]
P(f'/is-emirleri/duzenle/{iid}',arac_id=str(aid1),gelis_at='2026-10-05T10:30',gidis_at='',giris_km='',durum='Devam Ediyor',gelis_nedeni='x',yapilan_islem='',notlar='',geri='')
k('iş emri düzenle: km boşsa kayıt değişmez',db().execute('select giris_km from is_emirleri where id=?',(iid,)).fetchone()[0]==120000)

# --- tarayıcıda marka/model engeli kalmamış olmalı; kutular hep görünür ---
html=open('templates/isemirleri.html',encoding='utf-8').read()
k('formda marka/model zorunluluk mesajı yok',('Marka seçmelisin' not in html) and ('Model yazmalısın' not in html))
k('marka/model alanı gizlenmiyor',"aracAlan.classList.toggle('d-none'" not in html)

# --- işlem listesi: yinelenen yok, virgül yok, sağ/sol ve ön/arka parçalar var, eski işlemler korunmuş ---
tum=[c for _,_,l in A.ISLEM_KATEGORILERI for c in l]
k('işlem listesinde yinelenen yok',len(tum)==len(set(A.fold(c) for c in tum)))
k('işlem adlarında virgül yok (virgül ayırıcıdır)',not any(',' in c for c in tum))
k('sağ/sol ön takım parçaları var',all(x in tum for x in ('Ön salıncak sağ','Ön salıncak sol','Ön aks sağ','Ön aks körüğü sol','Ön rotil sağ','Ön rot başı sol')))
k('ön/arka ayrımı var',all(x in tum for x in ('Ön fren balatası','Arka fren balatası','Ön amortisör sağ','Arka amortisör sol','Arka amortisör sağ','Arka helezon yayı sol')))
k('bakım hatırlatma anahtarları yeni işlemlere takılmıyor',not any(any(a in A.fold(c) for a in A.BAKIM_ANAHTAR) for c in tum if c not in ('Periyodik bakım','Yağ değişimi','Yağ filtresi')))

print(f'\n{ok} kontrol geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
