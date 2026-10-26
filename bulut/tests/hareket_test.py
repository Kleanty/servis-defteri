# Cihaz adı kapısı ve hareket kaydı (çok dükkânlı): kapı, aynı ad serbest, kişi bilgisi yok, 180 gün, dükkânlar arası yalıtım.
import os, re, sys, shutil, tempfile, sqlite3
from datetime import datetime, timedelta
os.environ.pop('APP_PASSWORD_HASH', None); os.environ['FORCE_HTTPS_COOKIE'] = '0'
d = tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), d + '/a', ignore=shutil.ignore_patterns('data', '__pycache__')); os.chdir(d + '/a'); sys.path.insert(0, '.')
import app as A          # CIHAZ_KAPISI burada AÇIK (varsayılan)
ok = fail = 0
def k(ad, c):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print('BAŞARISIZ:', ad)
R = {'REMOTE_ADDR': '127.0.0.1'}
def tok(c, y='/login'):
    m = re.search(r'name="csrf_token" value="([^"]+)"', c.get(y, environ_overrides=R, follow_redirects=True).get_data(as_text=True)); return m.group(1) if m else ''
def post(c, url, y='/login', **v): v['csrf_token'] = tok(c, y); return c.post(url, data=v, environ_overrides=R)
def get(c, url): return c.get(url, environ_overrides=R)
ia, _ = A.dukkan_olustur('ahmet-oto', 'Ahmet Oto', '0555 111 22 33', sifre='Ahmet-Sifre-1', gecici=False)
ib, _ = A.dukkan_olustur('veli-servis', 'Veli Servis', '0555 222 33 44', sifre='Veli-Sifre-12', gecici=False)
def giris(kul, sif):
    c = A.app.test_client(); post(c, '/login', kullanici=kul, sifre=sif); return c
def dbx(i): return sqlite3.connect(A.db_yolu(i))
def ad_ver(c, ad, **ek): return post(c, '/cihaz-adi', '/cihaz-adi', ad=ad, **ek)

a = giris('ahmet-oto', 'Ahmet-Sifre-1'); b = giris('veli-servis', 'Veli-Sifre-12')
r = get(a, '/panel'); k('adsız cihaz /panel yerine ad sayfasına yönlenir', r.status_code == 302 and '/cihaz-adi' in r.headers['Location'])
ad_ver(a, 'x'); k('1 karakterlik ad reddedilir', get(a, '/panel').status_code == 302 and dbx(ia).execute('select count(*) from cihazlar').fetchone()[0] == 0)
r = post(a, '/is-emirleri/hizli', '/cihaz-adi', plaka='34TST111', giris_km='1000', gelis_nedeni='Bakım')
k('adsız cihaz iş emri açamaz', dbx(ia).execute('select count(*) from is_emirleri').fetchone()[0] == 0)
r = ad_ver(a, 'Usta telefonu', geri='//kotu.example/x'); sc = [x for x in r.headers.getlist('Set-Cookie') if x.startswith('cihaz=')]
k('ad verilince kayıt oluşur, güvensiz geri adresi yok sayılır', r.status_code == 302 and 'kotu.example' not in r.headers['Location'] and dbx(ia).execute("select count(*) from cihazlar where ad='Usta telefonu'").fetchone()[0] == 1)
k('cihaz kartı 400 gün, HttpOnly, SameSite', bool(sc) and f'Max-Age={400*86400}' in sc[0] and 'HttpOnly' in sc[0] and 'SameSite=Lax' in sc[0])
k('ad verince panel açılır', get(a, '/panel').status_code == 200)

# --- dükkânlar arası yalıtım ---
k('B dükkânının cihazı A\'nın adını almaz (B hâlâ adsız)', get(b, '/panel').status_code == 302)
kart = a.get_cookie('cihaz').value
b2 = giris('veli-servis', 'Veli-Sifre-12'); b2.set_cookie('cihaz', kart)
k('A dükkânının cihaz kartı B dükkânında geçersiz', get(b2, '/panel').status_code == 302)
ad_ver(b, 'Usta telefonu')
k('aynı ad farklı dükkânda serbest, her dükkân kendi veritabanında', dbx(ib).execute("select count(*) from cihazlar").fetchone()[0] == 1 and dbx(ia).execute("select count(*) from cihazlar").fetchone()[0] == 1)

# --- aynı dükkânda aynı ad ikinci cihaza ---
a2 = giris('ahmet-oto', 'Ahmet-Sifre-1'); ad_ver(a2, 'Usta telefonu')
k('aynı ad ikinci cihaza verilebilir (kodlar farklı)', dbx(ia).execute("select count(*),count(distinct kod) from cihazlar where ad='Usta telefonu'").fetchone() == (2, 2))

# --- hareketler ---
post(a, '/is-emirleri/hizli', '/panel', plaka='34TST111', giris_km='1000', gelis_nedeni='Bakım', musteri_ad='Gizli Kisi', telefon='0555 777 66 55')
post(a, '/musteriler/ekle', '/panel', ad_soyad='Ali Veli', telefon='0555 999 88 77')
cid = dbx(ia).execute("select id,kod from cihazlar where ad='Usta telefonu' order by id").fetchone()
satir = dbx(ia).execute('select cihaz,olay from hareketler').fetchall(); olaylar = ' | '.join(x[1] for x in satir)
k('iş emri kaydı cihaz adı + kodla', any(x[1].startswith('İş emri açıldı: 34 TST 111') and x[0] == f'Usta telefonu · #{cid[1]}' for x in satir))
k('müşteri ekleme kaydı', any(x[1] == 'Müşteri eklendi' for x in satir))
k('hareket kaydında telefon ve müşteri adı YOK', all(z not in olaylar for z in ('0555', 'Gizli', 'Ali Veli')))
h = get(a, '/hareketler'); t = h.get_data(as_text=True)
k('hareketler sayfası açılır', h.status_code == 200 and 'Usta telefonu' in t and 'İş emri açıldı' in t)
k('B dükkânı A\'nın hareketlerini göremez', '34 TST 111' not in get(b, '/hareketler').get_data(as_text=True) and dbx(ib).execute("select count(*) from hareketler where olay like 'İş emri%'").fetchone()[0] == 0)
k('İstatistikte Hareketler düğmesi', '/hareketler' in get(a, '/istatistik').get_data(as_text=True))
k('girişsiz /hareketler giriş ister', A.app.test_client().get('/hareketler', environ_overrides=R).status_code == 302)

# --- yeniden adlandırma ---
r = post(a, f'/hareketler/cihaz/{cid[0]}', '/hareketler', ad='Ofis'); t = get(a, '/hareketler').get_data(as_text=True)
k('yeniden adlandırma eski kayıtlara da yansır', r.status_code == 302 and f'Ofis · #{cid[1]}' in t)
post(a, f'/hareketler/cihaz/{cid[0]}', '/hareketler', ad='a'); k('geçersiz yeni ad reddedilir', dbx(ia).execute('select ad from cihazlar where id=?', (cid[0],)).fetchone()[0] == 'Ofis')

# --- 180 gün ---
eski = (datetime.now() - timedelta(days=181)).strftime('%Y-%m-%d %H:%M:%S'); yeni = (datetime.now() - timedelta(days=179)).strftime('%Y-%m-%d %H:%M:%S')
con = dbx(ia); con.execute("insert into hareketler(zaman,cihaz,ip,olay) values(?,?,?,?)", (eski, 'x', '1.1.1.1', 'ESKI-181')); con.execute("insert into hareketler(zaman,cihaz,ip,olay) values(?,?,?,?)", (yeni, 'x', '1.1.1.1', 'YENI-179')); con.commit(); con.close()
A._hareket_temizlendi.clear(); post(a, '/musteriler/ekle', '/panel', ad_soyad='Temizlik Tetik')
k('181 günlük kayıt silinir, 179 günlük kalır', dbx(ia).execute("select count(*) from hareketler where olay='ESKI-181'").fetchone()[0] == 0 and dbx(ia).execute("select count(*) from hareketler where olay='YENI-179'").fetchone()[0] == 1)
# --- sağlamlaştırma ---
k('?s= çok büyük sayı 500 vermez', get(a, '/hareketler?s=99999999999999999999').status_code == 200)
con = dbx(ia); con.execute("update cihazlar set kod='ZZZZ' where id=?", (cid[0],)); con.commit(); con.close()
k('cihaz kodu değişince eski kart geçersiz', get(a, '/panel').status_code == 302)
con = dbx(ia); con.execute("update cihazlar set kod=? where id=?", (cid[1], cid[0])); con.commit(); con.close()
eski2 = (datetime.now() - timedelta(days=200)).strftime('%Y-%m-%d %H:%M:%S')
con = dbx(ia); con.execute("insert into cihazlar(ad,kod,olusturuldu_at,son_gorulme_at) values('Eski','ABCD',?,?)", (eski2, eski2)); con.commit(); con.close()
A._hareket_temizlendi.clear(); post(a, '/musteriler/ekle', '/panel', ad_soyad='Temizlik 2')
k('eski ve kayıtsız cihaz silinir', dbx(ia).execute("select count(*) from cihazlar where ad='Eski'").fetchone()[0] == 0 and dbx(ia).execute('select count(*) from cihazlar where id=?', (cid[0],)).fetchone()[0] == 1)
out = giris('ahmet-oto', 'Ahmet-Sifre-1'); ad_ver(out, 'Geçici'); a3 = out
r = post(a3, '/cikis-hepsi', '/panel'); k('cikis-hepsi isteği başarılı', r.status_code in (302, 200))
k('"tüm cihazlardan çıkış" olayı cihaz adıyla kayıtlı', dbx(ia).execute("select count(*) from hareketler where olay='TÜM CİHAZLARDAN ÇIKIŞ' and cihaz like 'Geçici%'").fetchone()[0] == 1)
k('düşmüş oturumdan çıkış hata vermez', post(a, '/logout', '/panel').status_code in (302, 200))
print(f'{ok} geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
