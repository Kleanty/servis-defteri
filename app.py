import os, re, json, sqlite3, hashlib, secrets, time
from io import BytesIO
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort, Response, jsonify
import qrcode
import etiket_yazici as EY

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DB_PATH=os.path.join(BASE_DIR,'data','servis.db')
BACKUP_DIR=os.path.join(BASE_DIR,'data','yedekler')
def _sirri_yukle():
    # SECRET_KEY artık koda gömülü DEĞİL (eski anahtar kodda göründüğü için sızmış sayılır).
    # Sıra: ortam değişkeni -> data/.secret_key dosyası -> yoksa rastgele üretip dosyaya yazar.
    k=os.environ.get('SECRET_KEY','').strip()
    if k: return k
    yol=os.path.join(BASE_DIR,'data','.secret_key')
    try:
        if os.path.exists(yol): return open(yol).read().strip()
        os.makedirs(os.path.dirname(yol),exist_ok=True); k=secrets.token_hex(32)
        fd=os.open(yol,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.write(fd,k.encode()); os.close(fd); return k
    except OSError: return secrets.token_hex(32)   # yazılamazsa geçici anahtar (oturumlar yeniden başlatmada düşer)
SECRET_KEY=_sirri_yukle()
def _hash_uret(sifre):
    tuz=secrets.token_bytes(16)
    return f"pbkdf2_sha256$600000${tuz.hex()}${hashlib.pbkdf2_hmac('sha256',sifre.encode(),tuz,600000).hex()}"
def _hash_yukle():
    # Şifre hash'i sırası: data/.password_hash (sifre_degistir.py yazar) -> APP_PASSWORD_HASH ortam değişkeni.
    # İkisi de yoksa İLK ÇALIŞTIRMA: rastgele bir şifre üretilir, hash'i data/.password_hash'e yazılır,
    # şifrenin kendisi bir kez log'a ve data/ILK_SIFRE.txt dosyasına yazılır. Koda gömülü şifre YOKTUR.
    yol=os.path.join(BASE_DIR,'data','.password_hash')
    try:
        if os.path.exists(yol):
            h=open(yol).read().strip()
            if h.count('$')==3: return h
    except OSError: pass
    h=os.environ.get('APP_PASSWORD_HASH','').strip()
    if h.count('$')==3: return h
    sifre=secrets.token_urlsafe(12); h=_hash_uret(sifre)
    try:
        os.makedirs(os.path.dirname(yol),exist_ok=True)
        for dosya,icerik in ((yol,h),(os.path.join(BASE_DIR,'data','ILK_SIFRE.txt'),'İlk giriş şifresi: '+sifre+'\nGirdikten sonra şifreni değiştir (python sifre_degistir.py) ve bu dosyayı sil.\n')):
            fd=os.open(dosya,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600); os.write(fd,icerik.encode()); os.close(fd)
    except OSError: pass
    print(f'\n*** İLK KURULUM: yönetici şifresi (bir kez gösterilir): {sifre}\n*** Değiştirmek için: python scripts/sifre_degistir.py\n',flush=True)
    return h
APP_PASSWORD_HASH=_hash_yukle()
# QR kodlarındaki herkese açık adres (alan adın). .env ile PUBLIC_BASE_URL=https://servis.ornek.com verilir.
# Boşsa o anki istek adresi kullanılır (yerel denemede çalışır; telefondan okutulacak QR için gerçek adres şart).
PUBLIC_BASE_URL=os.environ.get('PUBLIC_BASE_URL','').rstrip('/')
# ---- İşletme bilgileri (hepsi .env'den; koda dokunmadan değişir) ----
ISLETME_ADI=os.environ.get('ISLETME_ADI','Servis Defteri').strip() or 'Servis Defteri'
ISLETME_TEL=re.sub(r'[^0-9+ ]','',os.environ.get('ISLETME_TEL','')).strip()          # vitrinde arama/WhatsApp düğmeleri; boşsa gizlenir
ISLETME_ADRES=os.environ.get('ISLETME_ADRES','').strip()
ISLETME_ACIKLAMA=os.environ.get('ISLETME_ACIKLAMA','Arıza tespiti, periyodik bakım ve onarım. Sorunun kaynağını ilk seferde bulur, yaptığımız işi şeffafça gösteririz.').strip()
HARITA_EMBED_URL=os.environ.get('HARITA_EMBED_URL','').strip()                        # Google Haritalar > Paylaş > Harita yerleştir > src="..." adresi
HARITA_LINK=os.environ.get('HARITA_LINK','').strip()                                  # "Yol tarifi" düğmesi
ACILIS_SAATI=os.environ.get('ACILIS_SAATI','09:00').strip()
KAPANIS_SAATI=os.environ.get('KAPANIS_SAATI','19:00').strip()
SAAT_DILIMI=os.environ.get('SAAT_DILIMI','Europe/Istanbul').strip()
# PRINT_BRIDGE_URL kaldırıldı: artık Android Print Bridge yerine hazır
# 'ESC POS Bluetooth Print Service' uygulaması + Android'in yerleşik
# 'Telefon Yazdır' menüsü kullanılıyor. Ayrıca QR PNG olarak da indirilebiliyor.

# Yetkili servislerde yapılan işlemler ("İşlemler ve arama" paneli).
ISLEM_KATEGORILERI=[
 ('🛢️','Bakım ve sıvılar',['Periyodik bakım','Yağ değişimi','Yağ filtresi','Hava filtresi','Polen filtresi','Yakıt filtresi','Antifriz / soğutma','Fren hidroliği değişimi','Şanzıman yağı','Diferansiyel yağı','Direksiyon hidrolik yağı','Mevsimlik kontrol']),
 ('🛑','Fren',['Fren','Fren balatası','Fren diski','Fren kaliperi','El freni','ABS arızası','Fren hortumu / borusu']),
 ('⚙️','Motor',['Triger seti','Devirdaim','V kayışı / alternatör kayışı','Buji','Enjektör temizliği','Turbo','EGR / DPF temizliği','Silindir kapak contası','Motor takozu','Yağ kaçağı','Soğutma radyatörü','Termostat']),
 ('🔧','Alt takım ve direksiyon',['Direksiyon / süspansiyon','Amortisör','Helezon yayı','Rot / rotil','Z rot','Salıncak / burç','Tekerlek rulmanı','Aks / aks körüğü','Direksiyon kutusu','Rot balans']),
 ('🛞','Lastik ve jant',['Lastik değişimi','Balans','Lastik tamiri','Jant düzeltme','Lastik saklama','Rot ayarı']),
 ('⚡','Elektrik ve elektronik',['Akü','Marş / şarj','Alternatör','Elektrik arızası','Far / ampul','Silecek','Sensör','Bilgisayar / arıza kodu','Kilit / cam düğmesi']),
 ('❄️','Klima ve ısıtma',['Klima bakımı','Klima gazı','Klima kompresörü','Kalorifer']),
 ('🔩','Şanzıman ve debriyaj',['Debriyaj','Volan','Otomatik şanzıman bakımı','Şanzıman tamiri','Şaft']),
 ('💨','Egzoz',['Egzoz','Egzoz susturucu','Katalitik konvertör','Egzoz manifoldu','Egzoz contası']),
 ('🧰','Diğer',['Arıza tespiti','Genel kontrol','Muayene hazırlığı','LPG ayarı / bakımı','Kaporta / boya','Cam tamiri','Detaylı yıkama','Yol yardımı / çekici']),
]
DURUM_SECENEKLERI=['Beklemede','Devam Ediyor','Tamamlandı']
DURUM_RENK={'Beklemede':'warning','Devam Ediyor':'primary','Tamamlandı':'success'}
app=Flask(__name__); app.config['SECRET_KEY']=SECRET_KEY
# Cookie güvenliği: Cloudflare Tunnel HTTPS sağladığı için Secure=True varsayılan.
# Sadece yerel ağda http:// ile test ederken sorun çıkarsa, ortam değişkeniyle kapatılabilir:
#   FORCE_HTTPS_COOKIE=0 python3 app.py
app.config['SESSION_COOKIE_SECURE']=os.environ.get('FORCE_HTTPS_COOKIE','1')=='1'
app.config['SESSION_COOKIE_HTTPONLY']=True
app.config['SESSION_COOKIE_SAMESITE']='Lax'
app.config['PERMANENT_SESSION_LIFETIME']=60*60*24*90   # 90 gün; kullanıldıkça süre yenilenir -> usta her sabah şifre girmez, ancak 90 gün hiç açmazsa/çıkış yaparsa girer
app.config['SESSION_REFRESH_EACH_REQUEST']=True
app.config['MAX_CONTENT_LENGTH']=256*1024           # formlar küçük; büyük istekleri baştan reddet

# --- LOGLAMA: data/uygulama.log (1 MB x 3 dosya, sonra eskisi silinir; SD kartı doldurmaz) ---
import logging
from logging.handlers import RotatingFileHandler
def _log_kur():
    try:
        os.makedirs(os.path.join(BASE_DIR,'data'),exist_ok=True)
        h=RotatingFileHandler(os.path.join(BASE_DIR,'data','uygulama.log'),maxBytes=1_000_000,backupCount=3,encoding='utf-8')
        h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s')); h.setLevel(logging.INFO)
        app.logger.addHandler(h); app.logger.setLevel(logging.INFO)
    except OSError: pass
_log_kur()
def log_olay(mesaj): app.logger.info('%s | ip=%s',mesaj,client_ip())

@app.errorhandler(400)
def hata400(e):
    return render_template('hata.html',kod=400,baslik='İstek reddedildi',mesaj='Sayfa uzun süre açık kaldığı için oturum doğrulaması süresi dolmuş olabilir. Sayfayı yenileyip tekrar dene.'),400
@app.errorhandler(404)
def hata404(e): return render_template('hata.html',kod=404,baslik='Sayfa bulunamadı',mesaj='Aradığın sayfa yok ya da taşınmış.'),404
@app.errorhandler(413)
def hata413(e): return render_template('hata.html',kod=413,baslik='İstek çok büyük',mesaj='Gönderilen veri çok büyük.'),413
@app.errorhandler(500)
def hata500(e):
    app.logger.exception('Beklenmeyen hata: %s %s',request.method,request.path)
    return render_template('hata.html',kod=500,baslik='Bir hata oluştu',mesaj='Beklenmeyen bir sorun oldu. Tekrar dene; sürerse kayıtlar data/uygulama.log dosyasındadır.'),500

@app.errorhandler(sqlite3.Error)
def hata_db(e):
    app.logger.exception('Veritabanı hatası: %s %s',request.method,request.path)
    return render_template('hata.html',kod=500,baslik='Veritabanı hatası',mesaj='Kayıt yapılamadı. Tekrar dene; sürerse servisi yeniden başlat, olmazsa yedekten dön (data/yedekler).'),500
# Logo: static/logo.png (veya .svg/.webp/.jpg) dosyası varsa web sitesi, panel, giriş ve müşteri sayfasında otomatik görünür.
STATIC_DIR=os.path.join(BASE_DIR,'static')
@app.context_processor
def logo_bagla():
    # Marka bilgileri tüm şablonlara gelir. static/logo.(png|svg|webp|jpg) varsa üst çubukta o gösterilir,
    # yoksa işletme adı yazıyla gösterilir (ilk kelime beyaz, kalanı sarı).
    from markupsafe import Markup, escape
    p=ISLETME_ADI.split(' ',1)
    ad_html=Markup(escape(p[0])+(Markup(' <span class="amb">')+escape(p[1])+Markup('</span>') if len(p)>1 else Markup('')))
    ctx={'logo':'','now_yil':datetime.now().year,'public_base':PUBLIC_BASE_URL,'isletme':{'ad':ISLETME_ADI,'ad_html':ad_html,'tel':ISLETME_TEL,'tel_uluslararasi':_tel_uluslararasi(ISLETME_TEL),
         'adres':ISLETME_ADRES,'aciklama':ISLETME_ACIKLAMA,'harita_embed':HARITA_EMBED_URL,'harita_link':HARITA_LINK,'acilis':ACILIS_SAATI,'kapanis':KAPANIS_SAATI,'saat_dilimi':SAAT_DILIMI}}
    for uz in ('png','svg','webp','jpg','jpeg'):
        y=os.path.join(STATIC_DIR,'logo.'+uz)
        if os.path.exists(y): ctx['logo']=f'/static/logo.{uz}?v={int(os.path.getmtime(y))}'; break
    return ctx
def _tel_uluslararasi(t):
    d=re.sub(r'\D','',t or '')
    if not d: return ''
    if d.startswith('00'): d=d[2:]
    elif d.startswith('0'): d='90'+d[1:]
    return d
@app.route('/saglik')
def saglik():
    # Uptime servisleri için: veritabanı cevap veriyorsa "ok", yoksa 503. Veri döndürmez.
    try: get_db().execute('SELECT 1').fetchone(); return 'ok',200,{'Content-Type':'text/plain; charset=utf-8','Cache-Control':'no-store'}
    except Exception: app.logger.exception('Sağlık kontrolü başarısız'); return 'db hata',503

CSP=("default-src 'self'; script-src 'self' 'unsafe-inline'; "
     "style-src 'self' 'unsafe-inline'; "
     "font-src 'self' data:; img-src 'self' data: https:; frame-src https://www.google.com; "
     "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
@app.after_request
def guvenlik_basliklari(r):
    r.headers.setdefault('X-Content-Type-Options','nosniff')
    r.headers.setdefault('X-Frame-Options','DENY')
    r.headers.setdefault('Referrer-Policy','strict-origin-when-cross-origin')
    r.headers.setdefault('Permissions-Policy','camera=(), geolocation=(), payment=()')
    r.headers.setdefault('Content-Security-Policy',CSP)
    if request.path!='/': r.headers.setdefault('X-Robots-Tag','noindex, nofollow')   # panel ve müşteri QR sayfaları aramada çıkmasın
    if giris_var() and request.endpoint!='static': r.headers['Cache-Control']='no-store'          # çıkıştan sonra geri tuşuyla veri görünmesin
    return r

# --- BRUTE-FORCE / RATE LIMIT KORUMASI (yeni eklendi) ---
# Aynı IP'den 1 dakika içinde 5'ten fazla yanlış şifre denemesi olursa engellenir.
# Harici bir kütüphaneye ihtiyaç duymadan bellekte tutulan basit bir sayaç.
_login_attempts={}
def client_ip():
    # Cloudflare Tunnel arkasında remote_addr hep 127.0.0.1 olur; gerçek IP bu başlıkta gelir.
    # cloudflared isteği bu makineden (127.0.0.1) iletir; başlığa SADECE o zaman güven.
    # Ağdan doğrudan gelen biri sahte CF-Connecting-IP göndererek sınırı atlatamasın.
    ra=request.remote_addr or 'bilinmeyen'
    if ra in ('127.0.0.1','::1'): return request.headers.get('CF-Connecting-IP') or ra
    return ra
def is_rate_limited(ip):
    now_ts=time.time()
    if len(_login_attempts)>2000:   # bellek şişmesin
        for k in [k for k,v in _login_attempts.items() if not v or now_ts-v[-1]>60]: _login_attempts.pop(k,None)
    attempts=[t for t in _login_attempts.get(ip,[]) if now_ts-t<60]
    _login_attempts[ip]=attempts
    return len(attempts)>=5
def record_failed_attempt(ip):
    _login_attempts.setdefault(ip,[]).append(time.time())

# --- CSRF KORUMASI (yeni eklendi) ---
# Flask-WTF gibi ekstra bir bağımlılık eklemeden, session'a bağlı basit bir
# token mekanizması: her form bu token'ı gizli alan olarak taşımak zorunda,
# taşımayan/yanlış taşıyan POST istekleri reddediliyor.
def csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']
app.jinja_env.globals['csrf_token'] = csrf_token

@app.before_request
def csrf_protect():
    if request.method == 'POST':
        token = session.get('csrf_token')
        form_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        if not token or not form_token or not secrets.compare_digest(token, form_token):
            abort(400)

def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# --- TÜRKİYE PLAKA / TELEFON YARDIMCILARI ---
# Plaka standardı: il kodu (01-81) + 1-3 harf + 2-4 rakam, örn. "35 ABC 123".
# Veritabanında boşluksuz ve büyük harf saklanır (35ABC123); ekranda boşluklu gösterilir.
def tr_upper(t):
    # Türkçe büyük harf: i->İ, ı->I (Python'un upper()'ı i'yi I yapar, bu yanlış). Fazla boşlukları da temizler.
    return ' '.join(str(t or '').split()).replace('i','İ').replace('ı','I').upper()
_TR_HARF=str.maketrans('İıŞşÇçĞğÖöÜü','IiSsCcGgOoUu')
PLAKA_RE=re.compile(r'^(0[1-9]|[1-7][0-9]|8[01])[A-Z]{1,3}[0-9]{2,4}$')
TEL_RE=re.compile(r'^0[0-9]{10}$')
def temiz_plaka(p):
    return re.sub(r'[^0-9A-Z]','',str(p or '').translate(_TR_HARF).upper())
def temiz_tel(t):
    d=re.sub(r'\D','',str(t or ''))
    if d.startswith('90') and len(d)==12: d='0'+d[2:]
    elif len(d)==10 and d[0]!='0': d='0'+d
    return d
# --- ARAÇ FORMU LİSTELERİ ---
# Türkiye'de en yaygın markalar (elektrikli-only markalar bilerek yok). Model serbest metin.
MARKALAR=['Fiat','Renault','Volkswagen','Ford','Opel','Hyundai','Toyota','Peugeot','Citroën','Dacia','Honda','Skoda','Nissan','Seat','Mercedes-Benz','BMW','Audi','Kia','Mazda','Chevrolet','Suzuki','Mitsubishi','Volvo','Alfa Romeo','Mini','Jeep','Land Rover','Tofaş','Lada','Daewoo']
YAKITLAR=['Benzin','Dizel','Benzin + LPG']   # dizele LPG takılmadığı için LPG ayrı kutu değil, yakıt seçeneği
SANZIMANLAR=['Manuel','Otomatik','Yarı otomatik']
app.jinja_env.globals.update(MARKALAR=MARKALAR,YAKITLAR=YAKITLAR,SANZIMANLAR=SANZIMANLAR,yillar=lambda: list(range(datetime.now().year+1,1979,-1)))
def marka_al(f):
    m=(f.get('marka') or '').strip()
    if m=='__diger__': m=(f.get('marka_diger') or '').strip()
    return m[:40]
def yil_al(v):
    try:
        y=int(v); return y if 1950<=y<=datetime.now().year+1 else None
    except (TypeError,ValueError): return None
def plaka_like(q):
    t=temiz_plaka(q); return f'%{t}%' if t else f'%{q}%'
# --- İSTATİSTİK / HATIRLATMA AYARLARI (istersen sayıları değiştir) ---
BEKLEYEN_GUN=3          # bu kadar günden uzun açık duran iş emri "bekleyen" sayılır
BAKIM_GUN=182           # son periyodik bakımdan bu kadar gün (≈6 ay) geçen araçlar hatırlatma listesine girer
HATIRLATMA_BEKLEME=30   # "Hatırlattım" denen araç bu kadar gün listede çıkmaz
BAKIM_ANAHTAR=('periyodik','yag degisimi','yag filtresi')   # iş emrinde (harf/aksan duyarsız) bunlar geçiyorsa bakım sayılır: "Periyodik bakım", "Yağ değişimi", "Yağ filtresi"
def tr_baslik(t):
    # AHMET YILMAZ -> Ahmet Yılmaz (WhatsApp mesajı bağıran harflerle gitmesin)
    out=[]
    for w in str(t or '').split():
        low=w.replace('İ','i').replace('I','ı').lower()
        out.append((low[0].replace('i','İ').replace('ı','I').upper()+low[1:]) if low else w)
    return ' '.join(out)
def fold(t): return str(t or '').translate(_TR_HARF).lower()
def _wa(tel,mesaj):
    d=temiz_tel(tel)
    return ('https://wa.me/90'+d[1:]+'?text='+quote(mesaj)) if TEL_RE.match(d) else ''
@app.template_filter('plaka_goster')
def plaka_goster(p):
    s=temiz_plaka(p); m=re.match(r'^(\d{2})([A-Z]{1,3})(\d{2,4})$',s)
    return ' '.join(m.groups()) if m else (p or '')
@app.template_filter('zaman')
def zaman_filtre(v):
    # 2026-10-04 14:30:00 -> "04.10.2026 14:30" (her yerde aynı biçim)
    try: d=datetime.strptime(str(v)[:16],'%Y-%m-%d %H:%M')
    except ValueError: return v or '-'
    return d.strftime('%d.%m.%Y %H:%M')
@app.template_filter('gun_once')
def gun_once(v):
    try: return (datetime.now().date()-datetime.strptime(str(v)[:10],'%Y-%m-%d').date()).days
    except ValueError: return 0
@app.template_filter('wa_hazir')
def wa_hazir(r):
    return _wa(r['telefon'],f"Merhaba {tr_baslik(r['ad_soyad'])}, {plaka_goster(r['plaka'])} plakalı aracınız hazır, teslim alabilirsiniz. {ISLETME_ADI}")
@app.template_filter('wa_bakim')
def wa_bakim(r):
    return _wa(r['telefon'],f"Merhaba {tr_baslik(r['ad_soyad'])}, {plaka_goster(r['plaka'])} plakalı aracınızın son bakımının üzerinden {r['ay']} aydan fazla zaman geçti. Periyodik bakım için randevu almak isterseniz bu mesaja yazabilirsiniz. {ISLETME_ADI}")
@app.template_filter('tarih')
def f_tarih(v):
    try: return datetime.strptime(str(v)[:10],'%Y-%m-%d').strftime('%d.%m.%Y')
    except ValueError: return v or ''
@app.template_filter('ad_kisalt')
def f_ad_kisalt(ad):   # müşteri sayfasında isim maskelenir: Ahmet Yılmaz -> A***t Y****z (her kelimenin ilk ve son harfi açık)
    out=[]
    for w in tr_baslik(ad or '').split():
        out.append(w if len(w)==1 else w[0]+'*' if len(w)==2 else w[0]+'*'*(len(w)-2)+w[-1])
    return ' '.join(out)
@app.template_filter('wa_tel')
def f_wa_tel(tel): return _wa(tel,'')
@app.template_filter('tel_ara')
def f_tel_ara(tel):
    d=temiz_tel(tel); return ('tel:+90'+d[1:]) if TEL_RE.match(d) else ''
@app.template_filter('tel_goster')
def tel_goster(t):
    d=temiz_tel(t)
    return f'{d[:4]} {d[4:7]} {d[7:9]} {d[9:]}' if TEL_RE.match(d) else (t or '')
def verify_password(p):
    try:
        alg,it,salt_hex,dh=APP_PASSWORD_HASH.split('$'); salt=bytes.fromhex(salt_hex)
        got=hashlib.pbkdf2_hmac('sha256',p.encode(),salt,int(it)).hex()
        return secrets.compare_digest(got,dh)  # DÜZELTME: hashlib.compare_digest diye bir şey yok, doğrusu secrets/hmac.compare_digest
    except Exception: return False

def get_db():
    if 'db' not in g:
        g.db=sqlite3.connect(DB_PATH,timeout=10); g.db.row_factory=sqlite3.Row; g.db.execute('PRAGMA foreign_keys=ON'); g.db.execute('PRAGMA synchronous=NORMAL')
    return g.db
@app.teardown_appcontext
def close_db(e=None):
    db=g.pop('db',None)
    if db: db.close()

def addcol(c,t,n):
    try: c.execute(f'ALTER TABLE {t} ADD COLUMN {n}')
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower(): raise

COP_GUN=30   # silinen kayıtlar bu kadar gün çöp kutusunda saklanır
def init_db():
    os.makedirs(os.path.dirname(DB_PATH),exist_ok=True); os.makedirs(BACKUP_DIR,exist_ok=True)
    c=sqlite3.connect(DB_PATH); c.execute('PRAGMA journal_mode=WAL')
    c.executescript('''CREATE TABLE IF NOT EXISTS musteriler(id INTEGER PRIMARY KEY AUTOINCREMENT,ad_soyad TEXT NOT NULL,telefon TEXT,eposta TEXT,adres TEXT,notlar TEXT);
    CREATE TABLE IF NOT EXISTS araclar(id INTEGER PRIMARY KEY AUTOINCREMENT,musteri_id INTEGER NOT NULL,plaka TEXT NOT NULL UNIQUE,marka TEXT,model TEXT,model_yili INTEGER,kilometre INTEGER,yakit_tipi TEXT,sanziman TEXT,renk TEXT,lpg_durumu INTEGER NOT NULL DEFAULT 0,notlar TEXT,FOREIGN KEY(musteri_id) REFERENCES musteriler(id));
    CREATE TABLE IF NOT EXISTS is_emirleri(id INTEGER PRIMARY KEY AUTOINCREMENT,arac_id INTEGER NOT NULL,tarih TEXT NOT NULL,gelis_nedeni TEXT,durum TEXT NOT NULL DEFAULT 'Beklemede',notlar TEXT,FOREIGN KEY(arac_id) REFERENCES araclar(id));''')
    c.execute('CREATE TABLE IF NOT EXISTS cop(id INTEGER PRIMARY KEY AUTOINCREMENT,tablo TEXT NOT NULL,kayit_id INTEGER,ozet TEXT,veri TEXT NOT NULL,silindi_at TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS ozel_islem(id INTEGER PRIMARY KEY AUTOINCREMENT,ad TEXT NOT NULL UNIQUE COLLATE NOCASE,olusturuldu_at TEXT)')
    c.execute("DELETE FROM cop WHERE silindi_at<?",((datetime.now()-timedelta(days=COP_GUN)).strftime('%Y-%m-%d %H:%M:%S'),))
    for n in ['olusturuldu_at TEXT','guncellendi_at TEXT']: addcol(c,'musteriler',n)
    for n in ['qr_token TEXT','olusturuldu_at TEXT','guncellendi_at TEXT','hatirlatma_at TEXT']: addcol(c,'araclar',n)
    for n in ['gelis_at TEXT','giris_km INTEGER','gidis_at TEXT','olusturuldu_at TEXT','guncellendi_at TEXT','yapilan_islem TEXT','kaynak TEXT']: addcol(c,'is_emirleri',n)
    # backfill timestamps and QR tokens
    c.execute("UPDATE musteriler SET olusturuldu_at=COALESCE(olusturuldu_at,?) , guncellendi_at=COALESCE(guncellendi_at,?)",(now(),now()))
    rows=c.execute('SELECT id FROM araclar WHERE qr_token IS NULL OR qr_token=""').fetchall()
    for (i,) in rows: c.execute('UPDATE araclar SET qr_token=?,olusturuldu_at=COALESCE(olusturuldu_at,?),guncellendi_at=COALESCE(guncellendi_at,?) WHERE id=?',(secrets.token_urlsafe(18),now(),now(),i))
    c.execute("UPDATE araclar SET olusturuldu_at=COALESCE(olusturuldu_at,?),guncellendi_at=COALESCE(guncellendi_at,?)",(now(),now()))
    c.execute("UPDATE is_emirleri SET gelis_at=COALESCE(gelis_at,tarih||' 09:00:00'),olusturuldu_at=COALESCE(olusturuldu_at,tarih||' 09:00:00'),guncellendi_at=COALESCE(guncellendi_at,olusturuldu_at)")
    c.execute("UPDATE araclar SET yakit_tipi='Benzin + LPG' WHERE lpg_durumu=1 AND (yakit_tipi IS NULL OR yakit_tipi='' OR lower(yakit_tipi) IN ('benzin','benzinli','lpg'))")
    c.execute("UPDATE araclar SET yakit_tipi='Dizel' WHERE lower(yakit_tipi) IN ('dizel','diesel','motorin')")
    c.execute("UPDATE araclar SET yakit_tipi='Benzin' WHERE lower(yakit_tipi) IN ('benzin','benzinli')")
    c.execute("UPDATE araclar SET sanziman='Manuel' WHERE lower(sanziman) IN ('manuel','düz','duz','mekanik','manual')")
    c.execute("UPDATE araclar SET sanziman='Otomatik' WHERE lower(sanziman) IN ('otomatik','oto','automatic')")
    if c.execute('PRAGMA user_version').fetchone()[0]<2:
        c.execute('PRAGMA user_version=2')
    for i,ad in c.execute('SELECT id,ad_soyad FROM musteriler').fetchall():
        yeni=tr_upper(ad)
        if yeni and yeni!=ad: c.execute('UPDATE musteriler SET ad_soyad=? WHERE id=?',(yeni,i))
    # Eski kayıtlardaki "35 ABC 123" gibi plakaları 35ABC123'e çevir (çakışma olmazsa)
    mevcut={r[1] for r in c.execute('SELECT id,plaka FROM araclar')}
    for i,pl in c.execute('SELECT id,plaka FROM araclar').fetchall():
        yeni=temiz_plaka(pl)
        if yeni and yeni!=pl and yeni not in mevcut:
            c.execute('UPDATE araclar SET plaka=? WHERE id=?',(yeni,i)); mevcut.add(yeni)
    # İndeksler: QR sayfası, araç geçmişi ve panel sayaçları tüm tabloyu taramasın (veri büyüdükçe Pi'de fark eder)
    c.executescript('''CREATE INDEX IF NOT EXISTS ix_araclar_qr ON araclar(qr_token);
    CREATE INDEX IF NOT EXISTS ix_araclar_musteri ON araclar(musteri_id);
    CREATE INDEX IF NOT EXISTS ix_is_arac ON is_emirleri(arac_id,id);
    CREATE INDEX IF NOT EXISTS ix_is_durum ON is_emirleri(durum);
    CREATE INDEX IF NOT EXISTS ix_is_gelis ON is_emirleri(gelis_at);
    CREATE INDEX IF NOT EXISTS ix_is_gidis ON is_emirleri(gidis_at);''')
    c.commit(); c.close()

def _oturum_imza():
    # Şifre değişince VEYA "tüm cihazlardan çıkış" basılınca değişir -> eski oturumların hepsi geçersiz olur
    return hashlib.sha256((APP_PASSWORD_HASH+str(ayar_oku().get('oturum_surum',0))).encode()).hexdigest()[:16]
def giris_var(): return bool(session.get('giris_yapildi')) and session.get('sv')==_oturum_imza()
def login_required(v):
    @wraps(v)
    def w(*a,**kw):
        if not giris_var(): return redirect(url_for('login'))
        return v(*a,**kw)
    return w
@app.route('/login',methods=['GET','POST'])
def login():
    ip=client_ip()
    if request.method=='GET' and giris_var(): return redirect(url_for('dashboard'))
    if request.method=='POST':
        if is_rate_limited(ip):
            flash('Çok fazla yanlış deneme yaptın. 1 dakika bekleyip tekrar dene.','danger')
            return render_template('login.html')
        if verify_password(request.form.get('sifre','')):
            _login_attempts.pop(ip,None)
            session.clear(); session.permanent=True; session['giris_yapildi']=True; session['sv']=_oturum_imza()   # eski oturum içeriğini at (session fixation)
            log_olay('Giriş başarılı')
            return redirect(url_for('dashboard'))
        record_failed_attempt(ip); log_olay('Giriş başarısız')
        flash('Şifre hatalı.','danger')
    return render_template('login.html')
@app.route('/cikis-hepsi',methods=['POST'])
@login_required
def cikis_hepsi():
    ayar_yaz(oturum_surum=int(ayar_oku().get('oturum_surum',0))+1); log_olay('TÜM CİHAZLARDAN ÇIKIŞ'); session.clear()
    flash('Tüm cihazlardan çıkış yapıldı. Tekrar giriş yapabilirsin.','success'); return redirect(url_for('login'))
@app.route('/logout')
def logout(): log_olay('Çıkış'); session.clear(); return redirect(url_for('login'))
@app.route('/')
def anasayfa():
    # Herkese açık müşteri vitrini. Yönetim paneli artık /panel, giriş /login.
    return render_template('anasayfa.html')
@app.route('/panel')
@login_required
def dashboard():
    db=get_db(); bugun=datetime.now().strftime('%Y-%m-%d')+'%'
    acik,bugun_gelen,bugun_teslim=db.execute("SELECT COALESCE(SUM(durum!='Tamamlandı'),0),COALESCE(SUM(gelis_at LIKE ?),0),COALESCE(SUM(gidis_at LIKE ?),0) FROM is_emirleri",(bugun,bugun)).fetchone()
    toplam=[db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('musteriler','araclar','is_emirleri')]
    bugun_listesi=db.execute('''SELECT i.*,a.plaka,m.ad_soyad FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id JOIN musteriler m ON m.id=a.musteri_id WHERE i.gelis_at LIKE ? ORDER BY i.gelis_at DESC''',(bugun,)).fetchall()
    bekleyen_sayi=db.execute("SELECT COUNT(*) FROM is_emirleri WHERE durum!='Tamamlandı' AND substr(gelis_at,1,10)<=?",((datetime.now()-timedelta(days=BEKLEYEN_GUN)).strftime('%Y-%m-%d'),)).fetchone()[0]
    return render_template('dashboard.html',acik=acik,bugun_gelen=bugun_gelen,bugun_teslim=bugun_teslim,toplam=toplam,bugun_listesi=bugun_listesi,bekleyen_sayi=bekleyen_sayi,bekleyen_gun=BEKLEYEN_GUN,durum_renk=DURUM_RENK)
@app.route('/ara')
@login_required
def ara():
    q=request.args.get('q','').strip(); like=f'%{q}%'; likeu=f'%{tr_upper(q)}%'; db=get_db()
    ms=db.execute('SELECT * FROM musteriler WHERE ad_soyad LIKE ? OR telefon LIKE ? OR eposta LIKE ? ORDER BY id DESC LIMIT 30',(likeu,like,like)).fetchall()
    ars=db.execute('''SELECT a.*,m.ad_soyad,m.telefon FROM araclar a JOIN musteriler m ON m.id=a.musteri_id WHERE REPLACE(a.plaka,' ','') LIKE ? OR a.marka LIKE ? OR a.model LIKE ? OR m.ad_soyad LIKE ? OR m.telefon LIKE ? ORDER BY a.id DESC LIMIT 30''',(plaka_like(q),like,like,likeu,like)).fetchall()
    return render_template('search.html',q=q,ms=ms,ars=ars)
@app.route('/musteriler')
@login_required
def musteriler():
    q=request.args.get('q','').strip(); db=get_db(); like=f'%{q}%'; likeu=f'%{tr_upper(q)}%'
    rows=db.execute('SELECT * FROM musteriler WHERE ad_soyad LIKE ? OR telefon LIKE ? OR eposta LIKE ? ORDER BY id DESC',(likeu,like,like)).fetchall() if q else db.execute('SELECT * FROM musteriler ORDER BY id DESC').fetchall()
    plakalar={}; 
    for r in db.execute('SELECT musteri_id,plaka FROM araclar ORDER BY id'): plakalar.setdefault(r['musteri_id'],[]).append(r['plaka'])
    return render_template('musteriler.html',kayitlar=rows,q=q,plakalar=plakalar)
@app.route('/musteriler/<int:musteri_id>')
@login_required
def musteri_detay(musteri_id):
    db=get_db(); m=db.execute('SELECT * FROM musteriler WHERE id=?',(musteri_id,)).fetchone()
    if not m: abort(404)
    araclar_=db.execute('SELECT * FROM araclar WHERE musteri_id=? ORDER BY id',(musteri_id,)).fetchall()
    isler=db.execute("SELECT i.id,i.durum,i.gelis_at,i.gidis_at,i.yapilan_islem,i.gelis_nedeni,a.plaka FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id WHERE a.musteri_id=? ORDER BY COALESCE(i.gelis_at,i.tarih) DESC,i.id DESC LIMIT 15",(musteri_id,)).fetchall()
    is_say=db.execute('SELECT COUNT(*) FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id WHERE a.musteri_id=?',(musteri_id,)).fetchone()[0]
    return render_template('musteri_detay.html',m=m,araclar=araclar_,isler=isler,is_say=is_say)
# ===================== DIŞA AKTARMA (CSV — Excel'de çift tıkla açılır) =====================
import csv
from io import StringIO
def _csv_hucre(v):
    if v is None: return ''
    v=str(v)
    return "'"+v if v[:1] in ('=','+','-','@') else v    # Excel'de formül gibi çalışmasın
def _csv_yanit(ad,baslik,satirlar):
    o=StringIO(); w=csv.writer(o,delimiter=';',lineterminator='\r\n'); w.writerow(baslik)
    for r in satirlar: w.writerow([_csv_hucre(x) for x in r])
    veri=('\ufeff'+o.getvalue()).encode('utf-8')                # BOM: Türkçe karakterler Excel'de bozulmaz
    return Response(veri,mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="{ad}_{datetime.now().strftime("%Y-%m-%d")}.csv"','Cache-Control':'no-store'})
@app.route('/disa-aktar')
@login_required
def disa_aktar():
    db=get_db(); say={t:db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('musteriler','araclar','is_emirleri')}
    return render_template('disa_aktar.html',say=say)
@app.route('/disa-aktar/<tur>.csv')
@login_required
def disa_aktar_csv(tur):
    db=get_db()
    if tur=='musteriler':
        satir=[(r['id'],r['ad_soyad'],tel_goster(r['telefon']),r['eposta'],r['adres'],r['notlar'],r['olusturuldu_at']) for r in db.execute('SELECT * FROM musteriler ORDER BY ad_soyad')]
        return _csv_yanit('musteriler',['No','Ad Soyad','Telefon','E-posta','Adres','Not','Kayıt tarihi'],satir)
    if tur=='araclar':
        satir=[(r['plaka'] and plaka_goster(r['plaka']),r['ad_soyad'],tel_goster(r['telefon']),r['marka'],r['model'],r['model_yili'],r['kilometre'],r['yakit_tipi'],r['sanziman'],r['renk'],r['notlar']) for r in db.execute('SELECT a.*,m.ad_soyad,m.telefon FROM araclar a JOIN musteriler m ON m.id=a.musteri_id ORDER BY a.plaka')]
        return _csv_yanit('araclar',['Plaka','Müşteri','Telefon','Marka','Model','Model yılı','Kilometre','Yakıt','Şanzıman','Renk','Not'],satir)
    if tur=='is-emirleri':
        satir=[]
        for r in db.execute("SELECT i.*,a.plaka,m.ad_soyad,m.telefon FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id JOIN musteriler m ON m.id=a.musteri_id ORDER BY COALESCE(i.gelis_at,i.tarih),i.id"):
            satir.append((r['id'],zaman_filtre(r['gelis_at']) if r['gelis_at'] else '',zaman_filtre(r['gidis_at']) if r['gidis_at'] else '',plaka_goster(r['plaka']),r['ad_soyad'],tel_goster(r['telefon']),r['giris_km'],r['gelis_nedeni'],r['yapilan_islem'],r['durum'],r['notlar']))
        return _csv_yanit('is_emirleri',['No','Geliş','Teslim','Plaka','Müşteri','Telefon','Giriş KM','Geliş nedeni','Yapılan işlem','Durum','Not'],satir)
    abort(404)
@app.route('/musteriler/ekle',methods=['POST'])
@login_required
def musteri_ekle():
    ad=tr_upper(request.form.get('ad_soyad',''))
    if not ad: flash('Ad Soyad zorunludur.','danger'); return redirect(url_for('musteriler'))
    t=now(); db=get_db(); db.execute('INSERT INTO musteriler(ad_soyad,telefon,eposta,adres,notlar,olusturuldu_at,guncellendi_at) VALUES(?,?,?,?,?,?,?)',(ad,request.form.get('telefon','').strip(),request.form.get('eposta','').strip(),request.form.get('adres','').strip(),request.form.get('notlar','').strip(),t,t)); db.commit(); flash('Müşteri eklendi.','success'); return redirect(url_for('musteriler'))
@app.route('/musteriler/duzenle/<int:musteri_id>',methods=['GET','POST'])
@login_required
def musteri_duzenle(musteri_id):
    db=get_db(); row=db.execute('SELECT * FROM musteriler WHERE id=?',(musteri_id,)).fetchone()
    if not row: abort(404)
    if request.method=='POST':
        db.execute('UPDATE musteriler SET ad_soyad=?,telefon=?,eposta=?,adres=?,notlar=?,guncellendi_at=? WHERE id=?',(tr_upper(request.form.get('ad_soyad','')),request.form.get('telefon','').strip(),request.form.get('eposta','').strip(),request.form.get('adres','').strip(),request.form.get('notlar','').strip(),now(),musteri_id)); db.commit(); flash('Müşteri güncellendi.','success'); return redirect(url_for('musteriler'))
    return render_template('musteri_duzenle.html',m=row)
@app.route('/musteriler/sil/<int:musteri_id>',methods=['POST'])
@login_required
def musteri_sil(musteri_id):
    db=get_db()
    log_olay(f'SİL isteği: Müşteri #{musteri_id}')
    if db.execute('SELECT COUNT(*) FROM araclar WHERE musteri_id=?',(musteri_id,)).fetchone()[0]: flash('Bu müşteriye kayıtlı araçlar var; önce araçları silme yerine müşteriyi düzenle veya araçları başka müşteriye aktar.','danger'); return redirect(url_for('musteriler'))
    m=db.execute('SELECT * FROM musteriler WHERE id=?',(musteri_id,)).fetchone()
    if m: cop_at(db,'musteriler',m,f"{m['ad_soyad']} {m['telefon'] or ''}".strip())
    db.execute('DELETE FROM musteriler WHERE id=?',(musteri_id,)); db.commit(); flash('Müşteri silindi. (Silinenler sayfasından 30 gün içinde geri getirilebilir.)','success'); return redirect(url_for('musteriler'))
@app.route('/araclar')
@login_required
def araclar():
    q=request.args.get('q','').strip(); db=get_db(); like=f'%{q}%'; likeu=f'%{tr_upper(q)}%'
    sql='''SELECT a.*,m.ad_soyad,m.telefon FROM araclar a JOIN musteriler m ON m.id=a.musteri_id WHERE REPLACE(a.plaka,' ','') LIKE ? OR a.marka LIKE ? OR a.model LIKE ? OR m.ad_soyad LIKE ? OR m.telefon LIKE ? ORDER BY a.id DESC'''
    rows=db.execute(sql,(plaka_like(q),like,like,likeu,like)).fetchall() if q else db.execute('SELECT a.*,m.ad_soyad,m.telefon FROM araclar a JOIN musteriler m ON m.id=a.musteri_id ORDER BY a.id DESC').fetchall()
    ms=db.execute('SELECT id,ad_soyad FROM musteriler ORDER BY ad_soyad').fetchall(); return render_template('araclar.html',kayitlar=rows,musteri_listesi=ms,q=q)
@app.route('/araclar/ekle',methods=['POST'])
@login_required
def arac_ekle():
    f=request.form; p=temiz_plaka(f.get('plaka','')); mid=f.get('musteri_id','')
    if not p or not mid: flash('Plaka ve müşteri zorunludur.','danger'); return redirect(url_for('araclar'))
    if not f.get('ozel_plaka') and not PLAKA_RE.match(p): flash('Plaka biçimi geçersiz. Örnek: 35 ABC 123. Özel/yabancı plakaysa kutuyu işaretle.','danger'); return redirect(url_for('araclar'))
    yakit=f.get('yakit_tipi','').strip(); t=now(); db=get_db()
    try:
        db.execute('''INSERT INTO araclar(musteri_id,plaka,marka,model,model_yili,kilometre,yakit_tipi,sanziman,renk,lpg_durumu,notlar,qr_token,olusturuldu_at,guncellendi_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(mid,p,marka_al(f),f.get('model','').strip()[:40],yil_al(f.get('model_yili')),re.sub(r'\D','',f.get('kilometre','')) or None,yakit,f.get('sanziman','').strip(),f.get('renk','').strip()[:30],1 if 'LPG' in yakit.upper() else 0,f.get('notlar','').strip(),secrets.token_urlsafe(18),t,t)); db.commit(); flash(f'Araç eklendi: {plaka_goster(p)}','success')
    except sqlite3.IntegrityError: flash(f'{plaka_goster(p)} plakası zaten kayıtlı.','danger')
    return redirect(url_for('araclar'))
@app.route('/araclar/duzenle/<int:arac_id>',methods=['GET','POST'])
@login_required
def arac_duzenle(arac_id):
    db=get_db(); a=db.execute('SELECT * FROM araclar WHERE id=?',(arac_id,)).fetchone()
    if not a: abort(404)
    if request.method=='POST':
        f=request.form; p=temiz_plaka(f.get('plaka','')); yakit=f.get('yakit_tipi','').strip()
        if not p: flash('Plaka zorunludur.','danger'); return redirect(url_for('arac_duzenle',arac_id=arac_id))
        if not f.get('ozel_plaka') and not PLAKA_RE.match(p): flash('Plaka biçimi geçersiz. Örnek: 35 ABC 123. Özel/yabancı plakaysa kutuyu işaretle.','danger'); return redirect(url_for('arac_duzenle',arac_id=arac_id))
        try:
            db.execute('''UPDATE araclar SET musteri_id=?,plaka=?,marka=?,model=?,model_yili=?,kilometre=?,yakit_tipi=?,sanziman=?,renk=?,lpg_durumu=?,notlar=?,guncellendi_at=? WHERE id=?''',(f.get('musteri_id'),p,marka_al(f),f.get('model','').strip()[:40],yil_al(f.get('model_yili')),re.sub(r'\D','',f.get('kilometre','')) or None,yakit,f.get('sanziman','').strip(),f.get('renk','').strip()[:30],1 if 'LPG' in yakit.upper() else 0,f.get('notlar','').strip(),now(),arac_id)); db.commit(); flash('Araç güncellendi.','success'); return redirect(url_for('araclar'))
        except sqlite3.IntegrityError: flash(f'{plaka_goster(p)} plakası başka bir araçta kayıtlı.','danger'); return redirect(url_for('arac_duzenle',arac_id=arac_id))
    kayitlar=db.execute('SELECT id,durum,gelis_at,gidis_at,giris_km,COALESCE(NULLIF(yapilan_islem,\'\'),NULLIF(gelis_nedeni,\'\'),\'-\') islem FROM is_emirleri WHERE arac_id=? ORDER BY gelis_at DESC,id DESC',(arac_id,)).fetchall()
    return render_template('arac_duzenle.html',kayitlar=kayitlar,a=a,musteri_listesi=db.execute('SELECT id,ad_soyad FROM musteriler ORDER BY ad_soyad').fetchall())
@app.route('/araclar/sil/<int:arac_id>',methods=['POST'])
@login_required
def arac_sil(arac_id):
    db=get_db()
    log_olay(f'SİL isteği: Araç #{arac_id}')
    if db.execute('SELECT COUNT(*) FROM is_emirleri WHERE arac_id=?',(arac_id,)).fetchone()[0]: flash('Bu araca ait iş emirleri var; silmek yerine düzenleyebilirsin.','danger'); return redirect(url_for('araclar'))
    a=db.execute('SELECT * FROM araclar WHERE id=?',(arac_id,)).fetchone()
    if a: cop_at(db,'araclar',a,plaka_goster(a['plaka']))
    db.execute('DELETE FROM araclar WHERE id=?',(arac_id,)); db.commit(); flash('Araç silindi. (Silinenler sayfasından 30 gün içinde geri getirilebilir.)','success'); return redirect(url_for('araclar'))
@app.route('/arac/<token>')
def qr_arac(token):
    # Herkese açık servis karnesi. Giriş yok; telefon, iç not GÖSTERİLMEZ (sadece güvenli alanlar seçilir).
    db=get_db(); usta=giris_var()    # telefon yalnızca giriş yapmış usta için çekilir; herkese açık sorguda yok
    a=db.execute('''SELECT a.id,a.plaka,a.marka,a.model,a.model_yili,a.yakit_tipi,a.sanziman,a.kilometre,m.ad_soyad'''+(',m.telefon' if usta else '')+''' FROM araclar a JOIN musteriler m ON m.id=a.musteri_id WHERE a.qr_token=?''',(token,)).fetchone()
    if not a: abort(404)
    toplam=db.execute('SELECT COUNT(*) FROM is_emirleri WHERE arac_id=?',(a['id'],)).fetchone()[0]
    hs=db.execute('SELECT id,durum,gelis_at,gidis_at,yapilan_islem,gelis_nedeni,giris_km FROM is_emirleri WHERE arac_id=? ORDER BY gelis_at DESC,id DESC LIMIT 300',(a['id'],)).fetchall()
    acik_id=next((h['id'] for h in hs if h['durum']!='Tamamlandı'),None)
    # giriş yapmış usta kendi telefonuyla okutursa müşteriyi arama/haber verme düğmelerini görür; herkese açık sayfada telefon HİÇ yok
    musteri_wa=_wa(a['telefon'],f"Merhaba {tr_baslik(a['ad_soyad'])}, {plaka_goster(a['plaka'])} plakalı aracınız hazır, teslim alabilirsiniz. {ISLETME_ADI}") if usta else ''
    return render_template('qr_arac.html',a=a,hs=hs,usta=usta,acik_id=acik_id if usta else None,
        yeni_url=url_for('is_emirleri',yeni=a['plaka'])+'#yeni' if usta else '',geri=url_for('qr_arac',token=token) if usta else '',musteri_tel=f_tel_ara(a['telefon']) if usta else '',musteri_wa=musteri_wa,toplam=toplam,site=(PUBLIC_BASE_URL or request.host_url.rstrip('/')).replace('https://','').replace('http://',''))
def public_url(a): return (PUBLIC_BASE_URL or request.url_root.rstrip('/'))+'/arac/'+a['qr_token']
@app.route('/arac/<int:arac_id>/qr')
@login_required
def arac_qr(arac_id):
    a=get_db().execute('SELECT a.*,m.ad_soyad FROM araclar a JOIN musteriler m ON m.id=a.musteri_id WHERE a.id=?',(arac_id,)).fetchone()
    if not a: abort(404)
    return render_template('qr_print.html',a=a,yeni=bool(request.args.get('yeni')))

# YENİ: QR'ı sunucu tarafında gerçek bir PNG olarak üretip döndürür.
# Önceki sürüm istemci tarafında (JavaScript ile) qrcodejs kütüphanesinin
# oluşturduğu <img>/<canvas>'ı "kazımaya" çalışıyordu; bu kırılgandı ve
# bazı durumlarda PNG yerine sayfanın kendisini indiriyordu. Artık QR
# görüntüsü doğrudan sunucudan gerçek image/png baytları olarak geliyor,
# hem sayfada gösterim hem indirme için aynı URL kullanılıyor.
@app.route('/araclar/<int:arac_id>/qr.png')
@login_required
def arac_qr_png(arac_id):
    a=get_db().execute('SELECT * FROM araclar WHERE id=?',(arac_id,)).fetchone()
    if not a: abort(404)
    img=qrcode.make(public_url(a), box_size=10, border=4)
    buf=BytesIO(); img.save(buf, format='PNG'); buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png')
# ===================== QR ETİKETİ =====================
# Etiket üretimi ve yazdırma etiket_yazici.py içinde (TSPL; tek tür: 58x40 yatay).
# Etikette telefon YOK. Etiket başlığı ETIKET_BASLIK (yoksa SERVIS DEFTERI) ile değişir.
SEKMELER=('acik','tamam','hepsi')
def _sekme(v=None):
    v=v if v is not None else (request.form.get('g') or request.args.get('g'))
    return v if v in SEKMELER else 'acik'
VARSAYILAN_SIK=['Periyodik bakım','Yağ değişimi','Yağ filtresi','Fren balatası','Lastik değişimi','Akü','Klima bakımı','Arıza tespiti']
def tum_islemler(db):
    liste=[c for _,_,l in ISLEM_KATEGORILERI for c in l]
    return liste+[r[0] for r in db.execute('SELECT ad FROM ozel_islem ORDER BY id')]
def sik_islemler(db,n=8):
    # Son 180 günün iş emirlerinden en çok yapılan işlemler; yetmezse varsayılanlarla tamamlanır.
    kanon={x.lower():x for x in tum_islemler(db)}; sayac={}
    esik=(datetime.now()-timedelta(days=180)).strftime('%Y-%m-%d')
    for (gx,) in db.execute("SELECT COALESCE(NULLIF(yapilan_islem,''),gelis_nedeni) FROM is_emirleri WHERE COALESCE(NULLIF(yapilan_islem,''),gelis_nedeni) IS NOT NULL AND COALESCE(gelis_at,tarih)>=?",(esik,)):
        for p in gx.split(','):
            p=p.strip().lower()
            if p in kanon: sayac[kanon[p]]=sayac.get(kanon[p],0)+1
    sik=[a for a,_ in sorted(sayac.items(),key=lambda x:(-x[1],x[0]))][:n]
    for v in VARSAYILAN_SIK:
        if len(sik)>=n: break
        if v not in sik: sik.append(v)
    return sik
def is_emirleri_render(form=None,hata=None,status=200):
    if form is None and request.args.get('yeni'): form={'plaka':request.args['yeni'][:14]}   # ?yeni=35ABC123 -> plaka dolu gelir
    db=get_db(); q=request.args.get('q','').strip(); sekme=_sekme(); like=f'%{q}%'; likeu=f'%{tr_upper(q)}%'; likep=f'%{temiz_plaka(q)}%' if temiz_plaka(q) else like
    base='''SELECT i.*,a.plaka,m.ad_soyad,m.telefon FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id JOIN musteriler m ON m.id=a.musteri_id'''
    if q:   # arama her zaman tüm kayıtlarda yapılır
        rows=db.execute(base+" WHERE REPLACE(a.plaka,' ','') LIKE ? OR m.ad_soyad LIKE ? OR i.gelis_nedeni LIKE ? ORDER BY i.id DESC LIMIT 200",(likep,likeu,like)).fetchall()
    elif sekme=='acik':   # çalışılan işler en üstte, sonra bekleyenler
        rows=db.execute(base+" WHERE i.durum!='Tamamlandı' ORDER BY CASE i.durum WHEN 'Devam Ediyor' THEN 0 ELSE 1 END, i.id DESC").fetchall()
    elif sekme=='tamam':
        rows=db.execute(base+" WHERE i.durum='Tamamlandı' ORDER BY i.gidis_at DESC, i.id DESC LIMIT 100").fetchall()
    else:
        rows=db.execute(base+' ORDER BY i.id DESC LIMIT 200').fetchall()
    acik_sayi=db.execute("SELECT COUNT(*) FROM is_emirleri WHERE durum!='Tamamlandı'").fetchone()[0]
    return render_template('isemirleri.html',kayitlar=rows,islem_kategorileri=ISLEM_KATEGORILERI,sik_islemler=sik_islemler(db),ozel_islemler=[r[0] for r in db.execute('SELECT ad FROM ozel_islem ORDER BY id')],durum_renk=DURUM_RENK,q=q,form=form or {},hata=hata,sekme=sekme,acik_sayi=acik_sayi,bekleyen_gun=BEKLEYEN_GUN),status
@app.route('/is-emirleri')
@login_required
def is_emirleri(): return is_emirleri_render()
def _geri_url(v): return v if isinstance(v,str) and v.startswith('/arac/') and '//' not in v and len(v)<80 else None
@app.route('/is-emirleri/duzenle/<int:is_emri_id>',methods=['GET','POST'])
@login_required
def is_emri_duzenle(is_emri_id):
    geri=_geri_url(request.values.get('geri'))
    db=get_db(); i=db.execute('SELECT * FROM is_emirleri WHERE id=?',(is_emri_id,)).fetchone()
    if not i: abort(404)
    araclar_=lambda: db.execute('SELECT a.id,a.plaka,m.ad_soyad FROM araclar a JOIN musteriler m ON m.id=a.musteri_id ORDER BY a.plaka').fetchall()
    if request.method=='POST':
        f=request.form; ga=f.get('gelis_at') or i['gelis_at']; gi=f.get('gidis_at') or None; durum=f.get('durum')
        if durum not in DURUM_SECENEKLERI: flash('Geçersiz durum.','danger'); return redirect(url_for('is_emri_duzenle',is_emri_id=is_emri_id,geri=geri))
        if not db.execute('SELECT 1 FROM araclar WHERE id=?',(f.get('arac_id'),)).fetchone(): flash('Geçersiz araç.','danger'); return redirect(url_for('is_emri_duzenle',is_emri_id=is_emri_id,geri=geri))
        ga=ga.replace('T',' ');  gi=gi.replace('T',' ') if gi else None
        if gi and len(gi)==16: gi+=':00'
        if len(ga)==16: ga+=':00'
        if durum=='Tamamlandı' and not gi: gi=now()      # tamamlandıysa teslim zamanı boş kalmasın
        if durum!='Tamamlandı': gi=None                   # yeniden açılan iş emrinde eski teslim zamanı kalmasın
        km=re.sub(r'\D','',f.get('giris_km','')) or None
        db.execute('''UPDATE is_emirleri SET arac_id=?,gelis_at=?,giris_km=?,gidis_at=?,gelis_nedeni=?,yapilan_islem=?,durum=?,notlar=?,guncellendi_at=?,tarih=? WHERE id=?''',(f.get('arac_id'),ga,km,gi,f.get('gelis_nedeni','').strip()[:500],f.get('yapilan_islem','').strip()[:500] or None,durum,f.get('notlar','').strip()[:1000],now(),ga[:10],is_emri_id)); db.commit(); flash('İş emri güncellendi.','success'); return redirect(geri or url_for('is_emirleri'))
    return render_template('is_emri_duzenle.html',i=i,geri=geri,sik_islemler=sik_islemler(db),ozel_islemler=[r[0] for r in db.execute('SELECT ad FROM ozel_islem ORDER BY id')],islem_kategorileri=ISLEM_KATEGORILERI,arac_listesi=araclar_(),durum_secenekleri=DURUM_SECENEKLERI)
@app.route('/is-emirleri/durum/<int:is_emri_id>',methods=['POST'])
@login_required
def is_emri_durum_guncelle(is_emri_id):
    f=request.form; d=f.get('durum'); db=get_db()
    g=_sekme()
    if d not in DURUM_SECENEKLERI: flash('Geçersiz durum.','danger'); return redirect(url_for('is_emirleri',g=g))
    pl=db.execute('SELECT a.plaka FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id WHERE i.id=?',(is_emri_id,)).fetchone()
    if not pl: abort(404)
    t=now()
    # Tamamlandı'ya geçince teslim zamanı yazılır (varsa korunur); başka duruma dönülürse teslim zamanı temizlenir.
    db.execute("UPDATE is_emirleri SET durum=?,gidis_at=CASE WHEN ?='Tamamlandı' THEN COALESCE(gidis_at,?) ELSE NULL END,guncellendi_at=? WHERE id=?",(d,d,t,t,is_emri_id))
    log_olay(f'İş emri #{is_emri_id} durumu: {d}')
    db.commit()
    flash(f"{plaka_goster(pl['plaka'])}: {({'Beklemede':'beklemeye alındı','Devam Ediyor':'işe başlandı','Tamamlandı':'teslim edildi'})[d]}",'success')
    return redirect(url_for('is_emirleri',g=g)+'#liste')
@app.route('/is-emirleri/sil/<int:is_emri_id>',methods=['POST'])
@login_required
def is_emri_sil(is_emri_id):
    db=get_db(); log_olay(f'SİL: İş emri #{is_emri_id}')
    i=db.execute('SELECT i.*,a.plaka FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id WHERE i.id=?',(is_emri_id,)).fetchone()
    if i:
        v={k:i[k] for k in i.keys() if k!='plaka'}; cop_at(db,'is_emirleri',v,f"{plaka_goster(i['plaka'])} · {(i['yapilan_islem'] or i['gelis_nedeni'] or 'İşlem belirtilmemiş')[:60]} · {(i['gelis_at'] or '')[:10]}")
    db.execute('DELETE FROM is_emirleri WHERE id=?',(is_emri_id,)); db.commit(); flash('İş emri silindi. (Silinenler sayfasından 30 gün içinde geri getirilebilir.)','success'); return redirect(url_for('is_emirleri'))

# ===================== USB ETİKET YAZICI (ham TSPL, bkz. etiket_yazici.py) =====================
AYAR_DOSYA=os.path.join(BASE_DIR,'data','ayarlar.json')
def ayar_oku():
    try:
        with open(AYAR_DOSYA,encoding='utf-8') as f: return json.load(f)
    except (OSError,ValueError): return {}
def ayar_yaz(**kv):
    a=ayar_oku(); a.update(kv); gecici=AYAR_DOSYA+'.tmp'
    with open(gecici,'w',encoding='utf-8') as f: json.dump(a,f)
    os.replace(gecici,AYAR_DOSYA)       # yarım dosya kalmasın
def _yazdir_cevap(ok,mesaj,**ek):
    if request.headers.get('X-Requested-With')=='fetch' or request.is_json or 'application/json' in request.headers.get('Accept',''):
        return jsonify(ok=ok,mesaj=mesaj,**ek),(200 if ok else 503)
    flash(mesaj,'success' if ok else 'danger'); return redirect(request.referrer or url_for('araclar'))
@app.route('/araclar/<int:arac_id>/yazdir',methods=['POST'])
@login_required
def arac_yazdir(arac_id):
    a=get_db().execute('SELECT a.plaka,a.qr_token FROM araclar a WHERE a.id=?',(arac_id,)).fetchone()
    if not a: abort(404)
    try: adet=int(request.form.get('adet','1') or 1)
    except ValueError: adet=1
    ok,mesaj=EY.etiket_bas(a['plaka'],public_url(a),adet=adet)
    log_olay(f'Etiket {"basıldı" if ok else "BASILAMADI"}: {a["plaka"]} – {mesaj}')
    return _yazdir_cevap(ok,mesaj,plaka=plaka_goster(a['plaka']))
@app.route('/yazici/durum')
@login_required
def yazici_durum(): return jsonify(**EY.yazici_durumu())
@app.route('/araclar/<int:arac_id>/etiket_onizleme.png')
@login_required
def arac_etiket_onizleme(arac_id):
    a=get_db().execute('SELECT plaka,qr_token FROM araclar WHERE id=?',(arac_id,)).fetchone()
    if not a: abort(404)
    return Response(EY.onizleme_png(EY.tspl_komutlari(a['plaka'],public_url(a))),mimetype='image/png')

# ===================== YARDIMCILAR (API) =====================
def api_login_required(v):
    # Sayfa yönlendirmesi yerine JSON 401 döner (fetch ile çağrıldığı için).
    @wraps(v)
    def w(*a,**kw):
        if not giris_var(): return jsonify(ok=False,hata='Oturum süresi dolmuş. Sayfayı yenileyip tekrar giriş yap.'),401
        return v(*a,**kw)
    return w

# ===================== HIZLI İŞ EMRİ (tek ekran) =====================
def arac_bul(db,plaka):
    sel="SELECT a.*,m.ad_soyad,m.telefon FROM araclar a JOIN musteriler m ON m.id=a.musteri_id WHERE "
    r=db.execute(sel+"a.plaka=?",(plaka,)).fetchone()       # plakalar normalize saklanır -> UNIQUE indeksle anında
    return r or db.execute(sel+"REPLACE(REPLACE(a.plaka,' ',''),'-','')=?",(plaka,)).fetchone()   # normalize edilememiş eski kayıt için
def musteri_bul_tel(db,tel):
    for m in db.execute("SELECT id,ad_soyad,telefon FROM musteriler WHERE telefon IS NOT NULL AND telefon!=''"):
        if temiz_tel(m['telefon'])==tel: return m
    return None

@app.route('/api/islem-ekle',methods=['POST'])
@api_login_required
def api_islem_ekle():
    ad=re.sub(r'\s+',' ',((request.get_json(silent=True) or {}).get('ad') or '')).strip().strip(',')[:40]
    if len(ad)<2: return jsonify(ok=False,hata='En az 2 harf yaz.'),400
    ad=ad[:1].replace('i','İ').upper()+ad[1:]
    db=get_db(); var={x.lower():x for x in tum_islemler(db)}
    if ad.lower() in var: return jsonify(ok=True,ad=var[ad.lower()],yeni=False)
    db.execute('INSERT OR IGNORE INTO ozel_islem(ad,olusturuldu_at) VALUES(?,?)',(ad,now())); db.commit(); log_olay(f'Yeni işlem eklendi: {ad}')
    return jsonify(ok=True,ad=ad,yeni=True)
@app.route('/api/islem-sil',methods=['POST'])
@api_login_required
def api_islem_sil():
    ad=re.sub(r'\s+',' ',((request.get_json(silent=True) or {}).get('ad') or '')).strip()
    if not ad: return jsonify(ok=False,hata='Geçersiz işlem.'),400
    db=get_db(); c=db.execute('DELETE FROM ozel_islem WHERE ad=? COLLATE NOCASE',(ad,))
    db.commit()
    if c.rowcount: log_olay(f'Eklenen işlem silindi: {ad}')
    return jsonify(ok=True,silindi=bool(c.rowcount))
@app.route('/api/plaka/<plaka>')
@api_login_required
def api_plaka(plaka):
    p=temiz_plaka(plaka); db=get_db(); a=arac_bul(db,p) if p else None
    if not a: return jsonify(bulundu=False,plaka=p)
    acik=db.execute("SELECT COUNT(*) FROM is_emirleri WHERE arac_id=? AND durum!='Tamamlandı'",(a['id'],)).fetchone()[0]
    son=db.execute("SELECT gelis_at,COALESCE(NULLIF(yapilan_islem,''),NULLIF(gelis_nedeni,'')) islem,giris_km FROM is_emirleri WHERE arac_id=? ORDER BY id DESC LIMIT 1",(a['id'],)).fetchone()
    return jsonify(bulundu=True,plaka=p,musteri_adi=a['ad_soyad'],telefon=tel_goster(a['telefon']),marka=a['marka'] or '',model=a['model'] or '',acik_is_emri=acik,
        son_gelis=(datetime.strptime(son['gelis_at'][:10],'%Y-%m-%d').strftime('%d.%m.%Y') if son and son['gelis_at'] else None),
        son_islem=(son['islem'] if son else None),son_km=(son['giris_km'] if son else None) or a['kilometre'])

@app.route('/is-emirleri/hizli',methods=['POST'])
@login_required
def is_emri_hizli():
    f=request.form
    form={k:f.get(k,'').strip() for k in ['plaka','musteri_ad','telefon','gelis_nedeni','marka','marka_diger','model','giris_km','notlar']}
    ozel=bool(f.get('ozel_plaka')); form['ozel_plaka']=ozel
    def hata(m): return is_emirleri_render(form,m,400)
    plaka=temiz_plaka(form['plaka'])
    if not plaka: return hata('Plaka gerekli.')
    if not ozel and not PLAKA_RE.match(plaka): return hata('Plaka biçimi geçersiz. Örnek: 35 ABC 123 (il kodu 01-81, 1-3 harf, 2-4 rakam). Özel/yabancı plakaysa kutuyu işaretle.')
    if len(plaka)>12: return hata('Plaka çok uzun.')
    km=re.sub(r'\D','',form['giris_km']) or None
    db=get_db(); t=now(); yeni_arac=yeni_musteri=False; notu=''
    try:
        a=arac_bul(db,plaka)
        if a:
            arac_id=a['id']; ad=a['ad_soyad']
            tel=temiz_tel(form['telefon'])
            if TEL_RE.match(tel) and not (a['telefon'] or '').strip():
                db.execute('UPDATE musteriler SET telefon=?,guncellendi_at=? WHERE id=?',(tel,t,a['musteri_id']))
        else:
            ad=tr_upper(form['musteri_ad'])[:100]; tel=temiz_tel(form['telefon'])
            if not ad: return hata('Müşteri adı gerekli.')
            if not TEL_RE.match(tel): return hata('Telefon geçersiz. Örnek: 0532 111 22 33')
            m=musteri_bul_tel(db,tel)
            if m: mid=m['id']; notu=f' (telefon {m["ad_soyad"]} adına kayıtlıydı, araç ona eklendi)'; ad=m['ad_soyad']
            else:
                mid=db.execute('INSERT INTO musteriler(ad_soyad,telefon,olusturuldu_at,guncellendi_at) VALUES(?,?,?,?)',(ad,tel,t,t)).lastrowid; yeni_musteri=True
            arac_id=db.execute('INSERT INTO araclar(musteri_id,plaka,marka,model,kilometre,lpg_durumu,qr_token,olusturuldu_at,guncellendi_at) VALUES(?,?,?,?,?,0,?,?,?)',(mid,plaka,marka_al(form),form['model'][:40],km,secrets.token_urlsafe(18),t,t)).lastrowid; yeni_arac=True
        if km: db.execute('UPDATE araclar SET kilometre=?,guncellendi_at=? WHERE id=?',(km,t,arac_id))
        db.execute('INSERT INTO is_emirleri(arac_id,tarih,gelis_nedeni,durum,notlar,gelis_at,giris_km,olusturuldu_at,guncellendi_at,kaynak) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (arac_id,t[:10],form['gelis_nedeni'][:500],'Beklemede',form['notlar'][:1000],t,km,t,t,'form'))
        db.commit()
    except sqlite3.Error:
        db.rollback(); app.logger.exception('Hızlı iş emri DB hatası')
        return hata('Kaydedilemedi (veritabanı hatası). Tekrar dene.')
    if yeni_arac:    # yeni araç: doğrudan "Etiketi çıkar" ekranı (usta tek dokunuşla etiketi basar)
        return redirect(url_for('arac_qr',arac_id=arac_id,yeni=1))
    flash(f'İş emri açıldı: {plaka_goster(plaka)} — {ad}'+notu,'success')
    return redirect(url_for('is_emirleri'))

# ===================== ÇÖP KUTUSU (silinenleri geri getir) =====================
TABLO_AD={'is_emirleri':'📋 İş emri','araclar':'🚗 Araç','musteriler':'👤 Müşteri'}
def cop_at(db,tablo,satir,ozet):
    d=dict(satir) if not isinstance(satir,dict) else satir
    db.execute('INSERT INTO cop(tablo,kayit_id,ozet,veri,silindi_at) VALUES(?,?,?,?,?)',(tablo,d.get('id'),ozet,json.dumps(d,ensure_ascii=False),now()))
@app.route('/silinenler')
@login_required
def silinenler():
    db=get_db(); db.execute("DELETE FROM cop WHERE silindi_at<?",((datetime.now()-timedelta(days=COP_GUN)).strftime('%Y-%m-%d %H:%M:%S'),)); db.commit()
    return render_template('silinenler.html',satirlar=db.execute('SELECT * FROM cop ORDER BY id DESC LIMIT 200').fetchall(),tablo_ad=TABLO_AD,cop_gun=COP_GUN)
@app.route('/silinenler/<int:cop_id>/geri',methods=['POST'])
@login_required
def cop_geri(cop_id):
    db=get_db(); r=db.execute('SELECT * FROM cop WHERE id=?',(cop_id,)).fetchone()
    if not r or r['tablo'] not in TABLO_AD: abort(404)
    try: veri=json.loads(r['veri'])
    except ValueError: abort(404)
    kolonlar=[x[1] for x in db.execute(f'PRAGMA table_info({r["tablo"]})')]; k=[c for c in kolonlar if c in veri]
    try:
        db.execute(f'INSERT INTO {r["tablo"]}({",".join(k)}) VALUES({",".join("?"*len(k))})',[veri[c] for c in k])
        db.execute('DELETE FROM cop WHERE id=?',(cop_id,)); db.commit(); log_olay(f'GERİ GETİRİLDİ: {r["tablo"]} #{r["kayit_id"]}'); flash(f'Geri getirildi: {r["ozet"]}','success')
    except sqlite3.IntegrityError:
        db.rollback()
        flash('Geri getirilemedi: bağlı kayıt (araç/müşteri) silinmiş veya aynı plaka/numara başka kayıtta var. Önce bağlı kaydı geri getir.','danger')
    return redirect(url_for('silinenler'))

# ===================== İSTATİSTİK =====================
GUN_AD=['Pzt','Sal','Çar','Per','Cum','Cmt','Paz']
@app.route('/istatistik')
@login_required
def istatistik():
    db=get_db(); simdi=datetime.now(); bugun=simdi.strftime('%Y-%m-%d')
    # --- bugün kartları ---
    gelen=db.execute('SELECT COUNT(*) FROM is_emirleri WHERE substr(gelis_at,1,10)=?',(bugun,)).fetchone()[0]
    tamam=db.execute("SELECT COUNT(*) FROM is_emirleri WHERE durum='Tamamlandı' AND substr(gidis_at,1,10)=?",(bugun,)).fetchone()[0]
    acik={r['durum']:r['n'] for r in db.execute("SELECT durum,COUNT(*) n FROM is_emirleri WHERE durum!='Tamamlandı' GROUP BY durum")}
    # --- dönem ---
    donem=request.args.get('donem','7')
    if donem not in ('bugun','7','30','ay'): donem='7'
    bas={'bugun':simdi,'7':simdi-timedelta(days=6),'30':simdi-timedelta(days=29),'ay':simdi.replace(day=1)}[donem]
    bas_s=bas.strftime('%Y-%m-%d')
    g={r['d']:r['n'] for r in db.execute("SELECT substr(gelis_at,1,10) d,COUNT(*) n FROM is_emirleri WHERE substr(gelis_at,1,10)>=? GROUP BY d",(bas_s,))}
    t={r['d']:r['n'] for r in db.execute("SELECT substr(gidis_at,1,10) d,COUNT(*) n FROM is_emirleri WHERE durum='Tamamlandı' AND substr(gidis_at,1,10)>=? GROUP BY d",(bas_s,))}
    gunler=[]; d=simdi.date()
    while d>=bas.date():
        k=d.strftime('%Y-%m-%d'); gunler.append({'tarih':d.strftime('%d.%m'),'gun':GUN_AD[d.weekday()],'gelen':g.get(k,0),'tamam':t.get(k,0),'bugun':k==bugun}); d-=timedelta(days=1)
    mx=max([x['gelen'] for x in gunler]+[x['tamam'] for x in gunler]+[1])
    # --- bekleyen (uzun süredir açık) işler ---
    limit=(simdi-timedelta(days=BEKLEYEN_GUN)).strftime('%Y-%m-%d')
    bekleyen=[dict(r,gun=(simdi.date()-datetime.strptime(r['gelis_at'][:10],'%Y-%m-%d').date()).days) for r in db.execute("SELECT i.id,i.durum,i.gelis_at,i.gelis_nedeni,a.plaka,m.ad_soyad,m.telefon FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id JOIN musteriler m ON m.id=a.musteri_id WHERE i.durum!='Tamamlandı' AND substr(i.gelis_at,1,10)<=? ORDER BY i.gelis_at",(limit,))]
    # --- bakım hatırlatma: son periyodik bakımı BAKIM_GUN günden eski araçlar ---
    son={}
    for r in db.execute('SELECT arac_id,gelis_at,gelis_nedeni,yapilan_islem FROM is_emirleri WHERE gelis_at IS NOT NULL'):
        txt=fold((r['gelis_nedeni'] or '')+' '+(r['yapilan_islem'] or ''))
        if any(k in txt for k in BAKIM_ANAHTAR) and r['gelis_at']>son.get(r['arac_id'],''): son[r['arac_id']]=r['gelis_at']
    esik=(simdi-timedelta(days=BAKIM_GUN)).strftime('%Y-%m-%d %H:%M:%S'); hat_esik=(simdi-timedelta(days=HATIRLATMA_BEKLEME)).strftime('%Y-%m-%d %H:%M:%S')
    acik_araclar={r[0] for r in db.execute("SELECT DISTINCT arac_id FROM is_emirleri WHERE durum!='Tamamlandı'")}
    bakim=[]
    for aid,tar in sorted(son.items(),key=lambda x:x[1]):
        if tar>=esik or aid in acik_araclar: continue
        a=db.execute('SELECT a.id,a.plaka,a.marka,a.model,a.hatirlatma_at,m.ad_soyad,m.telefon FROM araclar a JOIN musteriler m ON m.id=a.musteri_id WHERE a.id=?',(aid,)).fetchone()
        if not a or (a['hatirlatma_at'] and a['hatirlatma_at']>=hat_esik): continue
        gun=(simdi.date()-datetime.strptime(tar[:10],'%Y-%m-%d').date()).days
        bakim.append(dict(a,son=tar[:10],ay=gun//30))
    return render_template('istatistik.html',gelen=gelen,tamam=tamam,acik=acik,acik_toplam=sum(acik.values()),donem=donem,gunler=gunler,mx=mx,
        d_gelen=sum(x['gelen'] for x in gunler),d_tamam=sum(x['tamam'] for x in gunler),bekleyen=bekleyen,bekleyen_gun=BEKLEYEN_GUN,
        bakim=bakim[:100],bakim_ay=BAKIM_GUN//30)
@app.route('/araclar/<int:arac_id>/hatirlatildi',methods=['POST'])
@login_required
def arac_hatirlatildi(arac_id):
    db=get_db()
    if not db.execute('SELECT 1 FROM araclar WHERE id=?',(arac_id,)).fetchone(): abort(404)
    db.execute('UPDATE araclar SET hatirlatma_at=? WHERE id=?',(now(),arac_id)); db.commit(); log_olay(f'Bakım hatırlatıldı: araç #{arac_id}')
    flash(f'Hatırlatıldı olarak işaretlendi; {HATIRLATMA_BEKLEME} gün listede çıkmaz.','success'); return redirect(url_for('istatistik')+'#bakim')

# --- VERİ GÜVENCESİ: veritabanı boş açıldıysa ama yedek doluysa panelde kırmızı uyarı çıkar ---
_veri_uyari={'metin':None}
def _say(yol,tablo='musteriler'):
    try:
        c=sqlite3.connect(f'file:{yol}?mode=ro',uri=True,timeout=5)
        try: return c.execute(f'SELECT COUNT(*) FROM {tablo}').fetchone()[0]
        finally: c.close()
    except sqlite3.Error: return -1
def veri_kontrol():
    simdi=_say(DB_PATH); yedekler=sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith('servis_') and f.endswith('.db')) if os.path.isdir(BACKUP_DIR) else []
    app.logger.info('Veritabanı: %s | müşteri=%s | iş emri=%s | yedek sayısı=%s',DB_PATH,simdi,_say(DB_PATH,'is_emirleri'),len(yedekler))
    if simdi==0 and yedekler:
        eski=_say(os.path.join(BACKUP_DIR,yedekler[-1]))
        if eski>0:
            _veri_uyari['metin']=f'Veritabanı BOŞ görünüyor ama son yedekte ({yedekler[-1]}) {eski} müşteri var. Yanlış klasörden mi açıldı? Yedekten geri yükle: KURULUM.txt → GERİ YÜKLEME.'
            app.logger.error(_veri_uyari['metin'])
def yedek_bilgi():
    try: t=[os.path.getmtime(os.path.join(BACKUP_DIR,f)) for f in os.listdir(BACKUP_DIR) if f.startswith('servis_') and f.endswith('.db')]
    except OSError: t=[]
    if not t: return {'metin':'Henüz hiç yedek alınmamış.','kotu':True}
    sn=max(0,time.time()-max(t)); sa=int(sn//3600)
    metin='az önce' if sn<3600 else f'{sa} saat önce' if sa<48 else f'{sa//24} gün önce'
    return {'metin':f'Son yedek: {metin}','kotu':sn>48*3600}
@app.context_processor
def yedek_bagla(): return {'yedek':yedek_bilgi()}
@app.context_processor
def veri_uyari_bagla():
    if _veri_uyari['metin'] and _say(DB_PATH)>0: _veri_uyari['metin']=None     # veri geldi, uyarı kalksın
    return {'veri_uyari':_veri_uyari['metin']}
init_db()
veri_kontrol()
if __name__=='__main__': app.run(host='0.0.0.0',port=5000,debug=False)
