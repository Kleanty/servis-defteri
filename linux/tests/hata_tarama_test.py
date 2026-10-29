# Kod taraması (2026-10-30) düzeltmeleri: "Bağla" yalnızca kaydın plakasındaki aracın iş emrine bağlayabilir; gizli anahtar yarışı.
import os,re,sys,shutil,tempfile
os.environ['FORCE_HTTPS_COOKIE']='0'; os.environ['ENTEGRASYON_API_ANAHTARI']='k-123'
d=tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),d+'/a',ignore=shutil.ignore_patterns('data','__pycache__')); os.chdir(d+'/a'); sys.path.insert(0,'.')
import app as A; A.app.config['CIHAZ_KAPISI']=False
ok=0;fail=0
def k(ad,c):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print('BAŞARISIZ:',ad)
R={'REMOTE_ADDR':'127.0.0.1'}; c=A.app.test_client()
tok=lambda y='/login': re.search(r'name="csrf_token" value="([^"]+)"',c.get(y,environ_overrides=R).get_data(as_text=True)).group(1)
sif=re.search(r'(?:şifresi|Şifre)\S*:\s*(\S+)',open('data/ILK_SIFRE.txt',encoding='utf-8').read()).group(1)
c.post('/login',data={'csrf_token':tok(),'sifre':sif},environ_overrides=R)
def hizli(plaka,km): return c.post('/is-emirleri/hizli',data={'csrf_token':tok('/panel'),'plaka':plaka,'giris_km':str(km),'gelis_nedeni':'Bakım'},environ_overrides=R)
hizli('06AAA111',1000); hizli('06BBB222',2000)
db=A.sqlite3.connect(A.DB_PATH); db.row_factory=A.sqlite3.Row
def ie(p): return db.execute("SELECT i.id FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id WHERE a.plaka=?",(p,)).fetchone()['id']
def durum(i): return tuple(db.execute('SELECT durum,yapilan_islem,notlar FROM is_emirleri WHERE id=?',(i,)).fetchone())
api=A.app.test_client()
def gonder(no,plaka,islem):
    return api.post('/api/v1/is-emirleri',json={'plaka':plaka,'kayit_no':no,'yapilan_islem':islem,'durum':'Devam Ediyor'},headers={'X-API-Key':'k-123','X-Forwarded-Proto':'https'},environ_overrides={'REMOTE_ADDR':'10.1.2.3'})
def bagla(no,hedef): return c.post(f'/eslesmeyen-kayitlar/{no}/bagla',data={'csrf_token':tok('/panel'),'is_emri_id':hedef},environ_overrides=R)
def kayit(no): return db.execute('SELECT durum,is_emri_id FROM entegrasyon_kayit WHERE kayit_no=?',(no,)).fetchone()
# 1) kayıtsız plaka -> beklemede; başka aracın iş emrine bağlanamaz
k('kayıtsız plaka beklemeye düşer',gonder('S1','34ZZZ999','YANLIS ISLEM').status_code==202)
once=durum(ie('06AAA111')); bagla('S1',ie('06AAA111')); db.commit()
k('başka aracın iş emri değişmez',durum(ie('06AAA111'))==once and 'YANLIS' not in repr(durum(ie('06AAA111'))))
k('kayıt beklemede kalır (karar verilebilir)',kayit('S1')['durum']=='beklemede')
# 2) plakası kayıtlı ama iki açık iş emri (belirsiz) -> doğru araca bağlanır, yanlışa bağlanmaz
hizli('06AAA111',1500)
ikinci=db.execute("SELECT i.id FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id WHERE a.plaka='06AAA111' ORDER BY i.id DESC").fetchone()['id']
k('belirsiz plaka beklemeye düşer',gonder('S2','06AAA111','DOGRU ISLEM').status_code==202)
bagla('S2',ie('06BBB222')); k('S2 yanlış araca bağlanmaz',kayit('S2')['durum']=='beklemede' and 'DOGRU' not in repr(durum(ie('06BBB222'))))
bagla('S2',ikinci); k('S2 doğru araca bağlanır',kayit('S2')['durum']=='eslesti' and kayit('S2')['is_emri_id']==ikinci and 'DOGRU' in repr(durum(ikinci)))
# 3) gizli anahtar yarışı: dosya zaten varsa (başka süreç yazdı) onu okur
yol=os.path.join(A.BASE_DIR,'data','.secret_key'); os.environ.pop('SECRET_KEY',None)
k('anahtar dosyası var ve okunur',open(yol).read().strip()==A._sirri_yukle())
sil=os.remove; 
try:
    os.remove(yol); import threading; sonuc=[]
    t=[threading.Thread(target=lambda: sonuc.append(A._sirri_yukle())) for _ in range(6)]; [x.start() for x in t]; [x.join() for x in t]
    k('eşzamanlı başlayan süreçler aynı anahtarı kullanır',len(set(sonuc))==1 and sonuc[0]==open(yol).read().strip())
finally: pass
print(f'{ok} geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
