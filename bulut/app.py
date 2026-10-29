import os, re, json, sqlite3, hashlib, secrets, time, tempfile
from io import BytesIO
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort, Response, jsonify, has_request_context
from itsdangerous import URLSafeSerializer, BadSignature
import base64
os.umask(0o077)      # veritabanı, log ve yedek dosyaları yalnız çalıştıran kullanıcıya açık (0600/0700)
import qrcode
import etiket_yazici as EY

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
def _env_oku():
    # .env dosyasını burada da oku: uygulama 'python app.py' ile elle başlatılsa bile işletme bilgileri gelir.
    # Gerçek ortam değişkenleri öncelikli kalır (scripts/calistir.py ile aynı kurallar).
    try:
        with open(os.path.join(BASE_DIR,'.env'),encoding='utf-8-sig') as f: satirlar=f.read().splitlines()
    except OSError: return
    for s_ in satirlar:
        s_=s_.strip()
        if not s_ or s_.startswith('#') or '=' not in s_: continue
        k_,v_=s_.split('=',1); k_,v_=k_.strip(),v_.strip()
        if len(v_)>=2 and v_[0]==v_[-1] and v_[0] in '"\'': v_=v_[1:-1]
        if k_ and k_ not in os.environ: os.environ[k_]=v_
_env_oku()
os.umask(0o077)      # yeni dosyalar (veritabanı, yedek, log) yalnızca servisi çalıştıran kullanıcıya açık olur
DATA_DIR=os.path.join(BASE_DIR,'data'); DUKKAN_DIR=os.path.join(DATA_DIR,'dukkanlar'); YONETIM_DB=os.path.join(DATA_DIR,'yonetim.db')
def izinleri_sikilastir():
    # Önceki sürümlerden kalan geniş izinleri (klasör 0755, dosya 0644) kapatır: klasörler 0700, dosyalar 0600. Hata verirse sessiz geçer.
    try:
        for kok,dizinler,dosyalar in os.walk(DATA_DIR):
            os.chmod(kok,0o700)
            for f_ in dosyalar: os.chmod(os.path.join(kok,f_),0o600)
    except OSError: pass
def dukkan_dizin(i): return os.path.join(DUKKAN_DIR,str(int(i)))          # data/dukkanlar/<id>/  (servis.db + yedekler/)
def db_yolu(i): return os.path.join(dukkan_dizin(i),'servis.db')
def yedek_dizin(i): return os.path.join(dukkan_dizin(i),'yedekler')
def _sirri_yukle():
    # SECRET_KEY artık koda gömülü DEĞİL (eski anahtar kodda göründüğü için sızmış sayılır).
    # Sıra: ortam değişkeni -> data/.secret_key dosyası -> yoksa rastgele üretip dosyaya yazar.
    k=os.environ.get('SECRET_KEY','').strip()
    if k: return k
    yol=os.path.join(BASE_DIR,'data','.secret_key')
    try:
        if os.path.exists(yol):
            with open(yol) as f: k=f.read().strip()
            if k: return k
            os.remove(yol)      # boş/yarım kalmış dosya: yeniden üret
        os.makedirs(os.path.dirname(yol),exist_ok=True); k=secrets.token_hex(32)
        fd=os.open(yol,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.write(fd,k.encode()); os.close(fd); return k
    except OSError: return secrets.token_hex(32)   # yazılamazsa geçici anahtar (oturumlar yeniden başlatmada düşer)
SECRET_KEY=_sirri_yukle()
def _hash_uret(sifre):
    tuz=secrets.token_bytes(16)
    return f"pbkdf2_sha256$600000${tuz.hex()}${hashlib.pbkdf2_hmac('sha256',sifre.encode(),tuz,600000).hex()}"
def _hash_yukle():
    # BU SÜRÜMDE bu şifre YÖNETİCİ şifresidir (dükkân hesaplarını açan sen). Dükkânların şifreleri yonetim.db içinde ayrı tutulur.
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
# QR kodlarındaki herkese açık adres (alan adın). .env ile PUBLIC_BASE_URL=https://alanadiniz.com verilir.
# Boşsa o anki istek adresi kullanılır (yerel denemede çalışır; telefondan okutulacak QR için gerçek adres şart).
PUBLIC_BASE_URL=os.environ.get('PUBLIC_BASE_URL','').rstrip('/')
VITRIN_EPOSTA=os.environ.get('VITRIN_EPOSTA','ahmet.taner.2002@hotmail.com').strip()
if VITRIN_EPOSTA in ('-','0') or not re.fullmatch(r'[^\s@<>"\']{1,64}@[^\s@<>"\']{1,120}',VITRIN_EPOSTA): VITRIN_EPOSTA=''   # '-' yazarsan vitrinde iletişim bölümü gizlenir
SAAT_DILIMI=os.environ.get('SAAT_DILIMI','Europe/Istanbul').strip()      # dış sistemden gelen saat dilimli tarihler bu saate çevrilir
# İşletme adı/telefon/adres .env'den DEĞİL, giriş yapan dükkândan gelir (yönetici sayfasında girilir).
# Yetkili servislerde yapılan işlemler ("İşlemler ve arama" paneli).
def _yon(*adlar, yonler=('sağ','sol')):
    """'Amortisör' -> 'Amortisör sağ', 'Amortisör sol' (ayrıntılı kalemler)."""
    return [f'{a} {y}' for a in adlar for y in yonler]
ISLEM_KATEGORILERI=[
 ('🛢️','Bakım ve sıvılar',['Periyodik bakım','Yağ değişimi','Yağ filtresi','Hava filtresi','Polen filtresi','Yakıt filtresi','Antifriz / soğutma','Fren hidroliği değişimi','Şanzıman yağı','Diferansiyel yağı','Direksiyon hidrolik yağı','Mevsimlik kontrol']),
 ('🧾','Ağır bakım',['Ağır bakım','Triger seti + devirdaim','Yağ + 3 filtre (yağ/hava/polen)','Yağ + 4 filtre (yağ/hava/polen/yakıt)','Buji + bobin','Şanzıman yağı + filtre','Genel bakım kontrolü']),
 ('🛑','Fren',['Fren','Fren balatası','Fren diski','Fren kaliperi','El freni','ABS arızası','Fren hortumu / borusu']+['Ön fren balatası','Arka fren balatası','Ön fren diski','Arka fren diski']+_yon('Fren kaliperi','Fren hortumu')),
 ('⚙️','Motor',['Triger seti','Devirdaim','V kayışı / alternatör kayışı','Buji','Enjektör temizliği','Turbo','EGR / DPF temizliği','Silindir kapak contası','Motor takozu','Yağ kaçağı','Soğutma radyatörü','Termostat','Motor kulağı sağ','Motor kulağı sol','Yağ pompası','Kasnak / gergi']),
 ('🦾','Ön takım (sağ/sol)',['Direksiyon / süspansiyon']+_yon('Ön amortisör','Ön helezon yayı','Ön rotil','Ön rot başı','Ön z rot','Ön salıncak','Ön salıncak burcu','Ön tekerlek rulmanı','Ön aks','Ön aks körüğü','Ön amortisör takozu')),
 ('🦿','Arka takım (sağ/sol)',_yon('Arka amortisör','Arka helezon yayı','Arka tekerlek rulmanı','Arka salıncak','Arka salıncak burcu','Arka z rot','Arka amortisör takozu')+['Arka dingil / aks']),
 ('🔧','Alt takım ve direksiyon',['Amortisör','Helezon yayı','Rot / rotil','Z rot','Salıncak / burç','Tekerlek rulmanı','Aks / aks körüğü','Direksiyon kutusu','Rot balans','Direksiyon pompası','Direksiyon rotu','Alt takım kontrolü']),
 ('🛞','Lastik ve jant',['Lastik değişimi','Balans','Lastik tamiri','Jant düzeltme','Lastik saklama','Rot ayarı']+_yon('Ön lastik','Arka lastik',yonler=('sağ','sol'))+['4 lastik değişimi','Lastik sökme / takma']),
 ('⚡','Elektrik ve elektronik',['Akü','Marş / şarj','Alternatör','Elektrik arızası','Far / ampul','Silecek','Sensör','Bilgisayar / arıza kodu','Kilit / cam düğmesi','Marş motoru','Akü kutup başı','Sigorta / röle','Elektrik tesisatı']),
 ('📡','Sensör ve beyin',['Oksijen sensörü (lambda)','Krank sensörü','Kam sensörü','Map sensörü','Hava akış (debimetre) sensörü','Su ısı sensörü','ABS sensörü sağ ön','ABS sensörü sol ön','ABS sensörü sağ arka','ABS sensörü sol arka','Motor beyni (ECU) kontrolü','Arıza kodu silme / okuma','Kodlama / programlama','Gaz kelebeği temizliği','Airbag arızası']),
 ('💡','Aydınlatma, cam ve ayna',_yon('Ön far','Ön sis farı','Stop lambası','Sinyal lambası','Dikiz aynası','Cam kaldırma motoru','Cam düğmesi')+['Far ampulü','Park / plaka lambası','Silecek motoru','Silecek lastiği','Ön cam','Arka cam','Cam filmi','Ayna camı değişimi']),
 ('❄️','Klima ve ısıtma',['Klima bakımı','Klima gazı','Klima kompresörü','Kalorifer','Klima radyatörü','Klima fanı','Kalorifer radyatörü','Klima kaçak kontrolü']),
 ('🔩','Şanzıman ve debriyaj',['Debriyaj','Volan','Otomatik şanzıman bakımı','Şanzıman tamiri','Şaft','Debriyaj seti','Debriyaj bilyası','Debriyaj merkezi','Şanzıman takozu','Şanzıman keçesi']),
 ('💨','Egzoz',['Egzoz','Egzoz susturucu','Katalitik konvertör','Egzoz manifoldu','Egzoz contası','Ön susturucu','Arka susturucu','Egzoz askı lastiği','Egzoz kaynak']),
 ('⛽','LPG',['LPG ayarı / bakımı','LPG montajı','LPG filtre değişimi','LPG enjektör bakımı','LPG beyin ayarı','LPG kaçak kontrolü','LPG tüp muayenesi','LPG vakum hortumu','LPG buharlaştırıcı (reduktör) bakımı']),
 ('🧰','Diğer',['Arıza tespiti','Genel kontrol','Muayene hazırlığı','Kaporta / boya','Cam tamiri','Detaylı yıkama','Yol yardımı / çekici']),
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
app.config['PERMANENT_SESSION_LIFETIME']=60*60*24*14   # 14 gün (9 günlük bayram tatili aşılsın); her istekte süre yenilenir (REFRESH_EACH_REQUEST) -> usta her sabah şifre girmez, ancak 14 gün hiç açmazsa/çıkış yaparsa girer
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
def log_olay(mesaj):
    d=g.get('dukkan'); app.logger.info('%s | dukkan=%s | ip=%s',mesaj,d['kullanici'] if d else '-',client_ip())
    _hareket_kuyruk(mesaj)

@app.errorhandler(400)
def hata400(e):
    mesaj='Sayfa uzun süre açık kaldığı için oturum doğrulaması süresi dolmuş olabilir. Sayfayı yenileyip tekrar dene.'
    host=(request.host or '').split(':')[0].lower()
    if request.scheme=='http' and host not in ('localhost','127.0.0.1') and request.headers.get('X-Forwarded-Proto','').lower()!='https' and app.config.get('SESSION_COOKIE_SECURE'):
        # Güvenli (Secure) çerez, IP adresi üzerinden http ile açılan sayfada tarayıcı tarafından saklanmaz -> giriş hep 400 verir
        mesaj='Bu sayfayı IP adresi ile (http://'+(request.host or '')+') açtın; güvenlik gereği tarayıcı oturum çerezini saklamıyor. Bu bilgisayarda http://localhost:5000 adresini kullan, dışarıdan alan adını (https://) kullan. Yerel ağdan IP ile girmen gerekiyorsa .env dosyasına FORCE_HTTPS_COOKIE=0 yazıp sistemi yeniden başlat.'
    return render_template('hata.html',kod=400,baslik='İstek reddedildi',mesaj=mesaj),400
@app.errorhandler(404)
def hata404(e): return render_template('hata.html',kod=404,baslik='Sayfa bulunamadı',mesaj='Aradığın sayfa yok ya da taşınmış.'),404
@app.errorhandler(413)
def hata413(e): return render_template('hata.html',kod=413,baslik='İstek çok büyük',mesaj='Gönderilen veri çok büyük.'),413
@app.errorhandler(503)
def hata503(e): return render_template('hata.html',kod=503,baslik='Hesabın geçici olarak kapalı',mesaj='Bu dükkânın veritabanı açılamadı. Verin silinmedi; yöneticiyle görüş, yedekten geri yüklenecek.'),503
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
    # Marka bilgileri tüm şablonlara gelir. Ad/telefon/adres GİRİŞ YAPAN DÜKKÂNDAN gelir (yönetici sayfasında girilir).
    from markupsafe import Markup, escape
    ad,tel,adres=_isl()
    p=ad.split(' ',1)
    ad_html=Markup(escape(p[0])+(Markup(' <span class="amb">')+escape(p[1])+Markup('</span>') if len(p)>1 else Markup('')))
    ctx={'logo':'','now_yil':datetime.now().year,'public_base':PUBLIC_BASE_URL,'isletme':{'ad':ad,'kisa_html':ad_html,'ad_html':ad_html,'tel':tel,'tel_uluslararasi':_tel_uluslararasi(tel),'tel2':'','tel2_uluslararasi':'','eposta':'','yetkili':'','puan':'','yorum_sayisi':'','yorum_link':'',
         'adres':adres,'aciklama':'','harita_embed':'','harita_link':'','acilis':'09:00','kapanis':'19:00','saat_dilimi':'Europe/Istanbul'}}
    for uz in ('png','svg','webp','jpg','jpeg'):
        y=os.path.join(STATIC_DIR,'logo.'+uz)
        if os.path.exists(y): ctx['logo']=f'/static/logo.{uz}?v={int(os.path.getmtime(y))}'; break
    return ctx
def _isl():
    d=g.get('dukkan')
    return (d['ad'],d['tel'] or '',d['adres'] or '') if d else ('Servis Defteri','','')
def _tel_uluslararasi(t):
    d=re.sub(r'\D','',t or '')
    if not d: return ''
    if d.startswith('00'): d=d[2:]
    elif d.startswith('0'): d='90'+d[1:]
    return d
@app.route('/saglik')
def saglik():
    # Uptime servisleri için: veritabanı cevap veriyorsa "ok", yoksa 503. Veri döndürmez.
    try: c=yonetim_db(); c.execute('SELECT 1').fetchone(); c.close(); return 'ok',200,{'Content-Type':'text/plain; charset=utf-8','Cache-Control':'no-store'}
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
    if (giris_var() or yonetici_var()) and request.endpoint!='static': r.headers['Cache-Control']='no-store'          # çıkıştan sonra geri tuşuyla veri görünmesin
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
    if request.method == 'POST' and not request.path.startswith('/api/v1/'):   # dış sistem makine-makine API'si çerez/CSRF yerine dükkânın API anahtarını kullanır
        token = session.get('csrf_token')
        form_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        if not token or not form_token or not secrets.compare_digest(str(token).encode(), str(form_token).encode()):
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
def arac_km_guncelle(db,arac_id):
    # Aracın km'si ayrıca girilmez: her zaman EN SON iş emrinin giriş km'sidir (iş emri eklenince/düzenlenince/silinince yenilenir).
    r=db.execute("SELECT giris_km FROM is_emirleri WHERE arac_id=? AND giris_km IS NOT NULL ORDER BY substr(COALESCE(gelis_at,tarih),1,16) DESC,id DESC LIMIT 1",(arac_id,)).fetchone()
    if r: db.execute('UPDATE araclar SET kilometre=? WHERE id=?',(r[0],arac_id))
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
    return _wa(r['telefon'],f"Merhaba {tr_baslik(r['ad_soyad'])}, {plaka_goster(r['plaka'])} plakalı aracınız hazır, teslim alabilirsiniz. {_isl()[0]}")
@app.template_filter('wa_bakim')
def wa_bakim(r):
    return _wa(r['telefon'],f"Merhaba {tr_baslik(r['ad_soyad'])}, {plaka_goster(r['plaka'])} plakalı aracınızın son bakımının üzerinden {r['ay']} aydan fazla zaman geçti. Periyodik bakım için randevu almak isterseniz bu mesaja yazabilirsiniz. {_isl()[0]}")
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
def verify_password(p,h=None):
    try:
        alg,it,salt_hex,dh=(h or APP_PASSWORD_HASH).split('$'); salt=bytes.fromhex(salt_hex)
        got=hashlib.pbkdf2_hmac('sha256',p.encode(),salt,int(it)).hex()
        return secrets.compare_digest(got,dh)
    except Exception: return False

BOZUK_DUKKAN={}      # id -> hata; açılışta veritabanı açılamayan dükkânlar (yönetici geri yüklemeli)
def get_db():
    if 'db' not in g:
        d=g.get('dukkan')
        if not d: abort(401)
        if d['id'] in BOZUK_DUKKAN: abort(503)
        g.db=sqlite3.connect(db_yolu(d['id']),timeout=10); g.db.row_factory=sqlite3.Row; g.db.execute('PRAGMA foreign_keys=ON'); g.db.execute('PRAGMA synchronous=NORMAL')
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
def init_db(yol,kod):
    os.makedirs(os.path.dirname(yol),exist_ok=True); os.makedirs(os.path.join(os.path.dirname(yol),'yedekler'),exist_ok=True)
    c=sqlite3.connect(yol); c.execute('PRAGMA journal_mode=WAL')
    c.executescript('''CREATE TABLE IF NOT EXISTS musteriler(id INTEGER PRIMARY KEY AUTOINCREMENT,ad_soyad TEXT NOT NULL,telefon TEXT,eposta TEXT,adres TEXT,notlar TEXT);
    CREATE TABLE IF NOT EXISTS araclar(id INTEGER PRIMARY KEY AUTOINCREMENT,musteri_id INTEGER NOT NULL,plaka TEXT NOT NULL UNIQUE,marka TEXT,model TEXT,model_yili INTEGER,kilometre INTEGER,yakit_tipi TEXT,sanziman TEXT,renk TEXT,lpg_durumu INTEGER NOT NULL DEFAULT 0,notlar TEXT,FOREIGN KEY(musteri_id) REFERENCES musteriler(id));
    CREATE TABLE IF NOT EXISTS is_emirleri(id INTEGER PRIMARY KEY AUTOINCREMENT,arac_id INTEGER NOT NULL,tarih TEXT NOT NULL,gelis_nedeni TEXT,durum TEXT NOT NULL DEFAULT 'Beklemede',notlar TEXT,FOREIGN KEY(arac_id) REFERENCES araclar(id));''')
    c.execute('CREATE TABLE IF NOT EXISTS cop(id INTEGER PRIMARY KEY AUTOINCREMENT,tablo TEXT NOT NULL,kayit_id INTEGER,ozet TEXT,veri TEXT NOT NULL,silindi_at TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS entegrasyon_kayit(kayit_no TEXT PRIMARY KEY,is_emri_id INTEGER,arac_id INTEGER,yeni_arac INTEGER NOT NULL DEFAULT 0,durum TEXT,neden TEXT,olusturuldu_at TEXT,veri TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS entegrasyon_hata(id INTEGER PRIMARY KEY AUTOINCREMENT,zaman TEXT,kayit_no TEXT,hata TEXT,govde TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS ozel_islem(id INTEGER PRIMARY KEY AUTOINCREMENT,ad TEXT NOT NULL UNIQUE COLLATE NOCASE,olusturuldu_at TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS cihazlar(id INTEGER PRIMARY KEY AUTOINCREMENT,ad TEXT NOT NULL,kod TEXT NOT NULL,olusturuldu_at TEXT,son_gorulme_at TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS yazdirma_isleri(id INTEGER PRIMARY KEY AUTOINCREMENT,olusturuldu_at TEXT NOT NULL,arac_id INTEGER,plaka TEXT,adet INTEGER NOT NULL DEFAULT 1,veri TEXT NOT NULL,durum TEXT NOT NULL DEFAULT \'bekliyor\',mesaj TEXT,alindi_at TEXT,bitti_at TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS hareketler(id INTEGER PRIMARY KEY AUTOINCREMENT,zaman TEXT NOT NULL,cihaz_id INTEGER,cihaz TEXT,ip TEXT,olay TEXT NOT NULL)')
    c.execute('CREATE INDEX IF NOT EXISTS ix_hareketler_zaman ON hareketler(zaman)')
    c.execute("DELETE FROM cop WHERE silindi_at<?",((datetime.now()-timedelta(days=COP_GUN)).strftime('%Y-%m-%d %H:%M:%S'),))
    for n in ['olusturuldu_at TEXT','guncellendi_at TEXT']: addcol(c,'musteriler',n)
    for n in ['qr_token TEXT','olusturuldu_at TEXT','guncellendi_at TEXT','hatirlatma_at TEXT']: addcol(c,'araclar',n)
    for n in ['gelis_at TEXT','giris_km INTEGER','gidis_at TEXT','olusturuldu_at TEXT','guncellendi_at TEXT','yapilan_islem TEXT','kaynak TEXT']: addcol(c,'is_emirleri',n)
    # backfill timestamps and QR tokens
    c.execute("UPDATE musteriler SET olusturuldu_at=COALESCE(olusturuldu_at,?) , guncellendi_at=COALESCE(guncellendi_at,?)",(now(),now()))
    rows=c.execute('SELECT id FROM araclar WHERE qr_token IS NULL OR qr_token=""').fetchall()
    for (i,) in rows: c.execute('UPDATE araclar SET qr_token=?,olusturuldu_at=COALESCE(olusturuldu_at,?),guncellendi_at=COALESCE(guncellendi_at,?) WHERE id=?',(yeni_token(kod),now(),now(),i))
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

# ===================== DÜKKÂNLAR (çok dükkânlı sürüm) =====================
# Her dükkânın verisi AYRI: data/dukkanlar/<id>/servis.db. Dükkân hesapları data/yonetim.db içinde (kullanıcı adı + şifre özeti).
# Hesapları yalnızca yönetici açar (/yonetici). Yönetici şifresi: data/.password_hash (scripts/sifre_degistir.py).
KOD_HARF='abcdefghjkmnpqrstuvwxyz23456789'          # karışan harfler (i, l, o, 0, 1) yok
KULLANICI_RE=re.compile(r'^[a-z0-9][a-z0-9._-]{2,29}$')
def yonetim_db():
    c=sqlite3.connect(YONETIM_DB,timeout=10); c.row_factory=sqlite3.Row; return c
def yonetim_init():
    os.makedirs(DATA_DIR,exist_ok=True)
    c=yonetim_db(); c.execute('PRAGMA journal_mode=WAL')
    c.execute('''CREATE TABLE IF NOT EXISTS dukkanlar(id INTEGER PRIMARY KEY AUTOINCREMENT,kod TEXT NOT NULL UNIQUE,kullanici TEXT NOT NULL UNIQUE COLLATE NOCASE,
        ad TEXT NOT NULL,tel TEXT,adres TEXT,hash TEXT NOT NULL,oturum_surum INTEGER NOT NULL DEFAULT 0,aktif INTEGER NOT NULL DEFAULT 1,gecici INTEGER NOT NULL DEFAULT 1,olusturuldu_at TEXT)''')
    for n in ['api_hash TEXT','api_olusturuldu_at TEXT','ajan_hash TEXT','ajan_olusturuldu_at TEXT']: addcol(c,'dukkanlar',n)       # dış sistem API anahtarının özeti (anahtarın kendisi saklanmaz)
    c.commit(); c.close()
def _dukkan_sor(sql,args=()):
    c=yonetim_db()
    try: r=c.execute(sql,args).fetchone(); return dict(r) if r else None
    finally: c.close()
def dukkan_getir(i):
    try: return _dukkan_sor('SELECT * FROM dukkanlar WHERE id=?',(int(i),))
    except (TypeError,ValueError): return None
def dukkan_kullanici(k): return _dukkan_sor('SELECT * FROM dukkanlar WHERE kullanici=?',(k,))
def dukkan_kod_ile(kod): return _dukkan_sor('SELECT * FROM dukkanlar WHERE kod=?',(kod,)) if len(kod)==4 else None
def tum_dukkanlar():
    c=yonetim_db()
    try: return [dict(r) for r in c.execute('SELECT * FROM dukkanlar ORDER BY id')]
    finally: c.close()
def yeni_token(kod): return kod+secrets.token_urlsafe(18)       # QR kodu: ilk 4 harf dükkânı bulur, gerisi tahmin edilemez
def gecici_sifre(): return ''.join(secrets.choice(KOD_HARF) for _ in range(5))+'-'+''.join(secrets.choice(KOD_HARF) for _ in range(5))
def dukkan_olustur(kullanici,ad,tel='',adres='',sifre=None,gecici=True):
    """Yeni dükkân + kendi veritabanı. (id, sifre) döner; geçersiz/yinelenen girdide ValueError (Türkçe mesaj)."""
    kullanici=(kullanici or '').strip().lower(); ad=(ad or '').strip()[:60]
    if not KULLANICI_RE.match(kullanici): raise ValueError('Kullanıcı adı 3-30 karakter olmalı: küçük harf, rakam, nokta, tire (örn. ahmet-oto).')
    if not ad: raise ValueError('Dükkân adı boş olamaz.')
    tel=re.sub(r'[^0-9+ ]','',tel or '').strip()[:20]; adres=(adres or '').strip()[:200]
    sifre=sifre or gecici_sifre(); h=_hash_uret(sifre)
    c=yonetim_db()
    try:
        if c.execute('SELECT 1 FROM dukkanlar WHERE kullanici=?',(kullanici,)).fetchone(): raise ValueError('Bu kullanıcı adı zaten var.')
        for _ in range(50):
            kod=''.join(secrets.choice(KOD_HARF) for _ in range(4))
            if not c.execute('SELECT 1 FROM dukkanlar WHERE kod=?',(kod,)).fetchone(): break
        else: raise ValueError('Dükkân kodu üretilemedi, tekrar dene.')
        i=c.execute('INSERT INTO dukkanlar(kod,kullanici,ad,tel,adres,hash,gecici,olusturuldu_at) VALUES(?,?,?,?,?,?,?,?)',(kod,kullanici,ad,tel,adres,h,1 if gecici else 0,now())).lastrowid
        c.commit()
    finally: c.close()
    init_db(db_yolu(i),kod)
    return i,sifre
def dukkan_sifre_yaz(i,sifre,gecici):
    c=yonetim_db()
    try: c.execute('UPDATE dukkanlar SET hash=?,gecici=?,oturum_surum=oturum_surum+1 WHERE id=?',(_hash_uret(sifre),1 if gecici else 0,int(i))); c.commit()
    finally: c.close()
def dukkan_oturum_artir(i):
    c=yonetim_db()
    try: c.execute('UPDATE dukkanlar SET oturum_surum=oturum_surum+1 WHERE id=?',(int(i),)); c.commit()
    finally: c.close()

# ===================== GİRİŞ (dükkân: kullanıcı adı + şifre) =====================
SAHTE_HASH=_hash_uret('sahte-sifre')        # bilinmeyen kullanıcıda da aynı süre harcansın (kullanıcı adı sızmasın)
def _imza(d):
    # Şifre değişince, "tüm cihazlardan çıkış" basılınca veya hesap kapanınca eski oturumlar geçersiz olur
    return hashlib.sha256((d['hash']+str(d['oturum_surum'])).encode()).hexdigest()[:16]
def _oturum_dukkani():
    if '_od' in g: return g._od
    d=None; i=session.get('dukkan_id')
    if i and session.get('giris_yapildi'):
        d=dukkan_getir(i)
        if not d or not d['aktif'] or session.get('sv')!=_imza(d): d=None
    g._od=d; return d
def giris_var():
    d=_oturum_dukkani()
    if not d: return False
    if g.get('dukkan') and g.dukkan['id']!=d['id']: return False     # başka dükkânın QR sayfasında "usta" görünümü yok
    g.dukkan=d; return True
def login_required(v):
    @wraps(v)
    def w(*a,**kw):
        if not giris_var(): return redirect(url_for('login'))
        return v(*a,**kw)
    return w
@app.before_request
def gecici_sifre_zorla():
    # Yönetici geçici şifre verdiyse dükkân önce kendi şifresini seçer
    ep=request.endpoint or ''
    if ep in ('static','login','logout','sifre_degistir','saglik','qr_arac','anasayfa') or ep.startswith('yonetici'): return
    d=_oturum_dukkani()
    if d and d['gecici']: return redirect(url_for('sifre_degistir'))
@app.route('/login',methods=['GET','POST'])
def login():
    ip=client_ip()
    if request.method=='GET' and giris_var(): return redirect(url_for('dashboard'))
    if request.method=='POST':
        k=request.form.get('kullanici','').strip().lower()[:40]
        if is_rate_limited(ip) or is_rate_limited('u:'+k):
            flash('Çok fazla yanlış deneme yaptın. 1 dakika bekleyip tekrar dene.','danger')
            return render_template('login.html')
        d=dukkan_kullanici(k) if k else None
        dogru=verify_password(request.form.get('sifre',''),d['hash'] if d else SAHTE_HASH) and bool(d)
        if dogru and d['aktif']:
            _login_attempts.pop(ip,None); _login_attempts.pop('u:'+k,None)
            session.clear(); session.permanent=True; session['giris_yapildi']=True; session['dukkan_id']=d['id']; session['sv']=_imza(d)   # eski oturum içeriğini at (session fixation)
            g.dukkan=d; log_olay('Giriş başarılı')
            return redirect(url_for('dashboard'))
        if dogru:
            flash('Bu hesap şu an kapalı. Yöneticiyle görüş.','danger')
        else:
            record_failed_attempt(ip); record_failed_attempt('u:'+k); log_olay('Giriş başarısız (kullanıcı '+(d['kullanici'] if d else 'bilinmiyor')+')')    # yazılan metin log'a girmez: satır sonu / yanlışlıkla yazılan şifre
            flash('Kullanıcı adı veya şifre hatalı.','danger')
    return render_template('login.html')
@app.route('/sifre',methods=['GET','POST'])
@login_required
def sifre_degistir():
    d=g.dukkan
    if request.method=='POST':
        eski,yeni,yeni2=request.form.get('eski',''),request.form.get('yeni',''),request.form.get('yeni2','')
        hata=None
        if not verify_password(eski,d['hash']): hata='Mevcut şifre hatalı.'
        elif len(yeni)<8: hata='Yeni şifre en az 8 karakter olmalı.'
        elif yeni!=yeni2: hata='Yeni şifre iki kutuda aynı değil.'
        elif yeni==eski or yeni.lower()==d['kullanici']: hata='Yeni şifre eskisinden ve kullanıcı adından farklı olmalı.'
        if hata: flash(hata,'danger')
        else:
            dukkan_sifre_yaz(d['id'],yeni,0); session['sv']=_imza(dukkan_getir(d['id']))      # bu cihaz açık kalır, diğerleri düşer
            log_olay('Şifre değiştirildi'); flash('Şifren değişti. Diğer cihazlardaki oturumlar kapatıldı.','success')
            return redirect(url_for('dashboard'))
    return render_template('sifre.html',gecici=bool(d['gecici']),sade=bool(d['gecici']))
@app.route('/cikis-hepsi',methods=['POST'])
@login_required
def cikis_hepsi():
    dukkan_oturum_artir(g.dukkan['id']); log_olay('TÜM CİHAZLARDAN ÇIKIŞ'); session.clear()
    flash('Tüm cihazlardan çıkış yapıldı. Tekrar giriş yapabilirsin.','success'); return redirect(url_for('login'))
@app.route('/logout',methods=['GET','POST'])
def logout():
    # Çıkış yalnızca POST (CSRF'li) ile yapılır; GET durum değiştirmez.
    if request.method!='POST': return redirect(url_for('login'))
    giris_var(); log_olay('Çıkış'); session.clear(); return redirect(url_for('login'))

# ===================== YÖNETİCİ (dükkân hesaplarını sen açarsın) =====================
def _y_imza(): return hashlib.sha256(('yonetici'+APP_PASSWORD_HASH).encode()).hexdigest()[:16]
def yonetici_var(): return bool(session.get('yonetici')) and session.get('sv_y')==_y_imza()
def yonetici_gerekli(v):
    @wraps(v)
    def w(*a,**kw):
        if not yonetici_var(): return redirect(url_for('yonetici_giris'))
        return v(*a,**kw)
    return w
@app.route('/yonetici/giris',methods=['GET','POST'])
def yonetici_giris():
    ip='y:'+client_ip()
    if request.method=='POST':
        if is_rate_limited(ip): flash('Çok fazla yanlış deneme. 1 dakika bekle.','danger')
        elif verify_password(request.form.get('sifre','')):
            _login_attempts.pop(ip,None); session.clear(); session['yonetici']=True; session['sv_y']=_y_imza()
            app.logger.info('Yönetici girişi | ip=%s',client_ip()); return redirect(url_for('yonetici'))
        else: record_failed_attempt(ip); app.logger.info('Yönetici girişi başarısız | ip=%s',client_ip()); flash('Şifre hatalı.','danger')
    return render_template('yonetici_giris.html')
def _yonetici_liste():
    out=[]
    for d in tum_dukkanlar():
        yd=yedek_dizin(d['id']); t=[]
        try: t=[os.path.getmtime(os.path.join(yd,f)) for f in os.listdir(yd) if f.startswith('servis_') and f.endswith('.db')]
        except OSError: pass
        sn=time.time()-max(t) if t else None
        d['is_emri']=max(_say(db_yolu(d['id']),'is_emirleri'),0)
        d['yedek']='yok' if sn is None else ('az önce' if sn<3600 else f'{int(sn//3600)} saat önce' if sn<48*3600 else f'{int(sn//86400)} gün önce')
        d['yedek_kotu']=sn is None or sn>48*3600
        d['bozuk']=d['id'] in BOZUK_DUKKAN
        d['api']=bool(d.get('api_hash'))
        d['ajan']=bool(d.get('ajan_hash')); d['ajan_bagli']=ajan_bagli(d['id'])
        out.append(d)
    return out
@app.route('/yonetici')
@yonetici_gerekli
def yonetici():
    return render_template('yonetici.html',dukkanlar=_yonetici_liste(),yeni=None)
@app.route('/yonetici/ekle',methods=['POST'])
@yonetici_gerekli
def yonetici_ekle():
    f=request.form
    try: i,sifre=dukkan_olustur(f.get('kullanici',''),f.get('ad',''),f.get('tel',''),f.get('adres',''))
    except ValueError as e: flash(str(e),'danger'); return redirect(url_for('yonetici'))
    app.logger.info('Dükkân açıldı: %s | ip=%s',f.get('kullanici','').strip().lower(),client_ip())
    return render_template('yonetici.html',dukkanlar=_yonetici_liste(),yeni={'kullanici':f.get('kullanici','').strip().lower(),'ad':f.get('ad','').strip(),'sifre':sifre,'ne':'açıldı'})
@app.route('/yonetici/<int:i>/sifre-sifirla',methods=['POST'])
@yonetici_gerekli
def yonetici_sifre_sifirla(i):
    d=dukkan_getir(i)
    if not d: abort(404)
    sifre=gecici_sifre(); dukkan_sifre_yaz(i,sifre,True); app.logger.info('Dükkân şifresi sıfırlandı: %s | ip=%s',d['kullanici'],client_ip())
    return render_template('yonetici.html',dukkanlar=_yonetici_liste(),yeni={'kullanici':d['kullanici'],'ad':d['ad'],'sifre':sifre,'ne':'şifresi sıfırlandı'})
@app.route('/yonetici/<int:i>/durum',methods=['POST'])
@yonetici_gerekli
def yonetici_durum(i):
    d=dukkan_getir(i)
    if not d: abort(404)
    c=yonetim_db()
    try: c.execute('UPDATE dukkanlar SET aktif=?,oturum_surum=oturum_surum+1 WHERE id=?',(0 if d['aktif'] else 1,i)); c.commit()
    finally: c.close()
    app.logger.info('Dükkân %s: %s | ip=%s','KAPATILDI' if d['aktif'] else 'AÇILDI',d['kullanici'],client_ip())
    flash(f"{d['ad']} {'kapatıldı (giriş yapamaz, verisi durur)' if d['aktif'] else 'yeniden açıldı'}.",'success'); return redirect(url_for('yonetici'))
@app.route('/yonetici/<int:i>/api',methods=['POST'])
@yonetici_gerekli
def yonetici_api(i):
    d=dukkan_getir(i)
    if not d: abort(404)
    eylem=request.form.get('eylem','')
    if eylem not in ('uret','kapat'): abort(400)
    anahtar=f'sk_{d["kod"]}_'+secrets.token_urlsafe(30) if eylem=='uret' else None
    c=yonetim_db()
    try: c.execute('UPDATE dukkanlar SET api_hash=?,api_olusturuldu_at=? WHERE id=?',(hashlib.sha256(anahtar.encode()).hexdigest() if anahtar else None,now() if anahtar else None,i)); c.commit()
    finally: c.close()
    app.logger.info('Dükkân API anahtarı %s: %s | ip=%s','üretildi/yenilendi' if anahtar else 'KAPATILDI',d['kullanici'],client_ip())
    if not anahtar: flash(f"{d['ad']} için API anahtarı kapatıldı (eski anahtar artık çalışmaz).",'success'); return redirect(url_for('yonetici'))
    r=app.make_response(render_template('yonetici.html',dukkanlar=_yonetici_liste(),yeni={'kullanici':d['kullanici'],'ad':d['ad'],'api':anahtar,'ne':'API anahtarı üretildi'}))
    r.headers['Cache-Control']='no-store'; return r
@app.route('/yonetici/<int:i>/ajan',methods=['POST'])
@yonetici_gerekli
def yonetici_ajan(i):
    d=dukkan_getir(i)
    if not d: abort(404)
    eylem=request.form.get('eylem','')
    if eylem not in ('uret','kapat'): abort(400)
    anahtar=f'ya_{d["kod"]}_'+secrets.token_urlsafe(30) if eylem=='uret' else None
    c=yonetim_db()
    try: c.execute('UPDATE dukkanlar SET ajan_hash=?,ajan_olusturuldu_at=? WHERE id=?',(hashlib.sha256(anahtar.encode()).hexdigest() if anahtar else None,now() if anahtar else None,i)); c.commit()
    finally: c.close()
    _ajan_son.pop(i,None)
    app.logger.info('Dükkân ajan anahtarı %s: %s | ip=%s','üretildi/yenilendi' if anahtar else 'KAPATILDI',d['kullanici'],client_ip())
    if not anahtar: flash(f"{d['ad']} için yazdırma ajanı kapatıldı (eski anahtar artık çalışmaz).",'success'); return redirect(url_for('yonetici'))
    r=app.make_response(render_template('yonetici.html',dukkanlar=_yonetici_liste(),yeni={'kullanici':d['kullanici'],'ad':d['ad'],'ajan':anahtar,'ne':'yazdırma ajanı anahtarı üretildi'}))
    r.headers['Cache-Control']='no-store'; return r
@app.route('/yonetici/<int:i>/bilgi',methods=['POST'])
@yonetici_gerekli
def yonetici_bilgi(i):
    d=dukkan_getir(i)
    if not d: abort(404)
    ad=request.form.get('ad','').strip()[:60]
    if not ad: flash('Dükkân adı boş olamaz.','danger'); return redirect(url_for('yonetici'))
    c=yonetim_db()
    try: c.execute('UPDATE dukkanlar SET ad=?,tel=?,adres=? WHERE id=?',(ad,re.sub(r'[^0-9+ ]','',request.form.get('tel','')).strip()[:20],request.form.get('adres','').strip()[:200],i)); c.commit()
    finally: c.close()
    flash('Bilgiler kaydedildi.','success'); return redirect(url_for('yonetici'))
@app.route('/yonetici/cikis',methods=['POST'])
def yonetici_cikis(): session.clear(); return redirect(url_for('yonetici_giris'))

# ===================== DÜKKÂNIN KENDİ YEDEĞİ =====================
def anlik_yedek_bayt(yol):
    """Çalışan veritabanının tutarlı bir kopyasını (SQLite yedekleme API'si) bayt olarak verir."""
    fd,gecici=tempfile.mkstemp(suffix='.db'); os.close(fd)
    try:
        k=sqlite3.connect(f'file:{yol}?mode=ro',uri=True,timeout=10); h=sqlite3.connect(gecici)
        try:
            with h: k.backup(h)
        finally: k.close(); h.close()
        with open(gecici,'rb') as f: return f.read()
    finally:
        try: os.unlink(gecici)
        except OSError: pass
@app.route('/yedek-indir')
@login_required
def yedek_indir():
    d=g.dukkan; veri=anlik_yedek_bayt(db_yolu(d['id'])); log_olay('Yedek indirildi')
    ad=f"servis_{d['kullanici']}_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
    return Response(veri,mimetype='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{ad}"','Cache-Control':'no-store'})

@app.route('/')
def anasayfa():
    # Giriş yapmış usta panele gider; ziyaretçi vitrini (tanıtım sayfası) görür. Vitrinde veri yok, herkese açık.
    if giris_var(): return redirect(url_for('dashboard'))
    return render_template('vitrin.html',eposta=VITRIN_EPOSTA)
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
def _sayfa_no(): return min(100000,max(1,request.args.get('s',1,type=int) or 1))      # liste sayfası (?s=2), sayfa başına 100 kayıt
@app.route('/musteriler')
@login_required
def musteriler():
    q=request.args.get('q','').strip(); db=get_db(); like=f'%{q}%'; likeu=f'%{tr_upper(q)}%'
    s=_sayfa_no(); ofs=(s-1)*100
    rows=db.execute('SELECT * FROM musteriler WHERE ad_soyad LIKE ? OR telefon LIKE ? OR eposta LIKE ? ORDER BY id DESC LIMIT 101 OFFSET ?',(likeu,like,like,ofs)).fetchall() if q else db.execute('SELECT * FROM musteriler ORDER BY id DESC LIMIT 101 OFFSET ?',(ofs,)).fetchall()
    sonra=len(rows)>100; rows=rows[:100]; plakalar={}; ids=[r['id'] for r in rows]
    if ids:
        for r in db.execute('SELECT musteri_id,plaka FROM araclar WHERE musteri_id IN (%s) ORDER BY id'%','.join('?'*len(ids)),ids): plakalar.setdefault(r['musteri_id'],[]).append(r['plaka'])
    return render_template('musteriler.html',kayitlar=rows,q=q,plakalar=plakalar,sayfa=s,sonra=sonra,sayfa_ucu='musteriler')
@app.route('/musteriler/<int:musteri_id>')
@login_required
def musteri_detay(musteri_id):
    # Ayrı müşteri sayfası kaldırıldı: eski bağlantılar müşterinin araçları listesine gider (Düzenle / İş Emri Aç / Etiket orada).
    if not get_db().execute('SELECT 1 FROM musteriler WHERE id=?',(musteri_id,)).fetchone(): abort(404)
    return redirect(url_for('araclar',musteri=musteri_id))
# ===================== DIŞA AKTARMA (CSV — Excel'de çift tıkla açılır) =====================
import csv
from io import StringIO
def _csv_hucre(v):
    if v is None: return ''
    v=str(v)
    return "'"+v if (v[:1] in ('\t','\r','\n') or v.lstrip(' \t\r\n\x00')[:1] in ('=','+','-','@')) else v    # Excel'de formül gibi çalışmasın (baştaki boşluk/sekme dahil)
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
    ad=tr_upper(request.form.get('ad_soyad',''))[:100] or ISIMSIZ_ON_EK   # isim zorunlu değil
    t=now(); db=get_db(); db.execute('INSERT INTO musteriler(ad_soyad,telefon,eposta,adres,notlar,olusturuldu_at,guncellendi_at) VALUES(?,?,?,?,?,?,?)',(ad,request.form.get('telefon','').strip(),request.form.get('eposta','').strip(),request.form.get('adres','').strip(),request.form.get('notlar','').strip(),t,t)); db.commit(); log_olay('Müşteri eklendi'); flash('Müşteri eklendi.','success'); return redirect(url_for('musteriler'))
@app.route('/musteriler/duzenle/<int:musteri_id>',methods=['GET','POST'])
@login_required
def musteri_duzenle(musteri_id):
    db=get_db(); row=db.execute('SELECT * FROM musteriler WHERE id=?',(musteri_id,)).fetchone()
    if not row: abort(404)
    if request.method=='POST':
        db.execute('UPDATE musteriler SET ad_soyad=?,telefon=?,eposta=?,adres=?,notlar=?,guncellendi_at=? WHERE id=?',(tr_upper(request.form.get('ad_soyad',''))[:100] or ISIMSIZ_ON_EK,request.form.get('telefon','').strip(),request.form.get('eposta','').strip(),request.form.get('adres','').strip(),request.form.get('notlar','').strip(),now(),musteri_id)); db.commit(); log_olay(f'Müşteri #{musteri_id} düzenlendi'); flash('Müşteri güncellendi.','success'); return redirect(url_for('musteriler'))
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
    musteri=None
    if request.args.get('musteri','').isdigit():     # /araclar?musteri=5 -> yalnızca o müşterinin araçları
        musteri=db.execute('SELECT * FROM musteriler WHERE id=?',(int(request.args['musteri']),)).fetchone()
        if not musteri: abort(404)
    taban='SELECT a.*,m.ad_soyad,m.telefon FROM araclar a JOIN musteriler m ON m.id=a.musteri_id'
    s=_sayfa_no(); ofs=(s-1)*100; sonra=False
    if musteri: rows=db.execute(taban+' WHERE a.musteri_id=? ORDER BY a.id DESC',(musteri['id'],)).fetchall()      # tek müşterinin araçları: sayfalama gerekmez
    elif q: rows=db.execute(taban+''' WHERE REPLACE(a.plaka,' ','') LIKE ? OR a.marka LIKE ? OR a.model LIKE ? OR m.ad_soyad LIKE ? OR m.telefon LIKE ? ORDER BY a.id DESC LIMIT 101 OFFSET ?''',(plaka_like(q),like,like,likeu,like,ofs)).fetchall()
    else: rows=db.execute(taban+' ORDER BY a.id DESC LIMIT 101 OFFSET ?',(ofs,)).fetchall()
    if not musteri: sonra=len(rows)>100; rows=rows[:100]
    isler=[]; is_say=0
    if musteri:   # müşterinin tüm araçlarının son iş emirleri
        isler=db.execute("SELECT i.id,i.durum,i.gelis_at,i.gidis_at,i.yapilan_islem,i.gelis_nedeni,i.giris_km,a.plaka FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id WHERE a.musteri_id=? ORDER BY COALESCE(i.gelis_at,i.tarih) DESC,i.id DESC LIMIT 15",(musteri['id'],)).fetchall()
        is_say=db.execute('SELECT COUNT(*) FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id WHERE a.musteri_id=?',(musteri['id'],)).fetchone()[0]
    ms=db.execute('SELECT id,ad_soyad FROM musteriler ORDER BY ad_soyad').fetchall(); return render_template('araclar.html',kayitlar=rows,musteri_listesi=ms,q=q,musteri=musteri,isler=isler,is_say=is_say,sayfa=s,sonra=sonra,sayfa_ucu='araclar')
@app.route('/araclar/ekle',methods=['POST'])
@login_required
def arac_ekle():
    f=request.form; p=temiz_plaka(f.get('plaka','')); mid=f.get('musteri_id','')
    if not p or not mid: flash('Plaka ve müşteri zorunludur.','danger'); return redirect(url_for('araclar'))
    if not get_db().execute('SELECT 1 FROM musteriler WHERE id=?',(mid,)).fetchone(): flash('Seçilen müşteri bulunamadı.','danger'); return redirect(url_for('araclar'))
    if not f.get('ozel_plaka') and not PLAKA_RE.match(p): flash('Plaka biçimi geçersiz. Örnek: 35 ABC 123. Özel/yabancı plakaysa kutuyu işaretle.','danger'); return redirect(url_for('araclar'))
    yakit=f.get('yakit_tipi','').strip(); t=now(); db=get_db()
    try:
        db.execute('''INSERT INTO araclar(musteri_id,plaka,marka,model,model_yili,yakit_tipi,sanziman,renk,lpg_durumu,notlar,qr_token,olusturuldu_at,guncellendi_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(mid,p,marka_al(f),f.get('model','').strip()[:40],yil_al(f.get('model_yili')),yakit,f.get('sanziman','').strip(),f.get('renk','').strip()[:30],1 if 'LPG' in yakit.upper() else 0,f.get('notlar','').strip(),yeni_token(g.dukkan['kod']),t,t)); db.commit(); log_olay(f'Araç eklendi: {plaka_goster(p)}'); flash(f'Araç eklendi: {plaka_goster(p)}','success')
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
        if not db.execute('SELECT 1 FROM musteriler WHERE id=?',(f.get('musteri_id'),)).fetchone(): flash('Seçilen müşteri bulunamadı.','danger'); return redirect(url_for('arac_duzenle',arac_id=arac_id))
        if not f.get('ozel_plaka') and not PLAKA_RE.match(p): flash('Plaka biçimi geçersiz. Örnek: 35 ABC 123. Özel/yabancı plakaysa kutuyu işaretle.','danger'); return redirect(url_for('arac_duzenle',arac_id=arac_id))
        try:
            db.execute('''UPDATE araclar SET musteri_id=?,plaka=?,marka=?,model=?,model_yili=?,yakit_tipi=?,sanziman=?,renk=?,lpg_durumu=?,notlar=?,guncellendi_at=? WHERE id=?''',(f.get('musteri_id'),p,marka_al(f),f.get('model','').strip()[:40],yil_al(f.get('model_yili')),yakit,f.get('sanziman','').strip(),f.get('renk','').strip()[:30],1 if 'LPG' in yakit.upper() else 0,f.get('notlar','').strip(),now(),arac_id)); db.commit(); log_olay(f'Araç #{arac_id} düzenlendi: {plaka_goster(p)}'); flash('Araç güncellendi.','success'); return redirect(url_for('araclar'))
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
    d=dukkan_kod_ile(token[:4])
    if not d or not d['aktif']: abort(404)
    g.dukkan=d; db=get_db(); usta=giris_var()    # telefon yalnızca giriş yapmış usta için çekilir; herkese açık sorguda yok
    a=db.execute('''SELECT a.id,a.plaka,a.marka,a.model,a.model_yili,a.yakit_tipi,a.sanziman,a.kilometre,m.ad_soyad'''+(',m.telefon' if usta else '')+''' FROM araclar a JOIN musteriler m ON m.id=a.musteri_id WHERE a.qr_token=?''',(token,)).fetchone()
    if not a: abort(404)
    toplam=db.execute('SELECT COUNT(*) FROM is_emirleri WHERE arac_id=?',(a['id'],)).fetchone()[0]
    hs=db.execute('SELECT id,durum,gelis_at,gidis_at,yapilan_islem,gelis_nedeni,giris_km FROM is_emirleri WHERE arac_id=? ORDER BY gelis_at DESC,id DESC LIMIT 300',(a['id'],)).fetchall()
    sinir=(datetime.now()-timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')     # usta için "Tamamlandı" bildirimi 3 gün görünür, sonra kalkar (kayıt geçmişte durur)
    yeni_tamam={h['id'] for h in hs if h['durum']=='Tamamlandı' and (h['gidis_at'] or '')>=sinir} if usta else set()
    # giriş yapmış usta kendi telefonuyla okutursa müşteriyi arama/haber verme düğmelerini görür; herkese açık sayfada telefon HİÇ yok
    musteri_wa=_wa(a['telefon'],f"Merhaba {tr_baslik(a['ad_soyad'])}, {plaka_goster(a['plaka'])} plakalı aracınız hazır, teslim alabilirsiniz. {_isl()[0]}") if usta else ''
    return render_template('qr_arac.html',a=a,hs=hs,usta=usta,yeni_tamam=yeni_tamam,
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
def _zaman_duzelt(v):
    # 'YYYY-MM-DDTHH:MM' / 'YYYY-MM-DD HH:MM[:SS]' -> 'YYYY-MM-DD HH:MM:SS'; geçersizse None
    v=str(v or '').strip().replace('T',' ')
    for bicim in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M'):
        try: return datetime.strptime(v,bicim).strftime('%Y-%m-%d %H:%M:%S')
        except ValueError: pass
    return None
def _geri_url(v): return v if isinstance(v,str) and (v.startswith('/arac/') or re.fullmatch(r'/araclar\?musteri=\d{1,9}',v)) and '//' not in v and len(v)<80 else None
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
        ga=_zaman_duzelt(ga); gi=_zaman_duzelt(gi) if gi else None
        if not ga or (f.get('gidis_at') and not gi): flash('Tarih/saat biçimi geçersiz.','danger'); return redirect(url_for('is_emri_duzenle',is_emri_id=is_emri_id,geri=geri))
        if durum=='Tamamlandı' and not gi: gi=now()      # tamamlandıysa teslim zamanı boş kalmasın
        if durum!='Tamamlandı': gi=None                   # yeniden açılan iş emrinde eski teslim zamanı kalmasın
        km=re.sub(r'\D','',f.get('giris_km','')) or None
        if not km: flash('Giriş KM zorunludur.','danger'); return redirect(url_for('is_emri_duzenle',is_emri_id=is_emri_id,geri=geri))
        if len(str(int(km)))>7: flash('Giriş KM çok büyük görünüyor, kontrol et.','danger'); return redirect(url_for('is_emri_duzenle',is_emri_id=is_emri_id,geri=geri))
        km=str(int(km))
        db.execute('''UPDATE is_emirleri SET arac_id=?,gelis_at=?,giris_km=?,gidis_at=?,gelis_nedeni=?,yapilan_islem=?,durum=?,notlar=?,guncellendi_at=?,tarih=? WHERE id=?''',(f.get('arac_id'),ga,km,gi,f.get('gelis_nedeni','').strip()[:500],f.get('yapilan_islem','').strip()[:500] or None,durum,f.get('notlar','').strip()[:1000],now(),ga[:10],is_emri_id))
        for aid_ in {i['arac_id'],int(f.get('arac_id'))}: arac_km_guncelle(db,aid_)
        db.commit(); log_olay(f'İş emri #{is_emri_id} düzenlendi'); flash('İş emri güncellendi.','success'); return redirect(geri or url_for('is_emirleri'))
    return render_template('is_emri_duzenle.html',i=i,geri=geri,sik_islemler=sik_islemler(db),ozel_islemler=[r[0] for r in db.execute('SELECT ad FROM ozel_islem ORDER BY id')],islem_kategorileri=ISLEM_KATEGORILERI,arac_listesi=araclar_(),durum_secenekleri=DURUM_SECENEKLERI)
@app.route('/is-emirleri/durum/<int:is_emri_id>',methods=['POST'])
@login_required
def is_emri_durum_guncelle(is_emri_id):
    f=request.form; d=f.get('durum'); db=get_db()
    sk=_sekme(); geri=_geri_url(f.get('geri'))
    if d not in DURUM_SECENEKLERI: flash('Geçersiz durum.','danger'); return redirect(url_for('is_emirleri',g=sk))
    pl=db.execute('SELECT a.plaka FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id WHERE i.id=?',(is_emri_id,)).fetchone()
    if not pl: abort(404)
    t=now()
    # Tamamlandı'ya geçince teslim zamanı yazılır (varsa korunur); başka duruma dönülürse teslim zamanı temizlenir.
    db.execute("UPDATE is_emirleri SET durum=?,gidis_at=CASE WHEN ?='Tamamlandı' THEN COALESCE(gidis_at,?) ELSE NULL END,guncellendi_at=? WHERE id=?",(d,d,t,t,is_emri_id))
    log_olay(f'İş emri #{is_emri_id} durumu: {d}')
    db.commit()
    flash(f"{plaka_goster(pl['plaka'])}: {({'Beklemede':'beklemeye alındı','Devam Ediyor':'işe başlandı','Tamamlandı':'teslim edildi'})[d]}",'success')
    return redirect(geri or (url_for('is_emirleri',g=sk)+'#liste'))
@app.route('/is-emirleri/sil/<int:is_emri_id>',methods=['POST'])
@login_required
def is_emri_sil(is_emri_id):
    db=get_db(); log_olay(f'SİL: İş emri #{is_emri_id}')
    i=db.execute('SELECT i.*,a.plaka FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id WHERE i.id=?',(is_emri_id,)).fetchone()
    if i:
        v={k:i[k] for k in i.keys() if k!='plaka'}; cop_at(db,'is_emirleri',v,f"{plaka_goster(i['plaka'])} · {(i['yapilan_islem'] or i['gelis_nedeni'] or 'İşlem belirtilmemiş')[:60]} · {(i['gelis_at'] or '')[:10]}")
    db.execute('DELETE FROM is_emirleri WHERE id=?',(is_emri_id,))
    if i: arac_km_guncelle(db,i['arac_id'])
    db.commit(); flash('İş emri silindi. (Silinenler sayfasından 30 gün içinde geri getirilebilir.)','success'); return redirect(url_for('is_emirleri'))

# ===================== USB ETİKET YAZICI (ham TSPL, bkz. etiket_yazici.py) =====================
# ===================== ETİKET (Bluetooth, telefondan) =====================
@app.route('/araclar/<int:arac_id>/tspl',methods=['POST'])
@login_required
def arac_tspl(arac_id):
    # Telefondan Bluetooth ile basım: sunucu etiketin ham TSPL baytlarını üretir, telefon (dükkanda) yazıcıya kendisi gönderir.
    a=get_db().execute('SELECT a.plaka,a.qr_token FROM araclar a WHERE a.id=?',(arac_id,)).fetchone()
    if not a: abort(404)
    try: adet=min(max(int(request.form.get('adet','1') or 1),1),20)
    except ValueError: adet=1
    try: veri=EY.tspl_bayt(EY.tspl_komutlari(a['plaka'],public_url(a),g.dukkan['ad']),adet)
    except Exception as e:  # noqa: BLE001
        app.logger.exception('TSPL hazırlanamadı: %r',e); return jsonify(ok=False,mesaj='Etiket hazırlanamadı (iç hata).'),500
    log_olay(f'Etiket Bluetooth için hazırlandı: {a["plaka"]} x{adet}')
    return jsonify(ok=True,veri=base64.b64encode(veri).decode('ascii'),adet=adet)
@app.route('/araclar/<int:arac_id>/etiket_onizleme.png')
@login_required
def arac_etiket_onizleme(arac_id):
    a=get_db().execute('SELECT plaka,qr_token FROM araclar WHERE id=?',(arac_id,)).fetchone()
    if not a: abort(404)
    return Response(EY.onizleme_png(EY.tspl_komutlari(a['plaka'],public_url(a),g.dukkan['ad'])),mimetype='image/png')

def api_login_required(v):
    # Sayfa yönlendirmesi yerine JSON 401 döner (fetch ile çağrıldığı için).
    @wraps(v)
    def w(*a,**kw):
        if not giris_var(): return jsonify(ok=False,hata='Oturum süresi dolmuş. Sayfayı yenileyip tekrar giriş yap.'),401
        return v(*a,**kw)
    return w

# ===================== YAZDIRMA AJANI (dükkân bilgisayarındaki USB yazıcı) =====================
# Sunucu dükkân dışında olduğu için yazıcıya doğrudan erişemez. Dükkân bilgisayarında çalışan küçük "ajan" sunucuya kendisi bağlanır
# (dışarı doğru HTTPS; modemden port açmak gerekmez), kuyruktaki etiketi alır ve yazıcıya ham TSPL olarak gönderir.
# Kimlik: dükkâna özel ajan anahtarı (ya_<dükkân kodu>_<rastgele>), yalnız yönetici üretir; API anahtarından bağımsızdır.
AJAN_BEKLEYEN_SN=1800        # bu süre içinde alınmayan etiket "süresi doldu" olur (bilgisayar kapalıysa yığılıp sonra toplu basılmasın)
AJAN_ALINAN_SN=120           # alınıp sonuç gelmeyen iş: basılmış olabilir, tekrar BASILMAZ; "emin değil" olarak işaretlenir
AJAN_SINIR=20                # kuyrukta en çok bu kadar bekleyen iş
AJAN_BAGLI_SN=45             # ajan bu süre içinde sorduysa "bağlı" sayılır
_ajan_son={}                 # dükkân id -> son sorgu zamanı (bellekte; yeniden başlatmada sıfırlanır)
def ajan_bagli(dukkan_id):
    t=_ajan_son.get(dukkan_id); return bool(t) and time.time()-t<AJAN_BAGLI_SN
_ajan_sil_son={}             # dükkân id -> eski kayıtların en son silindiği zaman (saatte bir)
def _ajan_temizle(db):
    """Süresi dolan işleri 'hata' yapar. Sorgu/yoklama sık olduğu için önce OKUR; yazma yalnız gerçekten gerekirse (SQLite yazma kilidi boşuna alınmaz)."""
    sn=lambda n:(datetime.now()-timedelta(seconds=n)).strftime('%Y-%m-%d %H:%M:%S')
    b,a=sn(AJAN_BEKLEYEN_SN),sn(AJAN_ALINAN_SN)
    if db.execute("SELECT 1 FROM yazdirma_isleri WHERE (durum='bekliyor' AND olusturuldu_at<?) OR (durum='alindi' AND alindi_at<?) LIMIT 1",(b,a)).fetchone():
        db.execute("UPDATE yazdirma_isleri SET durum='hata',mesaj=?,bitti_at=? WHERE durum='bekliyor' AND olusturuldu_at<?",('Süresi doldu: dükkân bilgisayarı etiketi almadı (kapalı ya da ajan çalışmıyor).',now(),b))
        db.execute("UPDATE yazdirma_isleri SET durum='hata',mesaj=?,bitti_at=? WHERE durum='alindi' AND alindi_at<?",('Yazıcıdan yanıt gelmedi. Etiket çıkmış olabilir; kontrol et, çıkmadıysa tekrar bas.',now(),a))
        db.commit()
    dk=g.dukkan['id']
    if time.time()-_ajan_sil_son.get(dk,0)>3600:
        _ajan_sil_son[dk]=time.time()
        db.execute("DELETE FROM yazdirma_isleri WHERE olusturuldu_at<?",((datetime.now()-timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'),)); db.commit()
@app.route('/araclar/<int:arac_id>/yazdir',methods=['POST'])
@login_required
def arac_yazdir(arac_id):
    if not g.dukkan.get('ajan_hash'): return jsonify(ok=False,mesaj='Dükkân bilgisayarından basım bu dükkân için kapalı. Yöneticiden "yazdırma ajanı" iste.'),400
    db=get_db(); a=db.execute('SELECT a.plaka,a.qr_token FROM araclar a WHERE a.id=?',(arac_id,)).fetchone()
    if not a: abort(404)
    try: adet=min(max(int(request.form.get('adet','1') or 1),1),20)
    except ValueError: adet=1
    _ajan_temizle(db)
    var=db.execute("SELECT id FROM yazdirma_isleri WHERE arac_id=? AND adet=? AND durum='bekliyor' ORDER BY id DESC LIMIT 1",(arac_id,adet)).fetchone()
    if var: return jsonify(ok=True,is_id=var['id'],bagli=ajan_bagli(g.dukkan['id']),bekleyen=True)       # aynı etiket zaten bekliyor (bilgisayar kapalıyken art arda dokunuş yığılmaz)
    if db.execute("SELECT COUNT(*) FROM yazdirma_isleri WHERE durum IN ('bekliyor','alindi')").fetchone()[0]>=AJAN_SINIR:
        return jsonify(ok=False,mesaj='Kuyrukta çok etiket bekliyor. Dükkân bilgisayarı açık ve ajan çalışıyor mu?'),429
    try: veri=EY.tspl_bayt(EY.tspl_komutlari(a['plaka'],public_url(a),g.dukkan['ad']),adet)
    except Exception as e:  # noqa: BLE001
        app.logger.exception('TSPL hazırlanamadı: %r',e); return jsonify(ok=False,mesaj='Etiket hazırlanamadı (iç hata).'),500
    i=db.execute('INSERT INTO yazdirma_isleri(olusturuldu_at,arac_id,plaka,adet,veri) VALUES(?,?,?,?,?)',(now(),arac_id,a['plaka'],adet,base64.b64encode(veri).decode('ascii'))).lastrowid; db.commit()
    log_olay(f'Etiket kuyruğa alındı (dükkân bilgisayarı): {a["plaka"]} x{adet}')
    return jsonify(ok=True,is_id=i,bagli=ajan_bagli(g.dukkan['id']))
@app.route('/yazdirma/<int:is_id>/durum')
@api_login_required
def yazdirma_durum(is_id):
    db=get_db(); _ajan_temizle(db)
    r=db.execute('SELECT durum,mesaj FROM yazdirma_isleri WHERE id=?',(is_id,)).fetchone()
    if not r: return jsonify(ok=False,durum='yok',mesaj='İş bulunamadı.'),404
    return jsonify(ok=True,durum=r['durum'],mesaj=r['mesaj'] or '',bagli=ajan_bagli(g.dukkan['id']))
def _ajan_kimlik():
    """Ajan anahtarından dükkânı bulur ve g.dukkan'a koyar. Hata varsa (yanıt, kod) döner; yoksa None."""
    sema=(request.headers.get('X-Forwarded-Proto','').split(',')[0].strip().lower() or ('http' if '"scheme":"http"' in request.headers.get('CF-Visitor','').replace(' ','') else ''))
    if ENT_HTTPS_ZORUNLU and sema=='http': return jsonify(ok=False,kod='HTTPS_REQUIRED',hata='Yalnızca HTTPS ile kullanılır (https://… adresi).'),400
    ip='ajan:'+str(client_ip()); simdi=time.time()       # muhasebe API'siyle sayaç paylaşılmaz (ortak IP'de biri diğerini kilitlemesin)
    if len(_ent_hatali)>500:
        for _k in [k for k,t in _ent_hatali.items() if not t or simdi-t[-1]>=300]: _ent_hatali.pop(_k,None)
    _ent_hatali[ip]=[t for t in _ent_hatali.get(ip,[]) if simdi-t<300]
    if len(_ent_hatali[ip])>=10: return jsonify(ok=False,kod='RATE_LIMITED',hata='Çok fazla hatalı anahtar denemesi, 5 dakika sonra tekrar dene.'),429
    verilen=(request.headers.get('X-API-Key') or '').strip(); yet=request.headers.get('Authorization','')
    if not verilen and yet.lower().startswith('bearer '): verilen=yet[7:].strip()
    m=re.fullmatch(r'ya_([a-z0-9]{4})_[A-Za-z0-9_-]{20,64}',verilen or '')
    d=dukkan_kod_ile(m.group(1)) if m else None
    if not d or not d['aktif'] or not d.get('ajan_hash') or not secrets.compare_digest(hashlib.sha256(verilen.encode()).hexdigest(),d['ajan_hash']):
        _ent_hatali[ip].append(simdi); app.logger.info('Yazdırma ajanı: geçersiz anahtar | ip=%s',ip[5:]); return jsonify(ok=False,kod='INVALID_API_KEY',hata='Geçersiz ajan anahtarı.'),401
    g.dukkan=d
    if d['id'] in BOZUK_DUKKAN: return jsonify(ok=False,kod='SERVER_ERROR',hata='Bu dükkânın veritabanı şu an açılamıyor.'),503
    _ajan_son[d['id']]=time.time(); return None
@app.route('/api/v1/ajan/ping',methods=['POST'])
def ajan_ping():
    h=_ajan_kimlik()
    if h: return h
    return jsonify(ok=True,dukkan=g.dukkan['ad'])          # kurulumda anahtar/adres denemesi: kuyruğa dokunmaz
@app.route('/api/v1/ajan/sonraki',methods=['POST'])
def ajan_sonraki():
    h=_ajan_kimlik()
    if h: return h
    db=get_db(); _ajan_temizle(db)
    r=db.execute("SELECT id,plaka,adet,veri FROM yazdirma_isleri WHERE durum='bekliyor' ORDER BY id LIMIT 1").fetchone()
    if r and db.execute("UPDATE yazdirma_isleri SET durum='alindi',alindi_at=? WHERE id=? AND durum='bekliyor'",(now(),r['id'])).rowcount==1:
        db.commit(); return jsonify({'ok':True,'is':{'id':r['id'],'plaka':r['plaka'],'adet':r['adet'],'veri':r['veri']}})
    return jsonify({'ok':True,'is':None})
@app.route('/api/v1/ajan/sonuc',methods=['POST'])
def ajan_sonuc():
    h=_ajan_kimlik()
    if h: return h
    d=request.get_json(silent=True)
    if not isinstance(d,dict): return jsonify(ok=False,hata='Gövde JSON nesnesi olmalı.'),400
    try: i=int(d.get('id'))
    except (TypeError,ValueError,OverflowError): return jsonify(ok=False,hata='id geçersiz.'),400
    ok=d.get('ok') is True or str(d.get('ok')).strip().lower() in ('1','true','evet')      # "false" metni doğru sayılmaz
    mesaj=re.sub(r'\s+',' ',str(d.get('mesaj') or '')).strip()[:200]
    db=get_db(); r=db.execute('SELECT plaka,adet FROM yazdirma_isleri WHERE id=?',(i,)).fetchone()
    if not r: return jsonify(ok=False,hata='İş bulunamadı.'),404
    n=db.execute("UPDATE yazdirma_isleri SET durum=?,mesaj=?,bitti_at=? WHERE id=? AND durum IN ('alindi','hata')",('basildi' if ok else 'hata',None if ok else (mesaj or 'Yazıcıya gönderilemedi.'),now(),i)).rowcount; db.commit()
    if n: log_olay(f'Etiket {"basıldı" if ok else "BASILAMADI"} (dükkân bilgisayarı): {r["plaka"]} x{r["adet"]}'+('' if ok else f' · {mesaj}'))      # değişmeyen işe sonuç gelirse kayıt yazılmaz
    return jsonify(ok=True,uygulandi=bool(n))

# ===================== HIZLI İŞ EMRİ (tek ekran) =====================
def arac_bul(db,plaka):
    sel="SELECT a.*,m.ad_soyad,m.telefon FROM araclar a JOIN musteriler m ON m.id=a.musteri_id WHERE "
    r=db.execute(sel+"a.plaka=?",(plaka,)).fetchone()       # plakalar normalize saklanır -> UNIQUE indeksle anında
    return r or db.execute(sel+"REPLACE(REPLACE(a.plaka,' ',''),'-','')=?",(plaka,)).fetchone()   # normalize edilememiş eski kayıt için
def musteri_bul_tel(db,tel):
    for m in db.execute("SELECT id,ad_soyad,telefon FROM musteriler WHERE telefon IS NOT NULL AND telefon!=''"):
        if temiz_tel(m['telefon'])==tel: return m
    return None

def islem_ekle_kaydet(db,ham):
    """Eklediklerim listesine işlem ekler. (hata_metni|None, ad, yeni_mi) döner; iş emri sayfası ve Eklediklerim sayfası aynı kuralı kullanır."""
    ad=re.sub(r'\s+',' ',str(ham or '')).strip().strip(',')[:40]
    if len(ad)<2: return 'En az 2 harf yaz.',ad,False
    ad=ad[:1].replace('i','İ').upper()+ad[1:]
    var={fold(x):x for x in tum_islemler(db)}          # Türkçe harf/büyük-küçük duyarsız: "LPG TANK DEĞİŞİMİ" = "Lpg tank değişimi"
    if fold(ad) in var: return None,var[fold(ad)],False
    db.execute('INSERT OR IGNORE INTO ozel_islem(ad,olusturuldu_at) VALUES(?,?)',(ad,now())); db.commit(); log_olay(f'Yeni işlem eklendi: {ad}')
    return None,ad,True
@app.route('/api/islem-ekle',methods=['POST'])
@api_login_required
def api_islem_ekle():
    hata,ad,yeni=islem_ekle_kaydet(get_db(),(request.get_json(silent=True) or {}).get('ad'))
    if hata: return jsonify(ok=False,hata=hata),400
    return jsonify(ok=True,ad=ad,yeni=yeni)
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

# ===================== CİHAZ ADI + HAREKET KAYDI (hangi cihaz ne yaptı) =====================
# Telefon/bilgisayar ilk girişte kendine ad verir ("Usta telefonu"). Ad sunucuda durur; telefonda yalnızca imzalı bir kimlik (cihaz kartı, 400 gün) bulunur.
# Aynı ad birden çok cihazda kullanılabilir; ayırt etmek için adın yanında kısa kod (#7F3A) görünür. Kayıtlar HAREKET_GUN gün saklanır, sonra silinir.
# Hareket kaydında müşteri adı ve telefon YOKTUR; yalnızca plaka, kayıt numarası, cihaz, IP ve ne yapıldığı yazılır.
CIHAZ_COOKIE='cihaz'; CIHAZ_OMUR=400*24*3600; HAREKET_GUN=180      # tarayıcılar çerez ömrünü en fazla ~400 güne indirir
HAREKET_ATLA=('Giriş başarısız','ENTEGRASYON geçersiz')                # saldırı denemeleri veritabanını şişirmesin (dosya günlüğünde kalır)
_cihaz_ser=URLSafeSerializer(SECRET_KEY,salt='servis-cihaz-v1')
_hareket_temizlendi={}
def _cihaz_dukkan():
    d=g.get('dukkan'); return d['id'] if d else 0          # çok dükkânlı: kart yalnızca kendi dükkânında geçerli
def _cihaz_cookie_yaz(r,cid):
    k=get_db().execute('SELECT kod FROM cihazlar WHERE id=?',(cid,)).fetchone()      # kod da imzalanır: veritabanı yedekten dönse bile kart başka cihazın adını almaz
    r.set_cookie(CIHAZ_COOKIE,_cihaz_ser.dumps({'i':cid,'d':_cihaz_dukkan(),'k':k['kod'] if k else ''}),max_age=CIHAZ_OMUR,httponly=True,samesite='Lax',secure=bool(app.config.get('SESSION_COOKIE_SECURE')))
def _cihaz_oku():
    """Cihaz kartından (imzalı çerez) bu cihazın kaydını döner; kart yoksa/bozuksa None."""
    if '_cihaz' in g: return g._cihaz
    c=None; v=request.cookies.get(CIHAZ_COOKIE)
    if v:
        try:
            p=_cihaz_ser.loads(v)
            if isinstance(p,dict) and p.get('d')==_cihaz_dukkan():
                c=get_db().execute('SELECT id,ad,kod,son_gorulme_at FROM cihazlar WHERE id=?',(int(p.get('i')),)).fetchone()
                if c and p.get('k',c['kod'])!=c['kod']: c=None
        except (BadSignature,ValueError,TypeError): c=None
    g._cihaz=c; return c
def _cihaz_etiket(c): return f"{c['ad']} · #{c['kod']}"
def _cihaz_ad_temiz(v):
    ad=re.sub(r'\s+',' ',str(v or '')).strip()
    return ad if 2<=len(ad)<=30 and ad.isprintable() else None
def _cihaz_geri(v):
    v=str(v or ''); return v if v.startswith('/') and not v.startswith('//') and '\\' not in v and len(v)<200 and v.isprintable() else url_for('dashboard')
def _hareket_kuyruk(mesaj):
    """log_olay'dan çağrılır: olayı cihaz bilgisiyle sıraya alır; yanıt başarıyla bitince hareket_yaz veritabanına yazar."""
    if not has_request_context() or str(mesaj).startswith(HAREKET_ATLA): return
    try:
        if request.path.startswith('/api/v1/ajan/'): cid,et=None,'Yazdırma ajanı (dükkân bilgisayarı)'
        elif request.path.startswith('/api/v1/'): cid,et=None,'Dış sistem (API)'
        else:
            c=_cihaz_oku() if g.get('dukkan') else None      # imzalı cihaz kartı yeterli: giriş anında da cihaz adı yazılır
            cid,et=(c['id'],_cihaz_etiket(c)) if c else (None,'—')
        g.setdefault('_hareket',[]).append((now(),cid,et,str(client_ip())[:45],str(mesaj)[:300]))
    except Exception: app.logger.exception('Hareket sıraya alınamadı')
@app.after_request
def hareket_yaz(r):
    try:
        if not g.get('dukkan'): g.pop('_hareket',None); return r        # dükkân oturumu yoksa (ör. düşmüş oturumdan çıkış) kayıt yazılmaz
        olaylar=g.pop('_hareket',None); c=g.get('_cihaz'); yaz=bool(olaylar) and r.status_code<400
        yenile=bool(c) and (c['son_gorulme_at'] or '')[:10]!=now()[:10]       # günde bir: son görülme + kartın ömrünü yenile
        if yaz or yenile:
            db=get_db()
            if not db.in_transaction:
                if yaz: db.executemany('INSERT INTO hareketler(zaman,cihaz_id,cihaz,ip,olay) VALUES(?,?,?,?,?)',olaylar)
                if yenile: db.execute('UPDATE cihazlar SET son_gorulme_at=? WHERE id=?',(now(),c['id'])); _cihaz_cookie_yaz(r,c['id'])
                gun=now()[:10]; anahtar=_cihaz_dukkan()
                if _hareket_temizlendi.get(anahtar)!=gun:
                    sinir=(datetime.now()-timedelta(days=HAREKET_GUN)).strftime('%Y-%m-%d %H:%M:%S'); db.execute('DELETE FROM hareketler WHERE zaman<?',(sinir,))
                    db.execute('DELETE FROM cihazlar WHERE son_gorulme_at<? AND id NOT IN (SELECT DISTINCT cihaz_id FROM hareketler WHERE cihaz_id IS NOT NULL)',(sinir,)); _hareket_temizlendi[anahtar]=gun      # kullanılmayan eski cihaz kartları da temizlenir
                db.commit()
    except Exception: app.logger.exception('Hareket kaydı yazılamadı')
    return r
_CIHAZ_MUAF=('static','login','logout','saglik','qr_arac','anasayfa','cihaz_adi','cihaz_adi_kaydet','sifre_degistir')
@app.before_request
def cihaz_kapisi():
    """Giriş yapmış ama adı olmayan cihazı 'Bu cihaza ad ver' sayfasına yönlendirir (atlanamaz)."""
    if not app.config.get('CIHAZ_KAPISI',True): return
    ep=request.endpoint or ''
    if ep in _CIHAZ_MUAF or ep.startswith(('yonetici','ent_')) or request.path.startswith('/api/v1/'): return
    if not giris_var() or _cihaz_oku(): return
    if request.path.startswith('/api/'): return jsonify(ok=False,hata='Önce bu cihaza ad ver: sayfayı yenile.'),403
    if request.method!='GET': flash('Önce bu cihaza bir ad ver, sonra işlemi tekrarla.','warning'); return redirect(url_for('cihaz_adi'))
    return redirect(url_for('cihaz_adi',geri=request.full_path.rstrip('?')))
@app.route('/cihaz-adi')
@login_required
def cihaz_adi():
    if _cihaz_oku(): return redirect(url_for('dashboard'))
    return render_template('cihaz_adi.html',geri=_cihaz_geri(request.args.get('geri')) if request.args.get('geri') else '')
@app.route('/cihaz-adi',methods=['POST'])
@login_required
def cihaz_adi_kaydet():
    if _cihaz_oku(): return redirect(url_for('dashboard'))
    ad=_cihaz_ad_temiz(request.form.get('ad'))
    if not ad: flash('Cihaz adı 2-30 karakter olmalı.','danger'); return redirect(url_for('cihaz_adi'))
    db=get_db()
    for _ in range(20):
        kod=secrets.token_hex(2).upper()
        if not db.execute('SELECT 1 FROM cihazlar WHERE kod=?',(kod,)).fetchone(): break
    cid=db.execute('INSERT INTO cihazlar(ad,kod,olusturuldu_at,son_gorulme_at) VALUES(?,?,?,?)',(ad,kod,now(),now())).lastrowid; db.commit()
    g._cihaz={'id':cid,'ad':ad,'kod':kod,'son_gorulme_at':now()}
    log_olay(f'Cihaz adı verildi: {ad} #{kod}')
    r=redirect(_cihaz_geri(request.form.get('geri'))); _cihaz_cookie_yaz(r,cid); return r
@app.route('/hareketler')
@login_required
def hareketler():
    db=get_db(); s=min(100000,max(1,request.args.get('s',1,type=int) or 1)); cid=request.args.get('cihaz',type=int)
    w=' WHERE h.cihaz_id=?' if cid else ''; par=([cid] if cid else [])+[(s-1)*100]
    satir=db.execute("""SELECT h.zaman,COALESCE(c.ad||' · #'||c.kod,h.cihaz) cihaz,h.ip,h.olay FROM hareketler h LEFT JOIN cihazlar c ON c.id=h.cihaz_id"""+w+' ORDER BY h.id DESC LIMIT 101 OFFSET ?',par).fetchall()
    cihazlar=db.execute('SELECT c.id,c.ad,c.kod,c.son_gorulme_at son,(SELECT COUNT(*) FROM hareketler h WHERE h.cihaz_id=c.id) n FROM cihazlar c ORDER BY c.son_gorulme_at DESC').fetchall()
    return render_template('hareketler.html',satir=satir[:100],sonra=len(satir)>100,sayfa=s,cihazlar=cihazlar,cid=cid,ben=_cihaz_oku(),gun=HAREKET_GUN)
@app.route('/hareketler/cihaz/<int:cid>',methods=['POST'])
@login_required
def hareketler_cihaz_ad(cid):
    db=get_db(); c=db.execute('SELECT id,ad,kod FROM cihazlar WHERE id=?',(cid,)).fetchone()
    if not c: abort(404)
    ad=_cihaz_ad_temiz(request.form.get('ad'))
    if not ad: flash('Cihaz adı 2-30 karakter olmalı.','danger'); return redirect(url_for('hareketler'))
    db.execute('UPDATE cihazlar SET ad=? WHERE id=?',(ad,cid)); db.commit(); log_olay(f'Cihaz yeniden adlandırıldı: {c["ad"]} → {ad} #{c["kod"]}')
    flash('Cihaz adı güncellendi.','success'); return redirect(url_for('hareketler'))

# ===================== EKLEDİKLERİM (kendi işlem listem) =====================
@app.route('/eklediklerim')
@login_required
def eklediklerim():
    return render_template('eklediklerim.html',liste=get_db().execute('SELECT id,ad FROM ozel_islem ORDER BY ad COLLATE NOCASE').fetchall())
@app.route('/eklediklerim/ekle',methods=['POST'])
@login_required
def eklediklerim_ekle():
    # virgülle ayrılmış birden çok işlem aynı anda eklenebilir: "Lpg tank, Egzoz kaynağı"
    eklenen=[]; var=[]
    for parca in request.form.get('ad','').split(','):
        if not parca.strip(): continue
        hata,ad,yeni=islem_ekle_kaydet(get_db(),parca)
        if hata: flash(f'“{parca.strip()}”: {hata}','danger'); continue
        (eklenen if yeni else var).append(ad)
    if eklenen: flash('Eklendi: '+', '.join(eklenen),'success')
    if var: flash('Zaten listede var: '+', '.join(var),'warning')
    if not eklenen and not var and not request.form.get('ad','').strip(): flash('Eklemek için bir işlem yaz.','danger')
    return redirect(url_for('eklediklerim'))
@app.route('/eklediklerim/sil/<int:islem_id>',methods=['POST'])
@login_required
def eklediklerim_sil(islem_id):
    db=get_db(); r=db.execute('SELECT ad FROM ozel_islem WHERE id=?',(islem_id,)).fetchone()
    if not r: abort(404)
    db.execute('DELETE FROM ozel_islem WHERE id=?',(islem_id,)); db.commit(); log_olay(f'Eklenen işlem silindi: {r["ad"]}')
    flash(f'Silindi: {r["ad"]} (eski iş emirleri değişmez).','success'); return redirect(url_for('eklediklerim'))

ISIMSIZ_ON_EK='İSİMSİZ'   # isim girilmeden açılan kayıtlarda müşteri adı: "İSİMSİZ"
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
    if not km: return hata('Giriş KM zorunludur.')
    if len(km)>7: return hata('Giriş KM çok büyük görünüyor, kontrol et.')
    km=str(int(km))
    marka=marka_al(form); model=form['model'][:40].strip()
    db=get_db(); t=now(); yeni_arac=False; notu=''
    try:
        a=arac_bul(db,plaka)
        if a:
            arac_id=a['id']; ad=a['ad_soyad']
            if not ((a['marka'] or '').strip() and (a['model'] or '').strip()):      # kayıtlı ama marka/model eksik araç: şimdi tamamlanır
                marka=marka or (a['marka'] or '').strip(); model=model or (a['model'] or '').strip()
                if marka or model: db.execute('UPDATE araclar SET marka=?,model=?,guncellendi_at=? WHERE id=?',(marka,model,t,arac_id))
            tel=temiz_tel(form['telefon'])
            if tel and not TEL_RE.match(tel): return hata('Telefon geçersiz. Örnek: 0532 111 22 33 (boş bırakabilirsin).')
            if TEL_RE.match(tel) and not (a['telefon'] or '').strip():
                db.execute('UPDATE musteriler SET telefon=?,guncellendi_at=? WHERE id=?',(tel,t,a['musteri_id']))
            yeni_ad=tr_upper(form['musteri_ad'])[:100]
            if yeni_ad and (a['ad_soyad'] or '').startswith(ISIMSIZ_ON_EK):   # önceden isimsiz açılmış araç: isim şimdi girildiyse güncelle
                db.execute('UPDATE musteriler SET ad_soyad=?,guncellendi_at=? WHERE id=?',(yeni_ad,t,a['musteri_id'])); ad=yeni_ad
        else:
            # İsim, telefon, marka ve model zorunlu DEĞİL. Girildiyse telefon biçimi doğrulanır; isim boşsa plakadan geçici bir ad verilir.
            ad=tr_upper(form['musteri_ad'])[:100]; tel=temiz_tel(form['telefon'])
            if tel and not TEL_RE.match(tel): return hata('Telefon geçersiz. Örnek: 0532 111 22 33 (boş bırakabilirsin).')
            m=musteri_bul_tel(db,tel) if tel else None
            if m: mid=m['id']; notu=f' (telefon {m["ad_soyad"]} adına kayıtlıydı, araç ona eklendi)'; ad=m['ad_soyad']
            else:
                if not ad: ad=ISIMSIZ_ON_EK        # isim boşsa yalnızca "İSİMSİZ" yazılır; plaka AYRI alanda tutulur, isme karışmaz
                mid=db.execute('INSERT INTO musteriler(ad_soyad,telefon,olusturuldu_at,guncellendi_at) VALUES(?,?,?,?)',(ad,tel or None,t,t)).lastrowid
            arac_id=db.execute('INSERT INTO araclar(musteri_id,plaka,marka,model,kilometre,lpg_durumu,qr_token,olusturuldu_at,guncellendi_at) VALUES(?,?,?,?,?,0,?,?,?)',(mid,plaka,marka,model,km,yeni_token(g.dukkan['kod']),t,t)).lastrowid; yeni_arac=True
        db.execute('INSERT INTO is_emirleri(arac_id,tarih,gelis_nedeni,durum,notlar,gelis_at,giris_km,olusturuldu_at,guncellendi_at,kaynak) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (arac_id,t[:10],form['gelis_nedeni'][:500],'Devam Ediyor',form['notlar'][:1000],t,km,t,t,'form'))
        arac_km_guncelle(db,arac_id)
        db.commit()
    except sqlite3.Error:
        db.rollback(); app.logger.exception('Hızlı iş emri DB hatası')
        return hata('Kaydedilemedi (veritabanı hatası). Tekrar dene.')
    log_olay(f'İş emri açıldı: {plaka_goster(plaka)}'+(' (yeni araç)' if yeni_arac else ''))
    if yeni_arac:    # yeni araç: doğrudan "Etiketi çıkar" ekranı (usta tek dokunuşla etiketi basar)
        return redirect(url_for('arac_qr',arac_id=arac_id,yeni=1))
    flash(f'İş emri açıldı: {plaka_goster(plaka)} — {ad}'+notu,'success')
    return redirect(url_for('is_emirleri'))

# ===================== DIŞ SİSTEM ENTEGRASYONU (muhasebe/servis yazılımı -> Servis Defteri) =====================
# Akış: usta Servis Defteri'nde plaka+km ile iş emrini açar; karşı sistem (ör. muhasebe programı) kayıt açınca POST /api/v1/is-emirleri çağırır.
# API YENİ İŞ EMRİ AÇMAZ: o plakanın TEK açık (Tamamlandı olmayan) iş emrini bulup kaydı ona işler. Etiket basılmaz.
# Tek güvenilir eşleşme yoksa (plaka kayıtsız / açık iş emri yok / birden fazla açık / km tutmuyor / iş emri çok eski) kayıt
# "Dış sistem" sayfasındaki Karar bekleyen sekmesine düşer (kalıcı olarak saklanır); kimse rastgele seçilmez.
# İŞLEM: karşı sistem (muhasebe) son karardır -> gelen "yapilan_islem" mevcut "Yapılan işlem" alanının YERİNE yazılır; eski metin nota "Önceki işlem: ..." diye saklanır.
# Ustanın "Ne yapılacak?" (gelis_nedeni) alanına dokunulmaz.
# Kimlik: API anahtarı (.env: ENTEGRASYON_API_ANAHTARI), "Authorization: Bearer <anahtar>" veya "X-API-Key". Anahtar yoksa uç nokta KAPALIDIR (404).
ENT_KM_TOLERANS=int(os.environ.get('ENTEGRASYON_KM_TOLERANS','50') or 50)        # ustanın km'si ile gelen km en çok bu kadar farklı olabilir
ENT_GUN_ARALIGI=float(os.environ.get('ENTEGRASYON_GUN_ARALIGI','5') or 5)        # açık iş emri bundan eskiyse (gün) otomatik bağlanmaz
ENT_KAYIT_NO_ZORUNLU=os.environ.get('ENTEGRASYON_KAYIT_NO_ZORUNLU','0').strip()=='1'
ENT_HTTPS_ZORUNLU=os.environ.get('ENTEGRASYON_HTTPS_ZORUNLU','1').strip()!='0'   # düz http gelirse anahtar kabul edilmez (HTTPS_REQUIRED)
ENT_YENI_KAYIT=os.environ.get('ENTEGRASYON_YENI_KAYIT','0').strip()=='1'         # 1: eşleşme yoksa yeni iş emri açılır (varsayılan 0: incelemeye alınır)
def _ent_acik():
    """API yalnızca en az bir dükkânın (açık) API anahtarı varsa çalışır; yoksa 404."""
    c=yonetim_db()
    try: return c.execute("SELECT 1 FROM dukkanlar WHERE aktif=1 AND api_hash IS NOT NULL AND api_hash!='' LIMIT 1").fetchone() is not None
    finally: c.close()
def _ent_dukkan(anahtar):
    """Anahtardan dükkânı bulur (anahtar: sk_<dükkân kodu>_<rastgele>); özeti sabit sürede karşılaştırır. Geçersizse None."""
    m=re.fullmatch(r'sk_([a-z0-9]{4})_[A-Za-z0-9_-]{20,64}',anahtar or '')
    d=dukkan_kod_ile(m.group(1)) if m else None
    if not d or not d['aktif'] or not d.get('api_hash'): return None
    return d if secrets.compare_digest(hashlib.sha256(anahtar.encode()).hexdigest(),d['api_hash']) else None
_ent_hatali={}
EMAIL_RE=re.compile(r'^[^@\s]{1,64}@[^@\s]{1,200}\.[^@\s]{2,}$')
_ENT_GIZLI_ALAN={'telefon','tel','adres','eposta','e-posta','email','phone','address'}
def _ent_maskele(govde):
    """Hata kaydına yazılacak ham gövdede telefon, adres ve e-postayı '***' yapar; kalanı (plaka, km, işlem, ad...) korur."""
    govde=str(govde or '')
    try:
        def m(o):
            if isinstance(o,dict): return {k:('***' if str(k).lower() in _ENT_GIZLI_ALAN and o[k] not in (None,'') else m(o[k])) for k in o}
            if isinstance(o,list): return [m(x) for x in o]
            return o
        return json.dumps(m(json.loads(govde)),ensure_ascii=False)
    except ValueError:
        if '=' in govde and ' ' not in govde.strip():                                          # form gövdesi (a=b&c=d): gizli alanların değerini '***' yap
            try:
                from urllib.parse import parse_qsl
                q=parse_qsl(govde,keep_blank_values=True)
                if q: return '&'.join(quote(str(k),safe='')+'='+('***' if str(k).strip().lower() in _ENT_GIZLI_ALAN and v!='' else quote(v,safe='')) for k,v in q)
            except ValueError: pass
        govde=re.sub(r'[^\s@&=<>"\']+@[^\s@&=<>"\']+','***',govde)   # ayrıştırılamayan gövdede e-posta biçimlilerini gizle
        return re.sub(r'\d[\d\s().+-]{6,}\d','***',govde)      # 7+ haneli rakam dizilerini gizle
def _ent_hata_kaydet(kayit_no,hata):
    try:
        db=get_db(); db.execute('INSERT INTO entegrasyon_hata(zaman,kayit_no,hata,govde) VALUES(?,?,?,?)',(now(),str(kayit_no or '')[:64],hata[:300],_ent_maskele(request.get_data(as_text=True) or (json.dumps(request.form.to_dict(),ensure_ascii=False) if request.form else ''))[:2000])); db.commit()
        db.execute('DELETE FROM entegrasyon_hata WHERE id NOT IN (SELECT id FROM entegrasyon_hata ORDER BY id DESC LIMIT 500)'); db.commit()
    except sqlite3.Error: app.logger.exception('entegrasyon_hata yazılamadı')
    log_olay(f'ENTEGRASYON [{g.dukkan["kullanici"]}] reddedildi ({kayit_no}): {hata}')
def _ent_zaman(x):
    """ISO 8601 (saat dilimli olabilir: 2026-10-22T14:30:00+03:00 / ...Z) veya 'YYYY-MM-DD HH:MM' -> yerel 'YYYY-MM-DD HH:MM:SS'; geçersizse None."""
    x=str(x or '').strip()
    if not x: return None
    try:
        dt=datetime.fromisoformat(x.replace('Z','+00:00'))
        if dt.tzinfo is not None:
            try:
                from zoneinfo import ZoneInfo; dt=dt.astimezone(ZoneInfo(SAAT_DILIMI))
            except Exception: dt=dt.astimezone()          # tzdata yoksa bilgisayarın yerel saati
            dt=dt.replace(tzinfo=None)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, OverflowError): return _zaman_duzelt(x)
def _km_rakam(v):
    """API'den gelen km'yi rakam dizisine çevirir: 45000.0 -> '45000'; '45.000' (binlik nokta) -> '45000'; '45000,5' -> '45000'."""
    if v is None or isinstance(v,bool): return ''
    if isinstance(v,(int,float)):
        try: return str(int(round(v))) if v>=0 else ''
        except (ValueError,OverflowError): return ''
    s=str(v).strip(); m=re.fullmatch(r'(\d+)[.,]\d{1,2}',s)
    return m.group(1) if m else re.sub(r'\D','',s)
def _dogru(v):
    """JSON/form değerini doğru/yanlış yapar: true, 1, 'true', 'evet' -> True; false, 0, 'false', '' -> False."""
    if isinstance(v,str): return v.strip().lower() in ('1','true','evet','on','yes')
    return bool(v)
def _ent_acik_isemirleri(db,arac_id):
    return db.execute("SELECT id,gelis_nedeni,yapilan_islem,notlar,giris_km,gelis_at,durum FROM is_emirleri WHERE arac_id=? AND durum!='Tamamlandı' ORDER BY COALESCE(gelis_at,tarih) DESC,id DESC",(arac_id,)).fetchall()
def _ent_isle(db,ie,v,t):
    """Gelen kaydı MEVCUT iş emrine işler. İşlem: muhasebe son karar (yerine yazılır, eski metin nota). Müşteri/araç: yalnızca BOŞ alanlar tamamlanır."""
    r=db.execute('SELECT i.yapilan_islem,i.notlar,i.giris_km,i.durum,i.gidis_at,i.arac_id,a.musteri_id,a.marka,a.model,m.ad_soyad,m.telefon,m.eposta,m.adres FROM is_emirleri i JOIN araclar a ON a.id=i.arac_id JOIN musteriler m ON m.id=a.musteri_id WHERE i.id=?',(ie,)).fetchone()
    yap=(r['yapilan_islem'] or '').strip(); notu=(r['notlar'] or '').strip(); ek=[]
    yeni=(v.get('yapilan') or '').strip()
    if yeni and yeni.lower()!=yap.lower():
        if yap: ek.append('Önceki işlem: '+yap)
        yap=yeni
    if v.get('notlar'): ek.append(v['notlar'])
    for e in ek:
        if e.lower() not in notu.lower(): notu=(notu+' | '+e if notu else e)
    durum=r['durum']; gidis=r['gidis_at']
    if v.get('durum') in DURUM_SECENEKLERI:
        durum=v['durum']; gidis=(v.get('gidis') or gidis or t) if durum=='Tamamlandı' else None
    db.execute("UPDATE is_emirleri SET yapilan_islem=?,notlar=?,giris_km=COALESCE(giris_km,?),durum=?,gidis_at=?,guncellendi_at=? WHERE id=?",(yap[:1000],notu[:1000],v.get('km'),durum,gidis,t,ie))
    if v.get('marka') and not (r['marka'] or '').strip(): db.execute('UPDATE araclar SET marka=?,guncellendi_at=? WHERE id=?',(v['marka'],t,r['arac_id']))
    if v.get('model') and not (r['model'] or '').strip(): db.execute('UPDATE araclar SET model=?,guncellendi_at=? WHERE id=?',(v['model'],t,r['arac_id']))
    for alan,sut in (('tel','telefon'),('eposta','eposta'),('adres','adres')):
        if v.get(alan) and not (r[sut] or '').strip(): db.execute(f'UPDATE musteriler SET {sut}=?,guncellendi_at=? WHERE id=?',(v[alan],t,r['musteri_id']))
    if v.get('ad') and (r['ad_soyad'] or '').startswith(ISIMSIZ_ON_EK): db.execute('UPDATE musteriler SET ad_soyad=?,guncellendi_at=? WHERE id=?',(v['ad'],t,r['musteri_id']))
    arac_km_guncelle(db,r['arac_id'])
def _ent_yeni_kayit(db,v,t):
    """Araç/iş emri açar (yalnızca incelemeden 'Yeni iş emri aç' denince ya da ENTEGRASYON_YENI_KAYIT=1 ile). (is_emri_id,arac_id,yeni_arac) döner. Etiket otomatik basılmaz."""
    plaka=v['plaka']; a=arac_bul(db,plaka); yeni=False
    if a: arac_id=a['id']
    else:
        m=musteri_bul_tel(db,v['tel']) if v.get('tel') else None
        mid=m['id'] if m else db.execute('INSERT INTO musteriler(ad_soyad,telefon,eposta,adres,olusturuldu_at,guncellendi_at) VALUES(?,?,?,?,?,?)',(v.get('ad') or ISIMSIZ_ON_EK,v.get('tel') or None,v.get('eposta') or None,v.get('adres') or None,t,t)).lastrowid
        arac_id=db.execute('INSERT INTO araclar(musteri_id,plaka,marka,model,kilometre,lpg_durumu,qr_token,olusturuldu_at,guncellendi_at) VALUES(?,?,?,?,?,0,?,?,?)',(mid,plaka,v.get('marka',''),v.get('model',''),v.get('km'),yeni_token(g.dukkan['kod']),t,t)).lastrowid; yeni=True
    durum=v.get('durum') if v.get('durum') in DURUM_SECENEKLERI else 'Devam Ediyor'; gelis=v.get('gelis') or t
    ie=db.execute('INSERT INTO is_emirleri(arac_id,tarih,gelis_nedeni,yapilan_islem,durum,notlar,gelis_at,gidis_at,giris_km,olusturuldu_at,guncellendi_at,kaynak) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
        (arac_id,gelis[:10],'',v.get('yapilan',''),durum,v.get('notlar',''),gelis,(v.get('gidis') or t) if durum=='Tamamlandı' else None,v.get('km'),t,t,'entegrasyon')).lastrowid
    arac_km_guncelle(db,arac_id); return ie,arac_id,yeni
@app.route('/api/v1/saglik',methods=['GET'])
def ent_saglik():
    if not _ent_acik(): abort(404)
    return jsonify(ok=True,hizmet='servis-defteri',surum=1)
@app.route('/api/v1/is-emirleri',methods=['POST'])
def ent_is_emri():
    if not _ent_acik(): abort(404)
    sema=(request.headers.get('X-Forwarded-Proto','').split(',')[0].strip().lower() or ('http' if '"scheme":"http"' in request.headers.get('CF-Visitor','').replace(' ','') else ''))
    if ENT_HTTPS_ZORUNLU and sema=='http': return jsonify(ok=False,kod='HTTPS_REQUIRED',hata='Bu API yalnızca HTTPS ile kullanılır. https://… adresini kullanın (API anahtarı düz http ile gönderilmemelidir).'),400
    ip=client_ip(); simdi=time.time()
    if len(_ent_hatali)>500:                                   # eski IP kayıtları birikmesin (bellek sınırı)
        for _k in [k for k,t in _ent_hatali.items() if not t or simdi-t[-1]>=300]: _ent_hatali.pop(_k,None)
    _ent_hatali[ip]=[t for t in _ent_hatali.get(ip,[]) if simdi-t<300]
    if len(_ent_hatali[ip])>=10: return jsonify(ok=False,kod='RATE_LIMITED',hata='Çok fazla hatalı anahtar denemesi, 5 dakika sonra tekrar dene.'),429,{'Retry-After':'300'}
    verilen=(request.headers.get('X-API-Key') or '').strip()
    yet=request.headers.get('Authorization','')
    if not verilen and yet.lower().startswith('bearer '): verilen=yet[7:].strip()
    dk=_ent_dukkan(verilen)
    if not dk:
        _ent_hatali[ip].append(simdi); log_olay('ENTEGRASYON geçersiz API anahtarı'); return jsonify(ok=False,kod='INVALID_API_KEY',hata='Geçersiz API anahtarı.'),401
    g.dukkan=dk
    if dk['id'] in BOZUK_DUKKAN: return jsonify(ok=False,kod='SERVER_ERROR',hata='Bu dükkânın veritabanı şu an açılamıyor; yöneticiye haber ver.'),503
    d=request.get_json(silent=True)
    if not isinstance(d,dict): d=request.values.to_dict()      # JSON yoksa düz form alanları da kabul
    if isinstance(d.get('yapilan_islem'),list): d['yapilan_islem']=', '.join(str(x) for x in d['yapilan_islem'])
    metin=lambda k,n: re.sub(r'\s+',' ',str(d.get(k) if d.get(k) is not None else '')).strip()[:n]
    plaka=temiz_plaka(metin('plaka',20)); km_ham=_km_rakam(d.get('km'))
    kayit_no=metin('kayit_no',64)
    if not kayit_no and plaka and not ENT_KAYIT_NO_ZORUNLU:      # numara gelmezse: YALNIZCA birebir aynı içerikli istek tekrar sayılır
        kayit_no='oto:'+hashlib.sha1(json.dumps({k:d[k] for k in sorted(d)},sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()[:24]
    def red(m,http=422,kod='VALIDATION_ERROR'): _ent_hata_kaydet(kayit_no,m); return jsonify(ok=False,kod=kod,hata=m),http
    if not plaka: return red('plaka zorunlu.')
    if not kayit_no: return red('kayit_no zorunlu (bu sunucuda ENTEGRASYON_KAYIT_NO_ZORUNLU=1).')
    if not PLAKA_RE.match(plaka) and not _dogru(d.get('ozel_plaka')): return red('Plaka biçimi geçersiz (örn. 35ABC123). Özel/yabancı plaka için "ozel_plaka": true gönder.')
    if len(plaka)>12: return red('Plaka çok uzun.')
    if len(km_ham)>7: return red('km çok büyük görünüyor.')
    durum=metin('durum',20)
    if durum and durum not in DURUM_SECENEKLERI: return red('durum geçersiz. Geçerli değerler: '+', '.join(DURUM_SECENEKLERI))
    gelis=_ent_zaman(d.get('gelis_zamani')); gidis=_ent_zaman(d.get('gidis_zamani'))
    if (d.get('gelis_zamani') and not gelis) or (d.get('gidis_zamani') and not gidis): return red('gelis_zamani/gidis_zamani geçersiz (ISO 8601, örn. 2026-10-22T14:30:00+03:00).')
    km=str(int(km_ham)) if km_ham else None
    tel=temiz_tel(metin('telefon',20)); tel=tel if TEL_RE.match(tel) else ''           # geçersiz telefon/e-posta yok sayılır
    eposta=metin('eposta',120); eposta=eposta if EMAIL_RE.match(eposta) else ''
    t=now(); v={'plaka':plaka,'km':km,'tel':tel,'eposta':eposta,'adres':metin('adres',300),'ad':tr_upper(metin('musteri_ad',100)),'marka':metin('marka',40),'model':metin('model',40),
        'yapilan':metin('yapilan_islem',1000),'notlar':metin('not',1000),'durum':durum,'gelis':gelis,'gidis':gidis}
    db=get_db()
    var=db.execute('SELECT is_emri_id,durum,veri FROM entegrasyon_kayit WHERE kayit_no=?',(kayit_no,)).fetchone()
    if var:
        try: ayni=json.loads(var['veri'] or '{}')==v
        except ValueError: ayni=True
        if not ayni: return jsonify(ok=False,kod='IDEMPOTENCY_CONFLICT',hata='Bu kayit_no daha önce FARKLI içerikle işlendi; kayıt değiştirilmedi. Düzeltme için yeni bir kayit_no kullanın veya Servis Defteri\'nden elle düzenleyin.',durum=var['durum'],is_emri_id=var['is_emri_id']),409
        return jsonify(ok=True,tekrar=True,durum=var['durum'],is_emri_id=var['is_emri_id'],mesaj='Bu kayit_no daha önce işlendi, tekrar işlem yapılmadı.'),200
    try:
        a=arac_bul(db,plaka); neden=None; ie=None
        if not a: neden='Bu plaka Servis Defteri\'nde kayıtlı değil.'
        else:
            acik=_ent_acik_isemirleri(db,a['id'])
            if not acik: neden='Bu plakanın açık iş emri yok.'
            elif len(acik)>1: neden=f'Bu plakada {len(acik)} açık iş emri var, hangisi olduğu belli değil.'
            elif km and acik[0]['giris_km'] and abs(int(acik[0]['giris_km'])-int(km))>ENT_KM_TOLERANS: neden=f'Km uyuşmuyor (Servis Defteri: {acik[0]["giris_km"]}, gelen: {km}).'
            else:
                try: yas=(datetime.now()-datetime.strptime((acik[0]['gelis_at'] or '')[:19],'%Y-%m-%d %H:%M:%S')).total_seconds()/86400
                except ValueError: yas=None
                if yas is None or yas>ENT_GUN_ARALIGI: neden=f'Açık iş emri çok eski ({"tarihsiz" if yas is None else int(yas)} gün; sınır {ENT_GUN_ARALIGI:g} gün).'
        if neden is None:
            ie=acik[0]['id']; _ent_isle(db,ie,v,t)
            db.execute('INSERT INTO entegrasyon_kayit(kayit_no,is_emri_id,arac_id,durum,olusturuldu_at,veri) VALUES(?,?,?,?,?,?)',(kayit_no,ie,a['id'],'eslesti',t,json.dumps(v,ensure_ascii=False)))
            db.commit(); log_olay(f'ENTEGRASYON [{g.dukkan["kullanici"]}] eşleşti: {kayit_no} · {plaka} -> iş emri #{ie}')
            return jsonify(ok=True,tekrar=False,eslesti=True,durum='eslesti',is_emri_id=ie,arac_id=a['id']),200
        if ENT_YENI_KAYIT and (not a or not acik):    # yalnızca "araç yok / açık iş emri yok" durumunda ve ayar açıksa
            ie,arac_id,yeni=_ent_yeni_kayit(db,v,t)
            db.execute('INSERT INTO entegrasyon_kayit(kayit_no,is_emri_id,arac_id,yeni_arac,durum,olusturuldu_at,veri) VALUES(?,?,?,?,?,?,?)',(kayit_no,ie,arac_id,int(yeni),'yeni_acildi',t,json.dumps(v,ensure_ascii=False)))
            db.commit(); log_olay(f'ENTEGRASYON [{g.dukkan["kullanici"]}] yeni iş emri açıldı: {kayit_no} · {plaka} #{ie}')
            return jsonify(ok=True,tekrar=False,eslesti=False,durum='yeni_acildi',is_emri_id=ie),201
        db.execute('INSERT INTO entegrasyon_kayit(kayit_no,durum,neden,olusturuldu_at,veri) VALUES(?,?,?,?,?)',(kayit_no,'beklemede',neden,t,json.dumps(v,ensure_ascii=False)))
        db.commit(); log_olay(f'ENTEGRASYON [{g.dukkan["kullanici"]}] incelemeye alındı: {kayit_no} · {plaka} · {neden}')
        return jsonify(ok=True,tekrar=False,eslesti=False,durum='beklemede',neden=neden),202
    except sqlite3.IntegrityError:
        db.rollback(); var=db.execute('SELECT is_emri_id,durum FROM entegrasyon_kayit WHERE kayit_no=?',(kayit_no,)).fetchone()
        if var: return jsonify(ok=True,tekrar=True,durum=var['durum'],is_emri_id=var['is_emri_id']),200
        return red('Eş zamanlı aynı kayıt işleniyor; birkaç saniye sonra aynı isteği tekrar gönderin.',409,'CONFLICT')
    except sqlite3.Error:
        db.rollback(); app.logger.exception('Entegrasyon DB hatası'); return red('Veritabanı hatası, tekrar dene.',500,'SERVER_ERROR')

# --- Dış sistem sayfası (Karar bekleyen + Reddedilen): usta/muhasebe görüp karar verir ---
def eslesmeyen_say():
    d=g.get('dukkan')
    if not d or d['id'] in BOZUK_DUKKAN: return 0       # bozuk dükkânın 503 sayfası çizilirken veritabanına dokunma
    try: return get_db().execute("SELECT COUNT(*) FROM entegrasyon_kayit WHERE durum='beklemede'").fetchone()[0]
    except sqlite3.Error: return 0
def ent_red_say():
    """Son 7 günde dış sistemden reddedilen istek sayısı (üst çubuktaki 'Dış sistem' düğmesinin görünmesi için)."""
    d=g.get('dukkan')
    if not d or d['id'] in BOZUK_DUKKAN: return 0
    try: return get_db().execute("SELECT COUNT(*) FROM entegrasyon_hata WHERE zaman>=?",((datetime.now()-timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'),)).fetchone()[0]
    except sqlite3.Error: return 0
def _ent_red_ozet(govde):
    """entegrasyon_hata.govde (telefon/adres/e-posta zaten '***' yapılmış JSON ya da form gövdesi) -> ekranda gösterilecek alanlar."""
    d={}
    try:
        j=json.loads(govde or '')
        if isinstance(j,dict): d=j
    except ValueError:
        try:
            from urllib.parse import parse_qsl
            s=(govde or '').strip()
            d=dict(parse_qsl(s,keep_blank_values=True)) if s and ' ' not in s else {}
        except ValueError: d={}
    def al(k):
        x=d.get(k)
        if isinstance(x,list): x=', '.join(str(i) for i in x)
        return re.sub(r'\s+',' ',str(x if x is not None else '')).strip()[:300]
    gizli=[ad for ad,anahtarlar in (('Telefon',('telefon','tel','phone')),('E-posta',('eposta','e-posta','email')),('Adres',('adres','address'))) if any(str(d.get(k) or '').strip() for k in anahtarlar)]
    return {'plaka':al('plaka'),'km':al('km'),'ad':al('musteri_ad'),'islem':al('yapilan_islem'),'not':al('not'),'durum':al('durum'),'gizli':gizli}
@app.context_processor
def ent_bagla():
    return {'eslesmeyen':eslesmeyen_say() if giris_var() else 0,'ent_red7':ent_red_say() if giris_var() else 0}
@app.route('/eslesmeyen-kayitlar')
@login_required
def eslesmeyen_kayitlar():
    db=get_db(); liste=[]
    for r in db.execute("SELECT * FROM entegrasyon_kayit WHERE durum='beklemede' ORDER BY olusturuldu_at DESC LIMIT 100").fetchall():
        v=json.loads(r['veri'] or '{}'); a=arac_bul(db,v.get('plaka','')) if v.get('plaka') else None
        adaylar=[dict(x) for x in _ent_acik_isemirleri(db,a['id'])] if a else []
        liste.append({'kayit_no':r['kayit_no'],'neden':r['neden'],'zaman':r['olusturuldu_at'],'v':v,'adaylar':adaylar,'plaka_goster':plaka_goster(v.get('plaka','')),'arac_var':bool(a)})
    red=[]
    for r in db.execute("SELECT zaman,kayit_no,hata,govde FROM entegrasyon_hata ORDER BY id DESC LIMIT 100").fetchall():
        o=_ent_red_ozet(r['govde']); o.update(zaman=r['zaman'],kayit_no=r['kayit_no'],hata=r['hata'],plaka_goster=plaka_goster(o['plaka']) if o['plaka'] else ''); red.append(o)
    sekme=request.args.get('sekme')
    if sekme not in ('bekleyen','red'): sekme='red' if (red and not liste) else 'bekleyen'      # bekleyen yoksa ve reddedilen varsa doğrudan reddedilenler açılır
    return render_template('eslesmeyen_kayitlar.html',liste=liste,red=red,sekme=sekme)
@app.route('/eslesmeyen-kayitlar/<path:kayit_no>/<eylem>',methods=['POST'])
@login_required
def eslesmeyen_islem(kayit_no,eylem):
    db=get_db(); r=db.execute("SELECT * FROM entegrasyon_kayit WHERE kayit_no=? AND durum='beklemede'",(kayit_no,)).fetchone()
    if not r: flash('Kayıt bulunamadı ya da zaten işlendi.','warning'); return redirect(url_for('eslesmeyen_kayitlar'))
    v=json.loads(r['veri'] or '{}'); t=now()
    try:
        if db.execute("UPDATE entegrasyon_kayit SET durum='isleniyor' WHERE kayit_no=? AND durum='beklemede'",(kayit_no,)).rowcount==0:   # çift tıklama: ikinci istek işlemi tekrarlamaz
            db.rollback(); flash('Kayıt bulunamadı ya da zaten işlendi.','warning'); return redirect(url_for('eslesmeyen_kayitlar'))
        if eylem=='bagla':
            ie=request.form.get('is_emri_id',type=int); x=db.execute('SELECT id,arac_id,durum FROM is_emirleri WHERE id=?',(ie,)).fetchone() if ie else None
            if not x or x['durum']=='Tamamlandı': flash('Geçerli ve açık bir iş emri seç.','danger'); db.rollback(); return redirect(url_for('eslesmeyen_kayitlar'))
            _ent_isle(db,x['id'],v,t); db.execute("UPDATE entegrasyon_kayit SET durum='eslesti',is_emri_id=?,arac_id=? WHERE kayit_no=?",(x['id'],x['arac_id'],kayit_no)); flash('İş emrine bağlandı.','success')
        elif eylem=='yeni':
            ie,arac_id,yeni=_ent_yeni_kayit(db,v,t); db.execute("UPDATE entegrasyon_kayit SET durum='yeni_acildi',is_emri_id=?,arac_id=?,yeni_arac=? WHERE kayit_no=?",(ie,arac_id,int(yeni),kayit_no)); flash('Yeni iş emri açıldı (etiket otomatik basılmadı; araç sayfasından basabilirsin).','success')
        elif eylem=='yoksay':
            db.execute("UPDATE entegrasyon_kayit SET durum='yoksayildi' WHERE kayit_no=?",(kayit_no,)); flash('Yoksayıldı.','info')
        else: abort(404)
        db.commit()
    except sqlite3.Error:
        db.rollback(); app.logger.exception('Dış sistem kaydı işlem hatası'); flash('Kaydedilemedi, tekrar dene.','danger')
    return redirect(url_for('eslesmeyen_kayitlar'))

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
        db.execute('DELETE FROM cop WHERE id=?',(cop_id,))
        if r['tablo']=='is_emirleri' and veri.get('arac_id'): arac_km_guncelle(db,veri['arac_id'])
        db.commit(); log_olay(f'GERİ GETİRİLDİ: {r["tablo"]} #{r["kayit_id"]}'); flash(f'Geri getirildi: {r["ozet"]}','success')
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
    gelen_gun={r['d']:r['n'] for r in db.execute("SELECT substr(gelis_at,1,10) d,COUNT(*) n FROM is_emirleri WHERE substr(gelis_at,1,10)>=? GROUP BY d",(bas_s,))}
    tamam_gun={r['d']:r['n'] for r in db.execute("SELECT substr(gidis_at,1,10) d,COUNT(*) n FROM is_emirleri WHERE durum='Tamamlandı' AND substr(gidis_at,1,10)>=? GROUP BY d",(bas_s,))}
    gunler=[]; d=simdi.date()
    while d>=bas.date():
        k=d.strftime('%Y-%m-%d'); gunler.append({'tarih':d.strftime('%d.%m'),'gun':GUN_AD[d.weekday()],'gelen':gelen_gun.get(k,0),'tamam':tamam_gun.get(k,0),'bugun':k==bugun}); d-=timedelta(days=1)
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

# --- VERİ GÜVENCESİ (dükkân başına): veritabanı boş açıldıysa ama yedek doluysa panelde kırmızı uyarı çıkar ---
_veri_uyari={}
def _say(yol,tablo='musteriler'):
    try:
        c=sqlite3.connect(f'file:{yol}?mode=ro',uri=True,timeout=5)
        try: return c.execute(f'SELECT COUNT(*) FROM {tablo}').fetchone()[0]
        finally: c.close()
    except sqlite3.Error: return -1
def veri_kontrol():
    for d in tum_dukkanlar():
        yol=db_yolu(d['id']); yd=yedek_dizin(d['id'])
        simdi=_say(yol); yedekler=sorted(f for f in os.listdir(yd) if f.startswith('servis_') and f.endswith('.db')) if os.path.isdir(yd) else []
        app.logger.info('Dükkân %s | müşteri=%s | iş emri=%s | yedek sayısı=%s',d['kullanici'],simdi,_say(yol,'is_emirleri'),len(yedekler))
        if simdi==0 and yedekler:
            eski=_say(os.path.join(yd,yedekler[-1]))
            if eski>0:
                _veri_uyari[d['id']]=f'Veritabanı BOŞ görünüyor ama son yedekte ({yedekler[-1]}) {eski} müşteri var. Yöneticiyle görüş: yedekten geri yüklenmesi gerekir.'
                app.logger.error('%s: %s',d['kullanici'],_veri_uyari[d['id']])
def yedek_bilgi():
    d=g.get('dukkan')
    if not d: return {'metin':'','kotu':False}
    yd=yedek_dizin(d['id'])
    try: t=[os.path.getmtime(os.path.join(yd,f)) for f in os.listdir(yd) if f.startswith('servis_') and f.endswith('.db')]
    except OSError: t=[]
    if not t:
        try: yeni_hesap=(datetime.now()-datetime.strptime(d.get('olusturuldu_at') or '','%Y-%m-%d %H:%M:%S')).total_seconds()<3*86400
        except ValueError: yeni_hesap=False
        if yeni_hesap: return {'metin':'İlk yedek bu gece alınır.','kotu':False}        # yeni dükkânda uyarı çıkmasın (yedeği sunucu alır)
        return {'metin':'Henüz hiç yedek alınmamış.','kotu':True}
    sn=max(0,time.time()-max(t)); sa=int(sn//3600)
    metin='az önce' if sn<3600 else f'{sa} saat önce' if sa<48 else f'{sa//24} gün önce'
    return {'metin':f'Son yedek: {metin}','kotu':sn>48*3600}
@app.context_processor
def yedek_bagla(): return {'yedek':yedek_bilgi()}
@app.context_processor
def veri_uyari_bagla():
    d=g.get('dukkan')
    if d and _veri_uyari.get(d['id']) and _say(db_yolu(d['id']))>0: _veri_uyari.pop(d['id'],None)     # veri geldi, uyarı kalksın
    return {'veri_uyari':_veri_uyari.get(d['id']) if d else None}
yonetim_init()
for _d in tum_dukkanlar():
    try: init_db(db_yolu(_d['id']),_d['kod'])
    except (sqlite3.Error,OSError) as _e:      # tek dükkânın bozuk dosyası diğerlerini durdurmasın
        BOZUK_DUKKAN[_d['id']]=str(_e); app.logger.error('Dükkân %s veritabanı AÇILAMADI, diğerleri çalışmaya devam ediyor: %r',_d['kullanici'],_e)
izinleri_sikilastir()
veri_kontrol()
if __name__=='__main__':
    # Elle başlatmada varsayılan yalnızca bu bilgisayar (127.0.0.1); yerel ağ için .env: DINLE_ADRES=0.0.0.0
    app.run(host=os.environ.get('DINLE_ADRES','127.0.0.1').strip() or '127.0.0.1',port=int(os.environ.get('PORT','5000') or 5000),debug=False)
