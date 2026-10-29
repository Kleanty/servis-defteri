# Kod taraması (2026-10-30) düzeltmeleri: yarım dükkân kalmaz, /saglik dükkân veritabanlarını da yoklar, "Bağla" başka aracın iş emrine bağlanmaz.
import os,re,sys,shutil,tempfile,hashlib,sqlite3
os.environ['FORCE_HTTPS_COOKIE']='0'
d=tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),d+'/a',ignore=shutil.ignore_patterns('data','__pycache__')); os.chdir(d+'/a'); sys.path.insert(0,'.'); sys.path.insert(0,'yazdirma_ajani')
import app as A; A.app.config['CIHAZ_KAPISI']=False
ok=fail=0
def k(ad,c):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print('BAŞARISIZ:',ad)
R={'REMOTE_ADDR':'127.0.0.1'}
# 1) init_db patlarsa: hata, kayıt yok, klasör yok, kullanıcı adı yeniden kullanılabilir
orijinal=A.init_db
def patla(y,kod): os.makedirs(os.path.dirname(y),exist_ok=True); raise OSError('disk dolu (taklit)')
A.init_db=patla
try: A.dukkan_olustur('yarim-oto','Yarım Oto',sifre='Yarim-Sifre-1',gecici=False); hata=None
except ValueError as e: hata=str(e)
A.init_db=orijinal
k('oluşturma hatası Türkçe ValueError verir',bool(hata) and 'oluşturulamadı' in hata)
k('yarım dükkân kaydı kalmaz',not any(x['kullanici']=='yarim-oto' for x in A.tum_dukkanlar()))
k('yarım dükkân klasörü kalmaz',not any(os.path.isdir(A.dukkan_dizin(i)) for i in range(1,5) if not any(x['id']==i for x in A.tum_dukkanlar())))
i1,_=A.dukkan_olustur('yarim-oto','Yarım Oto',sifre='Yarim-Sifre-1',gecici=False)
k('aynı kullanıcı adı sonra açılabilir ve etkin',any(x['kullanici']=='yarim-oto' and x['aktif'] for x in A.tum_dukkanlar()) and os.path.exists(A.db_yolu(i1)))
# 2) /saglik
api=A.app.test_client()
k('/saglik sağlamken ok',api.get('/saglik',environ_overrides=R).status_code==200)
os.rename(A.db_yolu(i1),A.db_yolu(i1)+'.x'); r=api.get('/saglik',environ_overrides=R)
k('dükkân veritabanı yoksa /saglik 503 verir ve boş dosya yaratmaz',r.status_code==503 and not os.path.exists(A.db_yolu(i1)))
os.rename(A.db_yolu(i1)+'.x',A.db_yolu(i1)); k('düzelince tekrar ok',api.get('/saglik',environ_overrides=R).status_code==200)
# 3) Bağla: başka aracın iş emri ezilmez
i2,_=A.dukkan_olustur('veli-servis','Veli Servis',sifre='Veli-Sifre-12',gecici=False)
c=A.app.test_client()
def tok(y='/login'): return re.search(r'name="csrf_token" value="([^"]+)"',c.get(y,environ_overrides=R).get_data(as_text=True)).group(1)
c.post('/login',data={'csrf_token':tok(),'kullanici':'veli-servis','sifre':'Veli-Sifre-12'},environ_overrides=R)
def hizli(p,km): return c.post('/is-emirleri/hizli',data={'csrf_token':tok('/panel'),'plaka':p,'giris_km':str(km),'gelis_nedeni':'Bakım'},environ_overrides=R)
hizli('06AAA111',1000)
kod=[x for x in A.tum_dukkanlar() if x['id']==i2][0]['kod']; KA=f'sk_{kod}_'+'a'*32
m=sqlite3.connect(A.YONETIM_DB); m.execute('UPDATE dukkanlar SET api_hash=? WHERE id=?',(hashlib.sha256(KA.encode()).hexdigest(),i2)); m.commit(); m.close()
r=api.post('/api/v1/is-emirleri',json={'plaka':'34ZZZ999','kayit_no':'S1','yapilan_islem':'YANLIS ISLEM','durum':'Devam Ediyor'},headers={'X-API-Key':KA,'X-Forwarded-Proto':'https'},environ_overrides={'REMOTE_ADDR':'10.1.2.3'})
k('kayıtsız plaka beklemeye düşer',r.status_code==202)
db=sqlite3.connect(A.db_yolu(i2)); db.row_factory=sqlite3.Row
hedef=db.execute('SELECT id FROM is_emirleri').fetchone()['id']; once=tuple(db.execute('SELECT durum,yapilan_islem,notlar FROM is_emirleri WHERE id=?',(hedef,)).fetchone())
c.post('/eslesmeyen-kayitlar/S1/bagla',data={'csrf_token':tok('/panel'),'is_emri_id':hedef},environ_overrides=R)
sonra=tuple(db.execute('SELECT durum,yapilan_islem,notlar FROM is_emirleri WHERE id=?',(hedef,)).fetchone())
k('başka aracın iş emri değişmez',once==sonra)
k('kayıt beklemede kalır',db.execute("SELECT durum FROM entegrasyon_kayit WHERE kayit_no='S1'").fetchone()[0]=='beklemede')
print(f'{ok} geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
