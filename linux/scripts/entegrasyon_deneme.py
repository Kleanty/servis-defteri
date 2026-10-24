#!/usr/bin/env python3
"""Dis sistem API'si (POST /api/v1/is-emirleri) DEMO TEST ARACI - ek paket gerekmez.

Ne yapar?  Veritabanina "[DEMO]" etiketli demo musteri/arac/is emri ekler, API'yi gercekten cagirir, sonucu hem API
cevabindan hem de veritabanindan dogrular. Her adimda: ne gonderildi, ne bekleniyordu, ne geldi, KALDIYSA olasi neden.
Demo kayitlar HEMEN SILINMEZ: uygulamada (Is Emirleri listesi, ust menu "Eslesmeyen") bakip inceleyebilirsin.
Gercek kayitlara dokunulmaz (yalniz "[DEMO]" musteriler ve "DEMO-" kayit numaralari).

  python scripts/entegrasyon_deneme.py                         -> yerel sunucu (http://127.0.0.1:5000)
  python scripts/entegrasyon_deneme.py --url https://alanadiniz.com   -> internet/tunel uzerinden (ayni bilgisayarda)
  python scripts/entegrasyon_deneme.py --temizle               -> demo kayitlari siler
  python scripts/entegrasyon_deneme.py --sessiz                -> sadece KALDI olanlari ve ozeti yazar
Cikis kodu: 0 = hepsi gecti, 1 = en az biri kaldi."""
import argparse, json, os, sqlite3, sys, uuid, urllib.request, urllib.error
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortam import KOK, env_yukle, utf8_cikti

DB = os.path.join(KOK, 'data', 'servis.db')
SIMDI = lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S')
IPUCU = {
    0: 'Sunucuya ULASILAMADI. Uygulama calisiyor mu? uygulamayi yeniden baslat (Windows: windows\\YENIDEN-BASLAT.bat, Linux: sudo systemctl restart servis-defteri); internet adresi icinse Cloudflare tuneli ve adres dogru mu?',
    403: 'Yaniti uygulama degil, ARADAKI Cloudflare/guvenlik duvari verdi (govde bos/JSON degil). Cloudflare panelinde Security > Events bolumune bak; /api/v1/* icin Bot Fight Mode / WAF kurali atlatma (Skip) kurali ekle.',
    404: 'API KAPALI. .env icinde ENTEGRASYON_API_ANAHTARI satiri yok ya da uygulama yeniden baslatilmadi (uygulamayi yeniden baslat).',
    401: 'Anahtar yanlis. Bu arac .env dosyasindaki ENTEGRASYON_API_ANAHTARI ile dener; uygulamayi anahtari ekledikten sonra yeniden baslattin mi?',
    400: 'Istek reddedildi. HTTPS_REQUIRED ise internetten https:// ile dene; baska ise gonderilen JSON bozuk olabilir.',
    422: 'Alan hatasi: cevaptaki "hata" metni hangi alanin gecersiz oldugunu soyler.',
    429: 'Cok fazla yanlis anahtar denemesi: 5 dakika bekle (Retry-After).',
    500: 'Sunucu hatasi: data\\uygulama.log dosyasinin son satirlarina bak (Traceback var mi?).',
}


def istek(url, yontem='GET', govde=None, anahtar=None, ek=None):
    b = {'Content-Type': 'application/json', 'User-Agent': 'ServisDefteri-API-Deneme/1.0', 'Accept': 'application/json'}
    if anahtar: b['Authorization'] = 'Bearer ' + anahtar
    b.update(ek or {})
    r = urllib.request.Request(url, data=json.dumps(govde).encode() if govde is not None else None, headers=b, method=yontem)
    try:
        with urllib.request.urlopen(r, timeout=20) as p: return p.status, json.loads(p.read().decode() or '{}')
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode() or '{}')
        except ValueError: return e.code, {'govde_ozet': 'JSON degil (uygulama degil, aradaki Cloudflare/guvenlik duvari yanit vermis olabilir)'}
    except (urllib.error.URLError, OSError) as e: return 0, {'hata': str(e)}


class Demo:
    """Veritabanina [DEMO] kayit ekler/siler (uygulamayla ayni anda calisabilir: SQLite WAL)."""
    def __init__(self): self.c = sqlite3.connect(DB, timeout=15); self.c.row_factory = sqlite3.Row
    def temizle(self):
        c = self.c; m = [r[0] for r in c.execute("SELECT id FROM musteriler WHERE ad_soyad LIKE '[DEMO]%'")]
        for mid in m:
            for a in [r[0] for r in c.execute('SELECT id FROM araclar WHERE musteri_id=?', (mid,))]:
                c.execute('DELETE FROM is_emirleri WHERE arac_id=?', (a,)); c.execute('DELETE FROM araclar WHERE id=?', (a,))
            c.execute('DELETE FROM musteriler WHERE id=?', (mid,))
        c.execute("DELETE FROM entegrasyon_kayit WHERE kayit_no LIKE 'DEMO-%'"); c.execute("DELETE FROM entegrasyon_hata WHERE kayit_no LIKE 'DEMO-%'")
        c.commit(); return len(m)
    def plaka_dolu(self, p): return self.c.execute('SELECT 1 FROM araclar a JOIN musteriler m ON m.id=a.musteri_id WHERE a.plaka=? AND m.ad_soyad NOT LIKE ?', (p, '[DEMO]%')).fetchone()
    def arac(self, plaka, ad, km=100000, marka='DemoMarka', model='DemoModel'):
        t = SIMDI(); mid = self.c.execute('INSERT INTO musteriler(ad_soyad,olusturuldu_at,guncellendi_at) VALUES(?,?,?)', ('[DEMO] ' + ad, t, t)).lastrowid
        aid = self.c.execute('INSERT INTO araclar(musteri_id,plaka,marka,model,kilometre,lpg_durumu,qr_token,olusturuldu_at,guncellendi_at) VALUES(?,?,?,?,?,0,?,?,?)', (mid, plaka, marka, model, km, uuid.uuid4().hex, t, t)).lastrowid
        self.c.commit(); return aid
    def is_emri(self, aid, nedeni='Yag degisimi', yapilan='', km=100000, gun_once=0, durum='Devam Ediyor'):
        g = (datetime.now() - timedelta(days=gun_once)).strftime('%Y-%m-%d %H:%M:%S'); t = SIMDI()
        i = self.c.execute('INSERT INTO is_emirleri(arac_id,tarih,gelis_nedeni,yapilan_islem,durum,notlar,gelis_at,giris_km,olusturuldu_at,guncellendi_at,kaynak,gidis_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                              (aid, g[:10], nedeni, yapilan, durum, '', g, km, t, t, 'demo', t if durum == 'Tamamlandı' else None)).lastrowid
        self.c.commit(); return i
    def satir(self, sql, *a): return self.c.execute(sql, a).fetchone()
    def say(self, sql, *a): return self.c.execute(sql, a).fetchone()[0]


def ozet(sonuc, hafif=False):
    ok = sum(1 for _, o in sonuc if o); print('\n' + '=' * 64)
    print('SONUC: %d/%d GECTI' % (ok, len(sonuc)))
    for b, o in sonuc:
        if not o: print('  KALDI -> ' + b)
    if not hafif:
        print('\nDEMO KAYITLAR uygulamada duruyor (silinmedi). Incelemek icin:')
        print('  * Is Emirleri listesi: "[DEMO]" musteriler, 01 DMO 010..017 plakalari')
        print('  * Ust menude "Eslesmeyen" rozeti: beklemede kalan 5 demo kayit (kayitsiz, tamamlanmis, iki acik, km, eski)')
        print('  * Ana senaryo (01 DMO 010): is emri Tamamlandi, "Yapilan islem" = Motor yagi degisimi, Yag filtresi')
        print('Isin bitince silmek icin:  python scripts\\entegrasyon_deneme.py --temizle')
    return 0 if ok == len(sonuc) else 1


def main():
    utf8_cikti(); env_yukle()
    ap = argparse.ArgumentParser(); ap.add_argument('--url', default='http://127.0.0.1:%s' % (os.environ.get('PORT') or '5000'))
    ap.add_argument('--internet', action='store_true', help='adres olarak .env icindeki PUBLIC_BASE_URL kullanilir'); ap.add_argument('--temizle', action='store_true'); ap.add_argument('--sessiz', action='store_true'); ap.add_argument('--hafif', action='store_true', help='yalniz baglanti/guvenlik kontrolleri; demo kayit EKLEMEZ/SILMEZ'); a = ap.parse_args()
    if a.internet:
        a.url = os.environ.get('PUBLIC_BASE_URL', '').strip()
        if not a.url: print('HATA: .env icinde PUBLIC_BASE_URL yok (domain baglandiktan sonra yazilir).'); return 1
    if not os.path.exists(DB): print('HATA: veritabani bulunamadi:', DB, '(bu arac uygulamanin kurulu oldugu bilgisayarda calismali)'); return 1
    demo = Demo()
    if a.temizle: print('Silinen demo musteri sayisi:', demo.temizle()); return 0
    anahtar = os.environ.get('ENTEGRASYON_API_ANAHTARI', '').strip(); taban = a.url.rstrip('/') + '/api/v1'; US = taban + '/is-emirleri'
    if not anahtar: print('HATA: .env icinde ENTEGRASYON_API_ANAHTARI yok. Kurulumu/guncellemeyi kontrol et.'); return 1
    onceki = 0 if a.hafif else demo.temizle()
    if onceki and not a.sessiz: print('(Onceki demo calismasindan %d demo musteri temizlendi.)' % onceki)
    sonuc = []; no = [0]; RUN = uuid.uuid4().hex[:6]
    def kno(): no[0] += 1; return 'DEMO-%s-%02d' % (RUN, no[0])
    def adim(baslik, gonderilen, beklenen_kod, beklenen_aciklama, kod, cevap, dogrulamalar=()):
        """dogrulamalar: [(aciklama, kosul, ipucu)] -> hepsi gecerse GECTI."""
        hatalar = []
        if kod != beklenen_kod: hatalar.append('HTTP %s bekleniyordu, %s geldi.%s' % (beklenen_kod, kod, ('  Ipucu: ' + IPUCU[kod]) if kod in IPUCU else ''))
        for acik, kosul, ipucu in dogrulamalar:
            if not kosul: hatalar.append('Veritabani/cevap dogrulamasi tutmadi: %s.  Ipucu: %s' % (acik, ipucu))
        ok = not hatalar; sonuc.append((baslik, ok))
        if a.sessiz and ok: return
        print('\n[%s] %s' % ('GECTI' if ok else 'KALDI', baslik))
        print('   Gonderilen : %s' % (json.dumps(gonderilen, ensure_ascii=False) if gonderilen is not None else '-'))
        print('   Beklenen   : HTTP %s - %s' % (beklenen_kod, beklenen_aciklama))
        print('   Gelen      : HTTP %s %s' % (kod, json.dumps(cevap, ensure_ascii=False)))
        for h in hatalar: print('   !! ' + h)
    def gonder(g, anah=anahtar, ek=None): return istek(US, 'POST', g, anah, ek)
    P = lambda n: '01 DMO %03d' % n          # Adana 01 + DMO harfleri: gercek plaka cakisma ihtimali cok dusuk
    for n in ([] if a.hafif else range(1, 20)):
        if demo.plaka_dolu(P(n).replace(' ', '')): print('HATA: %s plakasi gercek bir kayitta var; demo calismasi durduruldu (hicbir sey eklenmedi).' % P(n)); return 1
    print('Adres:', US, '| Anahtar: .env\'den okundu (gizli)')
    # ---- Altyapi
    kod, j = istek(taban + '/saglik'); adim('Saglik kontrolu', None, 200, 'ok:true', kod, j)
    if kod in (0, 403, 404): print('\nTemel baglanti kurulamadi; devam edilmiyor.\n  Ipucu: ' + IPUCU[kod]); return 1
    g = {'kayit_no': kno(), 'plaka': P(1), 'km': 1}; kod, j = gonder(g, anah=''); adim('Anahtarsiz istek reddedilir', g, 401, 'kod=INVALID_API_KEY', kod, j)
    g = {'kayit_no': kno(), 'plaka': P(1), 'km': 1}; kod, j = gonder(g, anah='yanlis-anahtar'); adim('Yanlis anahtar reddedilir', g, 401, 'kod=INVALID_API_KEY', kod, j)
    g = {'kayit_no': kno(), 'km': 5}; kod, j = gonder(g); adim('Plakasiz istek reddedilir', g, 422, 'kod=VALIDATION_ERROR', kod, j)
    if kod in (401, 429):
        print('\nDOGRU anahtarla bile kabul edilmedi (HTTP %s); diger adimlar anlamsiz oldugu icin durduruldu.\n  Ipucu: %s' % (kod, IPUCU[kod])); return ozet(sonuc, hafif=True)
    g = {'kayit_no': kno(), 'plaka': 'ABC'}; kod, j = gonder(g); adim('Gecersiz plaka reddedilir', g, 422, 'plaka bicimi hatasi', kod, j)
    g = {'kayit_no': kno(), 'plaka': P(1), 'durum': 'Bitti'}; kod, j = gonder(g); adim('Gecersiz durum reddedilir', g, 422, 'durum degerleri: Beklemede/Devam Ediyor/Tamamlandi', kod, j)
    if not a.hafif:     # internet testinde Cloudflare CF-Visitor basligini kendisi yazar, sahte http taklit edilemez (yerel testte denenir)
        g = {'kayit_no': kno(), 'plaka': P(1)}; kod, j = gonder(g, ek={'CF-Visitor': '{"scheme":"http"}'}); adim('Duz http (Cloudflare basligi) reddedilir', g, 400, 'kod=HTTPS_REQUIRED', kod, j)
    if a.hafif: return ozet(sonuc, hafif=True)
    # ---- 1) Ana senaryo: usta acar, muhasebe kaydi gelir, iş emrine bağlanır (işlem + durum)
    aid = demo.arac(P(10), 'Ana Senaryo Musteri'); ie = demo.is_emri(aid, nedeni='Yag degisimi', km=100000); n0 = demo.say('SELECT COUNT(*) FROM is_emirleri')
    g = {'kayit_no': kno(), 'plaka': P(10), 'km': 100015, 'yapilan_islem': ['Motor yagi degisimi', 'Yag filtresi'], 'durum': 'Tamamlandı', 'musteri_ad': 'demo ahmet', 'telefon': '0532 000 00 01', 'eposta': 'demo@example.com', 'adres': 'Demo Mah. 1', 'not': 'Demo muhasebe notu'}
    kod, j = gonder(g); r = demo.satir('SELECT * FROM is_emirleri WHERE id=?', ie); m = demo.satir('SELECT m.* FROM musteriler m JOIN araclar a ON a.musteri_id=m.id WHERE a.id=?', aid)
    adim('ANA SENARYO: ustanin acik is emrine baglanir', g, 200, 'eslesti=true, is_emri_id=%s' % ie, kod, j, [
        ('yeni is emri ACILMAMALI', demo.say('SELECT COUNT(*) FROM is_emirleri') == n0, 'Eslesme yerine yeni kayit acilmis; api eslestirme mantigini (acik is emri) kontrol et'),
        ('yapilan_islem = muhasebe metni', r['yapilan_islem'] == 'Motor yagi degisimi, Yag filtresi', 'islem alani gelen listeyle yer degistirmeli; DB: %r' % r['yapilan_islem']),
        ('ustanin "Ne yapilacak?" (gelis_nedeni) degismemeli', r['gelis_nedeni'] == 'Yag degisimi', 'API gelis_nedeni alanina dokunmamali; DB: %r' % r['gelis_nedeni']),
        ('durum Tamamlandi + gidis zamani yazilmali', r['durum'] == 'Tamamlandı' and bool(r['gidis_at']), 'durum/gidis_at guncellenmemis; DB: %r / %r' % (r['durum'], r['gidis_at'])),
        ('not eklenmeli', 'Demo muhasebe notu' in (r['notlar'] or ''), 'notlar alani bos kalmis'),
        ('musteri bos alanlari dolmali (telefon, e-posta, adres)', m['telefon'] == '05320000001' and m['eposta'] == 'demo@example.com' and m['adres'] == 'Demo Mah. 1', 'musteri alanlari: %r' % dict(m)),
        ('arac km guncellenmeli', demo.say('SELECT kilometre FROM araclar WHERE id=?', aid) == 100000, 'ustanin giris km (100000) korunur; arac km = son is emrinin giris km')])
    kod, j2 = gonder(g); adim('Ayni kayit_no ayni icerikle tekrar: yinelenmez', g, 200, 'tekrar=true, degisiklik yok', kod, j2, [('tekrar=true', j2.get('tekrar') is True, 'idempotency calismiyor')])
    g2 = dict(g, yapilan_islem='BASKA ISLEM'); kod, j3 = gonder(g2); adim('Ayni kayit_no FARKLI icerik: cakisma, kayit degismez', g2, 409, 'kod=IDEMPOTENCY_CONFLICT', kod, j3, [
        ('yapilan_islem degismemeli', demo.satir('SELECT yapilan_islem FROM is_emirleri WHERE id=?', ie)[0] == 'Motor yagi degisimi, Yag filtresi', 'cakisan istek kaydi bozmus')])
    # ---- 2) Muhasebe son karar: usta yapilan islem yazmis, ezilir; eskisi nota
    aid = demo.arac(P(11), 'Ezme Senaryo Musteri'); ie = demo.is_emri(aid, nedeni='Fren', yapilan='Ustanin yazdigi islem', km=50000)
    g = {'kayit_no': kno(), 'plaka': P(11), 'km': 50000, 'yapilan_islem': 'Muhasebedeki islem'}; kod, j = gonder(g); r = demo.satir('SELECT * FROM is_emirleri WHERE id=?', ie)
    adim('MUHASEBE SON KARAR: eski islem ezilir, eskisi nota yazilir', g, 200, 'yapilan_islem yenisiyle degisir; notlarda "Onceki islem: ..."', kod, j, [
        ('yapilan_islem yeni metin', r['yapilan_islem'] == 'Muhasebedeki islem', 'DB: %r' % r['yapilan_islem']),
        ('eski metin notta saklandi', 'Önceki işlem: Ustanin yazdigi islem' in (r['notlar'] or ''), 'notlar: %r' % r['notlar'])])
    # ---- 3) Sadece plaka + km: islem uydurulmaz
    aid = demo.arac(P(12), 'Sadece Plaka Km'); ie = demo.is_emri(aid, nedeni='Aku', yapilan='', km=70000)
    g = {'kayit_no': kno(), 'plaka': P(12), 'km': 70005}; kod, j = gonder(g); r = demo.satir('SELECT * FROM is_emirleri WHERE id=?', ie)
    adim('Sadece plaka+km: eslesir, islem uydurulmaz', g, 200, 'eslesti=true; islem/durum degismez', kod, j, [
        ('yapilan_islem bos kalmali', (r['yapilan_islem'] or '') == '', 'DB: %r' % r['yapilan_islem']), ('durum degismemeli', r['durum'] == 'Devam Ediyor', 'DB: %r' % r['durum'])])
    # ---- 4) Belirsiz durumlar -> 202 inceleme kuyrugu, YENI KAYIT ACILMAZ
    n0 = demo.say('SELECT COUNT(*) FROM is_emirleri'); a0 = demo.say('SELECT COUNT(*) FROM araclar')
    g = {'kayit_no': kno(), 'plaka': P(13), 'km': 1000}; kod, j = gonder(g)
    adim('Kayitsiz plaka: incelemeye alinir, arac/is emri acilmaz', g, 202, 'durum=beklemede', kod, j, [
        ('yeni arac/is emri YOK', demo.say('SELECT COUNT(*) FROM is_emirleri') == n0 and demo.say('SELECT COUNT(*) FROM araclar') == a0, 'ENTEGRASYON_YENI_KAYIT=1 acik olabilir (.env)'),
        ('kayit kalici saklandi', demo.say("SELECT COUNT(*) FROM entegrasyon_kayit WHERE kayit_no=? AND durum='beklemede'", g['kayit_no']) == 1, 'entegrasyon_kayit tablosuna yazilmamis')])
    aid = demo.arac(P(14), 'Tamamlanmis Is Emri'); demo.is_emri(aid, km=10, durum='Tamamlandı')
    g = {'kayit_no': kno(), 'plaka': P(14), 'km': 10}; kod, j = gonder(g); adim('Acik is emri yok (hepsi tamamlanmis): incelemeye alinir', g, 202, 'neden: acik is emri yok', kod, j)
    aid = demo.arac(P(15), 'Iki Acik Is Emri'); demo.is_emri(aid, km=100); demo.is_emri(aid, km=105)
    g = {'kayit_no': kno(), 'plaka': P(15), 'km': 102}; kod, j = gonder(g); adim('Iki acik is emri: rastgele secilmez, incelemeye alinir', g, 202, 'neden: 2 acik is emri', kod, j)
    aid = demo.arac(P(16), 'Km Uyusmuyor'); demo.is_emri(aid, km=80000)
    g = {'kayit_no': kno(), 'plaka': P(16), 'km': 95000}; kod, j = gonder(g); adim('Km cok farkli: incelemeye alinir', g, 202, 'neden: km uyusmuyor', kod, j)
    aid = demo.arac(P(17), 'Eski Is Emri'); demo.is_emri(aid, km=900, gun_once=30)
    g = {'kayit_no': kno(), 'plaka': P(17), 'km': 900}; kod, j = gonder(g); adim('30 gun onceki acik is emri: otomatik baglanmaz', g, 202, 'neden: cok eski', kod, j)
    return ozet(sonuc)


if __name__ == '__main__': sys.exit(main())
