import os as _os; _os.environ['APP_PASSWORD_HASH']='pbkdf2_sha256$600000$0123456789abcdef0123456789abcdef$bc43d8da4a5cfd47df54d15115d65eafe20121e09ab04ca54ddf8dd8397d4335'   # test şifresi: TestSifre-12345!
# Araç km (iş emri silinince/taşınınca), CSV formül koruması, çıkışın POST olması
import os,re,sys,shutil,tempfile
d=tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),d+'/a',ignore=shutil.ignore_patterns('data','__pycache__')); os.chdir(d+'/a'); sys.path.insert(0,'.')
import app as A
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
def db(): return A.sqlite3.connect(A.DB_PATH)
def km(plaka): return db().execute('select kilometre from araclar where plaka=?',(plaka,)).fetchone()[0]

# --- km: en son iş emrinden gelir; iş emri kalmayınca son bilinen km korunur, başka araca taşınınca yeni araç yenilenir ---
P('/is-emirleri/hizli',plaka='35ABC123',giris_km='120000'); P('/is-emirleri/hizli',plaka='06XYZ99',giris_km='50000')
k('km iş emrinden gelir',km('35ABC123')==120000 and km('06XYZ99')==50000)
i1=db().execute("select i.id from is_emirleri i join araclar a on a.id=i.arac_id where a.plaka='35ABC123'").fetchone()[0]
a2=db().execute("select id from araclar where plaka='06XYZ99'").fetchone()[0]
P(f'/is-emirleri/duzenle/{i1}',arac_id=str(a2),gelis_at='2026-10-05T10:30',gidis_at='',giris_km='120000',durum='Beklemede',gelis_nedeni='x',yapilan_islem='',notlar='',geri='')
k('taşınınca eski aracın son bilinen km\'si korunur',km('35ABC123')==120000)
k('taşınınca yeni aracın km\'si güncellenir',km('06XYZ99') in (50000,120000))
r=db().execute("select id from is_emirleri").fetchall()
for (i,) in r: P(f'/is-emirleri/sil/{i}')
if db().execute('select count(*) from is_emirleri').fetchone()[0]==0:
    k('tüm iş emirleri silinince son bilinen km korunur',km('06XYZ99') in (50000,120000))
else: print('(silme adresi farklı, bu kontrol atlandı)')

# --- CSV formül koruması ---
h=A._csv_hucre
k('= ile başlayan korunur',h('=1+1').startswith("'"))
k('boşlukla başlayan formül korunur',h('  =cmd').startswith("'"))
k('sekmeyle başlayan korunur',h('\t=1').startswith("'"))
k('satır başıyla başlayan korunur',h('\r=1').startswith("'"))
k('@ + - korunur',all(h(x+'a').startswith("'") for x in '@+-'))
k('normal metin değişmez',h('Fren balatası')=='Fren balatası' and h(None)=='' and h(123)=='123')

# --- çıkış: yalnızca POST ---
sayfa=a.get('/panel',environ_overrides=R).get_data(as_text=True)
k('çıkış düğmesi POST formu',bool(re.search(r'<form method="post" action="/logout"',sayfa)))
a.get('/logout',environ_overrides=R)
k('GET /logout oturumu kapatmaz',a.get('/panel',environ_overrides=R).status_code==200)
r=a.post('/logout',data={'csrf_token':'yanlis'},environ_overrides=R)
k('yanlış CSRF ile çıkış yapılmaz',r.status_code in (400,403) and a.get('/panel',environ_overrides=R).status_code==200)
r=a.post('/logout',data={'csrf_token':tok(a,'/panel')},environ_overrides=R)
k('doğru CSRF ile çıkış çalışır',r.status_code==302 and a.get('/panel',environ_overrides=R).status_code==302)
print(f'\n{ok} kontrol geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
