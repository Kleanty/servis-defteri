#!/usr/bin/env python3
"""Servis Defteri yazdırma ajanı: dükkân bilgisayarındaki USB etiket yazıcısını bulut sunucusuna bağlar.

Nasıl çalışır: ajan sunucuya DIŞARI doğru (HTTPS) bağlanır ve birkaç saniyede bir "basılacak etiket var mı?" diye sorar.
Etiket varsa ham TSPL baytlarını (sunucu üretir) yazıcıya gönderir ve sonucu bildirir. Modemden port açmak gerekmez.

Ayar dosyası (ajan.env, bu dosyanın yanında; KUR sihirbazı yazar):
    SUNUCU=https://servis.ornek.com      # buluttaki Servis Defteri adresi
    ANAHTAR=ya_xxxx_...                  # yöneticinin ürettiği ajan anahtarı
    ETIKET_YAZICI_ADI=XP-470             # (isteğe bağlı) Windows yazıcı adının bir parçası; ETIKET_* ayarları da buraya yazılabilir

Kullanım:
    python yazdirma_ajani.py              # çalışır (sürekli)
    python yazdirma_ajani.py --baglanti   # adres + anahtar doğru mu (kuyruğa dokunmaz)
    python yazdirma_ajani.py --durum      # yazıcı bulunuyor mu
    python yazdirma_ajani.py --deneme     # yazıcıdan deneme etiketi çıkarır
"""
import base64, http.client, json, logging, logging.handlers, os, sys, time, urllib.error, urllib.parse, urllib.request

KLASOR = os.path.dirname(os.path.abspath(__file__))
SORGU_SN = 3.0            # kuyruk sorgu aralığı (iş yoksa)
BEKLEME_ENFAZLA_SN = 60.0 # bağlantı koparsa en çok bu kadar aralıkla yeniden dener
ZAMAN_ASIMI_SN = 15
log = logging.getLogger('ajan')


def ayar_oku(yol=None):
    """ajan.env -> dict. KEY=VALUE satırları; # yorum. ETIKET_* gibi diğer anahtarlar ortam değişkeni olur (ortamda zaten varsa ezilmez)."""
    yol = yol or os.environ.get('AJAN_AYAR') or os.path.join(KLASOR, 'ajan.env'); a = {}
    try:
        with open(yol, encoding='utf-8-sig') as f:
            for satir in f:
                satir = satir.strip()
                if not satir or satir.startswith('#') or '=' not in satir: continue
                k, v = satir.split('=', 1); k = k.strip(); v = v.split(' #')[0].strip().strip('"').strip("'")
                if k: a[k] = v
    except FileNotFoundError:
        pass
    except PermissionError:
        print('ajan.env okunamadi (izin yok). Bu komutu YONETICI olarak calistir: dosya yalnizca Yonetici/SYSTEM erisimine kisitli.'); sys.exit(3)
    for k, v in a.items():
        if k not in ('SUNUCU', 'ANAHTAR') and k not in os.environ: os.environ[k] = v
    return a


def adres_kontrol(sunucu):
    """https zorunlu (yalnızca yerel deneme için http://localhost / 127.0.0.1 serbest). Temiz adres ya da ValueError."""
    s = (sunucu or '').strip().rstrip('/')
    try: u = urllib.parse.urlsplit(s); host = (u.hostname or '').lower()
    except ValueError: raise ValueError('SUNUCU adresi geçersiz.')
    yerel = u.scheme == 'http' and host in ('localhost', '127.0.0.1')      # tam konak eşlemesi: localhost.ornek.com gibi adresler yerel sayılmaz
    if not (u.scheme == 'https' or yerel): raise ValueError('SUNUCU adresi https:// ile başlamalı (örn. https://servis.ornek.com).')
    if not host or '.' not in host and not yerel or ' ' in s or u.username or u.password or u.query or u.fragment: raise ValueError('SUNUCU adresi geçersiz.')
    return s


class AnahtarHatasi(Exception):
    """Sunucu ajan anahtarını reddetti (yerel ağ/izin hatalarından ayrı tutulur)."""


class _YonlendirmeYok(urllib.request.HTTPRedirectHandler):
    """Yönlendirme izlenmez: ajan anahtarı başka bir konağa/düz http'ye taşınmasın."""
    def redirect_request(self, *a, **k): return None


class Istemci:
    def __init__(self, sunucu, anahtar):
        self.sunucu = adres_kontrol(sunucu); self.anahtar = (anahtar or '').strip()
        if not self.anahtar: raise ValueError('ANAHTAR boş. Yöneticinin verdiği ajan anahtarını ajan.env dosyasına yaz.')
        self._acici = urllib.request.build_opener(_YonlendirmeYok)

    def istek(self, yol, govde=None):
        """(http_kod, json) döner. Ağ hatasında OSError fırlatır."""
        veri = json.dumps(govde or {}).encode('utf-8')
        r = urllib.request.Request(self.sunucu + yol, data=veri, method='POST', headers={
            'Content-Type': 'application/json', 'X-API-Key': self.anahtar, 'User-Agent': 'servis-ajan/1'})
        try:
            with self._acici.open(r, timeout=ZAMAN_ASIMI_SN) as y: kod, ham = y.status, y.read()
        except urllib.error.HTTPError as e:
            kod, ham = e.code, e.read()
        except http.client.HTTPException as e:                       # IncompleteRead, BadStatusLine...: ağ hatası gibi (yeniden denenir)
            raise OSError('HTTP yanıtı bozuk: %r' % (e,))
        try: d = json.loads(ham.decode('utf-8'))
        except ValueError: return kod, {}
        return kod, d if isinstance(d, dict) else {}


def _yazici():
    import etiket_yazici as EY      # ayar_oku() ortam değişkenlerini önce yüklesin diye geç içe aktarılır
    return EY


def bir_tur(ist, gonder=None):
    """Bir sorgu turu. 'is' (bir etiket işlendi), 'bos' (iş yok) ya da 'hata' döner.
    gonder: ham baytları yazıcıya yollayan (ok, mesaj) fonksiyonu (testte taklit edilir)."""
    gonder = gonder or _yazici().gonder
    kod, d = ist.istek('/api/v1/ajan/sonraki')
    if kod == 401: raise AnahtarHatasi(d.get('hata') or 'Ajan anahtarı geçersiz ya da kapatılmış.')
    if kod != 200 or not d.get('ok'): raise OSError(f'Sunucu yanıtı beklenmedik (HTTP {kod}).')
    is_ = d.get('is')
    if not is_: return 'bos'
    try:
        bayt = base64.b64decode(is_['veri'], validate=True)
        ok, mesaj = gonder(bayt)
    except Exception as e:                                           # noqa: BLE001 - bozuk veri yazıcı hatası gibi bildirilir
        log.exception('Etiket işlenemedi: %r', e); ok, mesaj = False, 'Etiket verisi okunamadı.'
    log.info('Etiket %s: %s x%s (%s)', 'basıldı' if ok else 'BASILAMADI', is_.get('plaka'), is_.get('adet'), mesaj)
    for deneme in range(5):                                          # sonuç bildirimi: basıldıktan sonra aynı iş ASLA tekrar basılmaz
        try:
            k2, _ = ist.istek('/api/v1/ajan/sonuc', {'id': is_['id'], 'ok': bool(ok), 'mesaj': mesaj})
            if k2 == 200 or (400 <= k2 < 500 and k2 != 429): break    # sunucu aldı ya da kalıcı red; 429/5xx geçici: yeniden dene
            log.warning('Sonuç bildirilemedi (%d/5): HTTP %s', deneme + 1, k2)
        except OSError as e:
            log.warning('Sonuç bildirilemedi (%d/5): %r', deneme + 1, e)
        time.sleep(2)
    return 'is'


def calis(ist):
    bekle, son_hata = SORGU_SN, None
    log.info('Ajan başladı: %s', ist.sunucu)
    while True:
        try:
            if bir_tur(ist) == 'is': bekle = 0.2; son_hata = None; continue     # kuyrukta başka iş olabilir: hemen sor
            bekle = SORGU_SN; son_hata = None
        except AnahtarHatasi as e:
            if son_hata != str(e): log.error('%s', e)
            son_hata = str(e); bekle = BEKLEME_ENFAZLA_SN
        except Exception as e:                                       # noqa: BLE001 - beklenmedik hata da ajanı düşürmesin (ağ, bozuk yanıt...)
            if son_hata != str(e): log.warning('Sunucuya ulaşılamıyor / beklenmedik hata: %r (tekrar denenecek)', e)
            son_hata = str(e); bekle = min(max(bekle * 2, 5.0), BEKLEME_ENFAZLA_SN)
        time.sleep(bekle)


def log_kur(dosya=True):
    log.setLevel(logging.INFO); bicim = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    if dosya:
        h = logging.handlers.RotatingFileHandler(os.path.join(KLASOR, 'ajan.log'), maxBytes=500_000, backupCount=2, encoding='utf-8')
    else:
        h = logging.StreamHandler()
    h.setFormatter(bicim); log.addHandler(h)
    if dosya and sys.stdout is not None and sys.stdout.isatty():
        s = logging.StreamHandler(); s.setFormatter(bicim); log.addHandler(s)


DENEME_TSPL = ('\r\nSIZE 58 mm,40 mm\r\nGAP 3 mm,0\r\nDIRECTION 1\r\nCLS\r\nTEXT 40,60,"3",0,2,2,"AJAN DENEME"\r\n'
               'TEXT 40,140,"2",0,1,1,"Servis Defteri yazdirma ajani"\r\nTEXT 40,190,"2",0,1,1,"Yazici baglantisi calisiyor"\r\nPRINT 1,1\r\n').encode('ascii')


def main(argv):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass                                           # noqa: BLE001
    a = ayar_oku()
    if '--durum' in argv:
        d = _yazici().yazici_durumu(); print(d['mesaj']); return 0 if d['durum'] == 'hazir' else 1
    if '--deneme' in argv:
        ok, m = _yazici().gonder(DENEME_TSPL); print(m); return 0 if ok else 1
    try: ist = Istemci(a.get('SUNUCU'), a.get('ANAHTAR'))
    except ValueError as e:
        print('Ayar hatası:', e); return 2
    if '--baglanti' in argv:
        try: kod, d = ist.istek('/api/v1/ajan/ping')
        except OSError as e:
            print('Sunucuya ulaşılamadı:', e); return 1
        if kod == 200 and d.get('ok'): print('Bağlantı tamam. Dükkân:', d.get('dukkan')); return 0
        print('Anahtar kabul edilmedi:', d.get('hata') or f'HTTP {kod}'); return 1
    log_kur(); calis(ist); return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
