import os as _os; _os.environ['APP_PASSWORD_HASH']='pbkdf2_sha256$600000$0123456789abcdef0123456789abcdef$bc43d8da4a5cfd47df54d15115d65eafe20121e09ab04ca54ddf8dd8397d4335'   # test şifresi: TestSifre-12345!
# Uzun listeler sayfalanır (100'er), arama sayfalarla çalışır; WhatsApp "araç hazır" düğmesi yalnız açık/bugün biten işlerde; panelde bugünün tarihi yerine saat.
import os,re,sys,shutil,tempfile,sqlite3
from datetime import datetime,timedelta
d=tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),d+'/a',ignore=shutil.ignore_patterns('data','__pycache__')); os.chdir(d+'/a'); sys.path.insert(0,'.')
import app as A; A.app.config['CIHAZ_KAPISI']=False
ok=0;fail=0
def k(ad,c):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print('BAŞARISIZ:',ad)
R={'REMOTE_ADDR':'127.0.0.1'}
c=A.app.test_client(); t=re.search(r'name="csrf_token" value="([^"]+)"',c.get('/login',environ_overrides=R).get_data(as_text=True)).group(1)
c.post('/login',data={'csrf_token':t,'sifre':'TestSifre-12345!'},environ_overrides=R)
def G(u): return c.get(u,environ_overrides=R)
def bugun(n=0): return (datetime.now()-timedelta(days=n)).strftime('%Y-%m-%d %H:%M:%S')
con=sqlite3.connect(A.DB_PATH)
for i in range(250):
    con.execute("insert into musteriler(ad_soyad,telefon,olusturuldu_at,guncellendi_at) values(?,?,?,?)",(f'MÜŞTERİ {i:03d}',f'0532{i:07d}',bugun(),bugun()))
    con.execute("insert into araclar(musteri_id,plaka,qr_token,olusturuldu_at,guncellendi_at) values(?,?,?,?,?)",(i+1,f'34AB{i:03d}',f'tk{i}',bugun(),bugun()))
con.commit()
KART='fs-4 fw-bold lh-sm'
h1=G('/musteriler').get_data(as_text=True); h2=G('/musteriler?s=2').get_data(as_text=True); h3=G('/musteriler?s=3').get_data(as_text=True)
k('müşteriler: ilk sayfa 100 kayıt + Sonraki',h1.count(KART)==100 and 'Sonraki →' in h1 and '← Önceki' not in h1)
k('müşteriler: 2. sayfa 100 kayıt, her iki bağlantı',h2.count(KART)==100 and 'Sonraki →' in h2 and '← Önceki' in h2)
k('müşteriler: son sayfa 50 kayıt, Sonraki yok',h3.count(KART)==50 and 'Sonraki →' not in h3)
k('müşteriler: kayıtlar tekrarsız (en yeni önce)','MÜŞTERİ 249' in h1 and 'MÜŞTERİ 149' in h2 and 'MÜŞTERİ 049' in h3 and 'MÜŞTERİ 149' not in h1)
k('müşteriler: yalnız görünen müşterilerin plakası var','34 AB 249' in h1 and '34 AB 000' not in h1 and '34 AB 000' in h3)
k('müşteriler: çok büyük sayfa numarası hata vermez',G('/musteriler?s=99999999999999999999').status_code==200 and G('/musteriler?s=abc').status_code==200 and G('/musteriler?s=-5').get_data(as_text=True).count(KART)==100)
hq=G('/musteriler?q=M%C3%9C%C5%9ETER%C4%B0').get_data(as_text=True)
k('müşteriler: arama sayfalanır ve arama terimi sonraki bağlantıda kalır',hq.count(KART)==100 and 'Sonraki →' in hq and re.search(r'href="[^"]*q=[^"]*s=2"',hq) is not None)
k('müşteriler: tek sonuç aramada gezinme çubuğu yok','Sonraki' not in G('/musteriler?q=MÜŞTERİ+007').get_data(as_text=True) and 'MÜŞTERİ 007' in G('/musteriler?q=M%C3%9C%C5%9ETER%C4%B0+007').get_data(as_text=True))
PL='fs-3 fw-bold lh-1 text-nowrap'
a1=G('/araclar').get_data(as_text=True); a3=G('/araclar?s=3').get_data(as_text=True)
k('araçlar: 100 kayıt + Sonraki; son sayfa 50',a1.count(PL)==100 and 'Sonraki →' in a1 and a3.count(PL)==50 and 'Sonraki →' not in a3)
k('araçlar: tek müşterinin araçları sayfalanmaz',G('/araclar?musteri=5').get_data(as_text=True).count(PL)==1)
aq=G('/araclar?q=34AB').get_data(as_text=True)
k('araçlar: arama sayfalı çalışır, terim bağlantıda kalır',aq.count(PL)==100 and re.search(r'href="[^"]*q=34AB[^"]*s=2"',aq) is not None)
k('araçlar: plaka araması doğru sonuç',G('/araclar?q=34AB077').get_data(as_text=True).count(PL)==1)
# WhatsApp düğmesi + panel saati
con.execute("insert into is_emirleri(arac_id,tarih,gelis_nedeni,durum,gelis_at,gidis_at,giris_km,olusturuldu_at,guncellendi_at) values(1,'x','Bakım','Devam Ediyor',?,NULL,1000,?,?)",(bugun(),bugun(),bugun()))
con.execute("insert into is_emirleri(arac_id,tarih,gelis_nedeni,durum,gelis_at,gidis_at,giris_km,olusturuldu_at,guncellendi_at) values(2,'x','Bakım','Tamamlandı',?,?,1000,?,?)",(bugun(),bugun(),bugun(),bugun()))
con.execute("insert into is_emirleri(arac_id,tarih,gelis_nedeni,durum,gelis_at,gidis_at,giris_km,olusturuldu_at,guncellendi_at) values(3,'x','Bakım','Tamamlandı',?,?,1000,?,?)",(bugun(10),bugun(10),bugun(10),bugun(10)))
con.execute("insert into is_emirleri(arac_id,tarih,gelis_nedeni,durum,gelis_at,gidis_at,giris_km,olusturuldu_at,guncellendi_at) values(4,'x','Bakım','Beklemede',?,NULL,1000,?,?)",(bugun(),bugun(),bugun()))
con.commit()
def kartlar(plaka):
    h=G('/is-emirleri?sekme=hepsi&q='+plaka).get_data(as_text=True); return h.count('WhatsApp: Araç hazır')
k('WhatsApp düğmesi: devam eden işte var',kartlar('34AB000')==1)
k('WhatsApp düğmesi: bugün teslim edilen işte var',kartlar('34AB001')==1)
k('WhatsApp düğmesi: eski tamamlanan işte yok',kartlar('34AB002')==0)
k('WhatsApp düğmesi: beklemedeki işte yok',kartlar('34AB003')==0)
hp=G('/panel').get_data(as_text=True); gun=datetime.now().strftime('%d.%m.%Y')
k('panel: "Bugün gelen" satırlarında tarih yok, saat var',gun not in hp.split('Bugün gelen')[1].split('Toplam')[0] and re.search(r'· \d\d:\d\d</span>',hp) is not None)
k('iş emri formunda müşteri adı ipucu','placeholder="Ad Soyad"' in G('/is-emirleri').get_data(as_text=True))
# --- durum renkleri: yeşil temada "Devam Ediyor" ayrı (mavi), Windows'ta zaten mavi ---
yesil='#1f8f5f' in open('templates/base.html',encoding='utf-8').read()
hh=G('/is-emirleri?g=hepsi').get_data(as_text=True)
if yesil: k('yeşil tema: devam eden kart/rozet mavi sınıfla, tamamlanan yeşil',('text-bg-devam' in hh) and ('border-devam' in hh) and ('text-bg-primary fs-6' not in hh) and ('text-bg-success' in hh))
else: k('mavi tema: devam eden kart/rozet primary, tamamlanan yeşil',('text-bg-primary fs-6' in hh) and ('text-bg-success' in hh))
# --- giriş/arama alanlarında ekran okuyucu etiketi (placeholder tek başına yetmez) ---
import glob
eksik=[]
for f in glob.glob('templates/*.html'):
    s_=open(f,encoding='utf-8').read()
    for m in re.finditer(r'<(?:input|textarea)\b[^<>]*>',s_):
        t_=m.group(0)
        if '{%' in t_ or 'id="{{' in t_ or 'aria-label' in t_ or re.search(r'type="(hidden|checkbox|radio|submit|button|file)"',t_) or 'placeholder="' not in t_: continue
        i_=re.search(r'\bid="([^"{}]+)"',t_)
        if i_ and re.search(r'<label[^>]*for="%s"'%re.escape(i_.group(1)),s_): continue
        eksik.append(f)
k('placeholder\'lı her alanın ekran okuyucu etiketi var: '+','.join(eksik[:3]),not eksik)
print(f'{ok} geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
