"""USB termal etiket yazıcısına (XP-470B ve TSPL konuşan muadilleri) doğrudan, ham TSPL ile yazdırma.

Tek etiket türü: 58 x 40 mm, yatay (solda büyük QR, sağda işletme adı + plaka). CUPS / sürücü yok. (Bu modül yalnız USB yazıcıya yazar; telefondan Bluetooth ile basma tarayıcıda çalışır, bu modülü kullanmaz.)
Yazıcı önce pyusb ile doğrudan bulunur (Linux sürücüsü ayrılır, ham TSPL gönderilir); olmazsa /dev/usb/lp* denenir.
Flask'a bağımlı değildir.

Kısa kullanım:
    ok, mesaj = etiket_bas('35ABC123', 'https://servis.example.com/arac/XXXX')

Ortam değişkenleri (hepsi isteğe bağlı):
    ETIKET_USB_ID    yazıcının USB kimliği (lsusb), varsayılan 2d37:82c5 (yoksa otomatik aranır)
    ETIKET_BASLIK    etikette yazan işletme adı (varsayılan: SERVIS DEFTERI; en fazla 18 karakter, Türkçe harfler ASCII'ye çevrilir)
    ETIKET_AYGIT     yazıcı aygıtı (varsayılan: /dev/etiket varsa o, yoksa ilk /dev/usb/lp*)
    ETIKET_GAP_MM    etiketler arası boşluk, varsayılan 3
    ETIKET_YON       DIRECTION 0 veya 1, varsayılan 1  (etiket ters çıkarsa değiştir)
    ETIKET_X_OFFSET  sağa/sola kaydırma (nokta; 8 nokta = 1 mm), varsayılan 24 (3 mm sağa)
    ETIKET_Y_OFFSET  yukarı/aşağı kaydırma (nokta), varsayılan 16 (2 mm aşağı)
    ETIKET_YOGUNLUK  koyuluk 1-15, varsayılan 8
"""
import errno, glob, io, logging, os, re, select, threading, time

log = logging.getLogger('etiket')

ETIKET_W_MM, ETIKET_H_MM = 58, 40      # 203 dpi = 8 nokta/mm
NOKTA_MM = 8
BILINEN_USB = (0x2d37, 0x82c5)

_kilit = threading.Lock()           # aynı anda tek iş: iki dokunuşta komutlar iç içe girmesin
_son_gonderim = {}                  # plaka -> zaman; art arda çift dokunuşu engeller
CIFT_DOKUNUS_SN = 3.0

_TR = str.maketrans('ÇĞİıÖŞÜçğöşüÂÎÛâîû', 'CGIIOSUcgosuAIUaiu')


def _env_int(ad, varsayilan):
    try: return int(os.environ.get(ad, varsayilan))
    except ValueError: return varsayilan


def _ascii(s, uzun=40):
    """Etikette yalnızca ASCII: yazıcı yazı tiplerinin Türkçe karakter desteği firmware'e göre değişir."""
    s = str(s or '').translate(_TR).upper()
    return re.sub(r'[^A-Z0-9 .:/+()\-]', '', s)[:uzun].strip()


def plaka_yaz(plaka):
    """35ABC123 -> '35 ABC 123' (il kodu + harfler + rakamlar)."""
    m = re.match(r'^(\d{1,2})([A-Z]{1,3})(\d{1,4})$', str(plaka or '').upper().replace(' ', ''))
    return ' '.join(m.groups()) if m else _ascii(plaka, 14)


# ----------------------------------------------------------------- aygıt
def aygit_bul():
    e = os.environ.get('ETIKET_AYGIT', '').strip()
    if e: return e
    if os.path.exists('/dev/etiket'): return '/dev/etiket'
    bulunan = sorted(glob.glob('/dev/usb/lp*'))
    return bulunan[0] if bulunan else '/dev/usb/lp0'


def _usb_modul():
    try:
        import usb.core, usb.util          # noqa: F401
        return usb
    except Exception:                      # noqa: BLE001 - pyusb ya da libusb kurulu değil
        return None


def _usb_bul():
    """Yazıcının (vid, pid) değeri; yoksa None. Sıra: ETIKET_USB_ID, bilinen yazıcı, (lp aygıtı yoksa) otomatik tarama."""
    usb = _usb_modul()
    if usb is None or os.environ.get('ETIKET_AYGIT', '').strip(): return None
    try:
        e = os.environ.get('ETIKET_USB_ID', '').strip().lower()
        if e:
            v, p = e.split(':'); v, p = int(v, 16), int(p, 16)
            return (v, p) if usb.core.find(idVendor=v, idProduct=p) else None
        if usb.core.find(idVendor=BILINEN_USB[0], idProduct=BILINEN_USB[1]): return BILINEN_USB
        if os.path.exists(aygit_bul()): return None                  # çekirdek yazıcı aygıtı var: onu kullan
        for d in usb.core.find(find_all=True) or []:
            if d.bDeviceClass == 9: continue                       # hub
            for cfg in d:
                for intf in cfg:
                    if intf.bInterfaceClass == 7 and any(
                            usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT for ep in intf):
                        return (d.idVendor, d.idProduct)
    except Exception as ex:                # noqa: BLE001
        log.warning('USB tarama hatası: %r', ex)
    return None


def _yaz_usb(vp, veri, zaman_asimi=8.0):
    usb = _usb_modul()
    if usb is None: raise FileNotFoundError('pyusb yok')
    dev = usb.core.find(idVendor=vp[0], idProduct=vp[1])
    if dev is None: raise FileNotFoundError('usb yazıcı yok')
    try:
        try: dev.set_configuration()
        except usb.core.USBError as ex:
            if getattr(ex, 'errno', None) == errno.EBUSY: pass      # zaten ayarlı
            else: raise
        cfg = dev.get_active_configuration(); hedef = None
        try:                                                        # önce arayüz 0 / alternatif 0, sonra diğerleri
            for ep in cfg[(0, 0)]:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT: hedef = (cfg[(0, 0)], ep); break
        except (KeyError, IndexError, TypeError): pass
        if hedef is None:
            for intf in cfg:
                for ep in intf:
                    if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT: hedef = (intf, ep); break
                if hedef: break
        if hedef is None: raise OSError(errno.ENODEV, 'OUT uç noktası bulunamadı')
        intf, ep = hedef
        try:
            if dev.is_kernel_driver_active(intf.bInterfaceNumber): dev.detach_kernel_driver(intf.bInterfaceNumber)
        except (NotImplementedError, usb.core.USBError): pass
        usb.util.claim_interface(dev, intf.bInterfaceNumber)
        bitis, gidilen = time.monotonic() + zaman_asimi, 0
        while gidilen < len(veri):
            kalan = bitis - time.monotonic()
            if kalan <= 0: raise TimeoutError('yazıcı yanıt vermedi')
            try: gidilen += ep.write(veri[gidilen:gidilen + 4096], timeout=int(min(kalan, 3.0) * 1000))
            except usb.core.USBTimeoutError: raise TimeoutError('yazıcı yanıt vermedi')
    except usb.core.USBError as ex:
        en = getattr(ex, 'errno', None)
        if en == errno.EACCES: raise PermissionError(ex)
        if en in (errno.ENODEV, errno.EIO): raise FileNotFoundError(ex)
        raise
    finally:
        try: usb.util.dispose_resources(dev)
        except Exception: pass                                      # noqa: BLE001


def _yaz(aygit, veri, zaman_asimi=8.0):
    """O_NONBLOCK + select: yazıcı yanıt vermezse (kâğıt bitti, kapak açık, tampon dolu) sonsuza dek takılmaz.
    Aksi halde sunucunun tüm iş parçacıkları bu yazıda bloke olup panel donabilir."""
    fd = os.open(aygit, os.O_WRONLY | os.O_NONBLOCK)
    try:
        bitis, gidilen = time.monotonic() + zaman_asimi, 0
        while gidilen < len(veri):
            kalan = bitis - time.monotonic()
            if kalan <= 0: raise TimeoutError('yazıcı yanıt vermedi')
            _, w, _ = select.select([], [fd], [], min(kalan, 1.0))
            if not w: continue
            try: gidilen += os.write(fd, veri[gidilen:gidilen + 4096])
            except BlockingIOError: continue
    finally:
        os.close(fd)


def yazici_durumu():
    """Kâğıt/kapak durumunu tek yönlü TSPL'den güvenle okuyamayız; sadece bağlantıyı ve izni denetleriz."""
    vp = _usb_bul()
    if vp: return {'durum': 'hazir', 'aygit': 'usb:%04x:%04x' % vp, 'mesaj': 'Yazıcı hazır (doğrudan USB).'}
    a = aygit_bul()
    if not os.path.exists(a):
        return {'durum': 'yok', 'aygit': a, 'mesaj': 'Yazıcı bağlı değil. USB kablosunu ve yazıcının açık olduğunu kontrol et.'}
    if not os.access(a, os.W_OK):
        return {'durum': 'izin_yok', 'aygit': a, 'mesaj': 'Yazıcı bağlı ama uygulamanın izni yok. (Kurulum notu: lp grubu / udev kuralı)'}
    return {'durum': 'hazir', 'aygit': a, 'mesaj': 'Yazıcı hazır.'}


# ----------------------------------------------------------------- TSPL şablonu (58 x 40 yatay)
def _qr_bilgi(url):
    """URL için QR sürümü ve modül sayısı (yerleşimi önceden bilmek için)."""
    import qrcode
    q = qrcode.QRCode(error_correction=0, border=0)       # 0 = M
    q.add_data(url); q.make(fit=True)
    return q.version, 17 + 4 * q.version


def _baslik():
    """Etiket başlığı: ETIKET_BASLIK (yoksa SERVIS DEFTERI), ASCII, büyük harf, en fazla 18 karakter."""
    return _ascii(os.environ.get('ETIKET_BASLIK', '') or 'SERVIS DEFTERI', 18).upper().strip() or 'SERVIS'


def tspl_komutlari(plaka, url):
    """Etiketin TSPL komut satırları (liste). Gönderirken \\r\\n ile birleştirilir."""
    W, H = ETIKET_W_MM * NOKTA_MM, ETIKET_H_MM * NOKTA_MM
    xo, yo = _env_int('ETIKET_X_OFFSET', 24), _env_int('ETIKET_Y_OFFSET', 16)
    pl = plaka_yaz(plaka)
    kom = [f'SIZE {ETIKET_W_MM} mm,{ETIKET_H_MM} mm', f'GAP {min(max(_env_int("ETIKET_GAP_MM", 3), 0), 20)} mm,0 mm',
           f'DIRECTION {_env_int("ETIKET_YON", 1)}', 'REFERENCE 0,0',
           f'DENSITY {min(max(_env_int("ETIKET_YOGUNLUK", 8), 1), 15)}', 'SPEED 4', 'CLS']

    def yazi(x, y, font, metin):
        kom.append(f'TEXT {x + xo},{y + yo},"{font}",0,1,1,"{metin}"')
        kom.append(f'TEXT {x + xo + 1},{y + yo},"{font}",0,1,1,"{metin}"')      # 1 nokta kaydırıp tekrar: sahte kalın

    v, mod = _qr_bilgi(url)
    hucre = max(min((H - 20) // (17 + 4 * (v + 1)), 10), 3)    # yazıcı bir üst sürüm seçse bile taşmasın
    qr_w = mod * hucre
    qy = max(min((H - qr_w) // 2, H - (mod + 4) * hucre - 4), 8)
    url_t = re.sub(r'[^\x21-\x7e]|"', '', str(url))                # TSPL tırnak içinde: tırnak/boşluk/denetim karakteri komut kırmasın
    kom.append(f'QRCODE {12 + xo},{qy + yo},M,{hucre},A,0,"{url_t}"')
    sx = 12 + qr_w + 14
    sag = W - (sx + xo) - 6
    parcalar = pl.split(' ')                                  # '35','ABC','123' -> her biri kendi satırında, büyük
    uzun = max(len(p) for p in parcalar)                      # uzun/yabancı plakalarda yazı tipi küçülür, taşmaz
    font, yuk = next((f, h) for f, cw, h in (('5', 32, 48), ('4', 24, 32), ('3', 16, 24), ('2', 12, 20), ('1', 8, 12)) if uzun * cw + 1 <= sag or f == '1')
    govde = 24 + 4 + 24 + 14 + len(parcalar) * (yuk + 6)
    y = max((H - govde) // 2, 8)
    kelimeler = _baslik().split(' ', 1)                       # ilk kelime 1. satır, kalanı 2. satır (satır başına en fazla 9 karakter)
    satirlar = [k[:9] for k in kelimeler]
    mf = '3' if max(len(k) for k in satirlar) * 16 <= sag else '2'
    for i, k in enumerate(satirlar): yazi(sx, y + 28 * i, mf, k)
    y += 24 + 4 + 24 + 14
    for p in parcalar:
        yazi(sx, y, font, p); y += yuk + 6
    return kom


def tspl_bayt(komutlar, adet=1):
    adet = min(max(int(adet or 1), 1), 20)
    return ('\r\n' + '\r\n'.join(komutlar + [f'PRINT 1,{adet}']) + '\r\n').encode('ascii', 'replace')


# ----------------------------------------------------------------- gönderme
def _hata_mesaji(e):
    if isinstance(e, TimeoutError):
        return 'Yazıcı yanıt vermiyor. Kapağı, kâğıdı ve yazıcının açık olduğunu kontrol et.'
    if isinstance(e, FileNotFoundError) or getattr(e, 'errno', None) in (errno.ENOENT, errno.ENODEV, errno.ENXIO):
        return 'Yazıcı bağlı değil. USB kablosunu ve yazıcının açık olduğunu kontrol et.'
    if isinstance(e, PermissionError):
        return 'Yazıcı portuna izin yok. Kurulum notundaki "lp grubu" / udev adımını uygula.'
    if getattr(e, 'errno', None) == errno.EBUSY:
        return 'Yazıcı başka bir program tarafından kullanılıyor (CUPS kurulu olabilir). 10 sn sonra tekrar dene.'
    return 'Yazıcıya gönderilemedi. Yazıcıyı kapatıp açıp tekrar dene.'


def gonder(veri):
    """Ham baytları yazıcıya yolla. (ok, mesaj) döner; asla istisna fırlatmaz."""
    a = aygit_bul(); vp = _usb_bul()
    if not _kilit.acquire(timeout=3):
        return False, 'Yazıcı şu an meşgul. Birkaç saniye sonra tekrar bas.'
    try:
        if vp:
            try: _yaz_usb(vp, veri)
            except (PermissionError, FileNotFoundError):
                if not os.path.exists(a): raise                    # lp aygıtı da yok: asıl hatayı göster
                log.warning('Doğrudan USB olmadı, %s deneniyor', a); _yaz(a, veri)
        else: _yaz(a, veri)
        return True, 'Etiket yazıcıya gönderildi.'
    except Exception as e:                    # noqa: BLE001 - kullanıcıya anlaşılır mesaj, ayrıntı log'a
        log.warning('Etiket yazdırılamadı (%s): %r', vp or a, e)
        return False, _hata_mesaji(e)
    finally:
        _kilit.release()


def etiket_bas(plaka, url, adet=1):
    """Araç etiketini yazdır. (ok, mesaj) döner."""
    try:
        simdi = time.monotonic()
        if simdi - _son_gonderim.get(plaka, -99) < CIFT_DOKUNUS_SN:
            return False, 'Etiket az önce gönderildi. Çift basmamak için 3 saniye bekle.'
        ok, mesaj = gonder(tspl_bayt(tspl_komutlari(plaka, url), adet))
        if ok: _son_gonderim[plaka] = simdi
        return ok, mesaj
    except Exception as e:                    # noqa: BLE001 - şablon/QR hatası da işi çökertmesin
        log.exception('Etiket hazırlanamadı: %r', e)
        return False, 'Etiket hazırlanamadı (iç hata). Kayıtlar data/uygulama.log dosyasında.'


# ----------------------------------------------------------------- önizleme (yaklaşık; gerçek yazı tipleri biraz farklıdır)
_FONT = {'1': (8, 12), '2': (12, 20), '3': (16, 24), '4': (24, 32), '5': (32, 48)}


def onizleme_png(komutlar):
    """TSPL komutlarından kabaca bir PNG üretir: yerleşimin sığıp sığmadığını yazıcı olmadan görmek için."""
    from PIL import Image, ImageDraw, ImageFont
    import qrcode
    w = h = 0
    for k in komutlar:
        m = re.match(r'SIZE (\d+) mm,(\d+) mm', k)
        if m: w, h = int(m.group(1)) * NOKTA_MM, int(m.group(2)) * NOKTA_MM
    im = Image.new('L', (w, h), 255); d = ImageDraw.Draw(im)
    kok = os.path.dirname(os.path.abspath(__file__))
    # Önce pakete eklenen yazı tipi (Windows/Linux fark etmez), yoksa sistemdekiler; hiçbiri yoksa küçük varsayılan yazı tipi
    yol = next((p for p in (os.path.join(kok, 'static', 'fonts', 'DejaVuSansMono-Bold.ttf'),
                            r'C:\Windows\Fonts\consolab.ttf', r'C:\Windows\Fonts\courbd.ttf',
                            '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf') if os.path.exists(p)), None)
    fontlar = {}
    for k in komutlar:
        m = re.match(r'TEXT (-?\d+),(-?\d+),"(\w)",0,(\d+),(\d+),"(.*)"$', k)
        if m:
            x, y, f, xm, ym, t = int(m[1]), int(m[2]), m[3], int(m[4]), int(m[5]), m[6]
            cw, ch = _FONT.get(f, (16, 24))
            for i, c in enumerate(t):
                g = Image.new('L', (cw, ch), 255); gd = ImageDraw.Draw(g)
                if ch not in fontlar: fontlar[ch] = ImageFont.truetype(yol, int(ch * 0.85)) if yol else ImageFont.load_default()
                fnt = fontlar[ch]
                gd.text((cw // 2, ch // 2), c, font=fnt, fill=0, anchor='mm')
                g = g.resize((cw * xm, ch * ym)); im.paste(g, (x + i * cw * xm, y))
            continue
        m = re.match(r'QRCODE (-?\d+),(-?\d+),(\w),(\d+),\w,0,"(.*)"$', k)
        if m:
            x, y, hc, url = int(m[1]), int(m[2]), int(m[4]), m[5]
            q = qrcode.QRCode(error_correction=0, border=0); q.add_data(url); q.make(fit=True)
            for r_, satir in enumerate(q.get_matrix()):
                for c_, v in enumerate(satir):
                    if v: d.rectangle((x + c_ * hc, y + r_ * hc, x + (c_ + 1) * hc - 1, y + (r_ + 1) * hc - 1), fill=0)
            continue
        m = re.match(r'BOX (\d+),(\d+),(\d+),(\d+),(\d+)', k)
        if m:
            x1, y1, x2, y2, t = map(int, m.groups())
            for i in range(t): d.rectangle((x1 + i, y1 + i, x2 - i, y2 - i), outline=0)
    b = io.BytesIO(); im.convert('1').save(b, 'PNG', dpi=(203, 203)); return b.getvalue()
