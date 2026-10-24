"""58 x 40 mm yatay QR etiketi için ham TSPL komutları (Xprinter XP-470B ve TSPL konuşan muadilleri).

Bu sürümde sunucu yazıcıya BAĞLANMAZ: etiketin TSPL baytlarını üretir, telefon (dükkânda) Bluetooth ile yazıcıya gönderir.
Flask'a bağımlı değildir.

Ortam değişkenleri (hepsi isteğe bağlı):
    ETIKET_BASLIK    dükkân adı verilmediğinde etikette yazan ad (varsayılan: SERVIS DEFTERI; en fazla 18 karakter, Türkçe harfler ASCII'ye çevrilir)
    ETIKET_GAP_MM    etiketler arası boşluk, varsayılan 3
    ETIKET_YON       DIRECTION 0 veya 1, varsayılan 1  (etiket ters çıkarsa değiştir)
    ETIKET_X_OFFSET  sağa/sola kaydırma (nokta; 8 nokta = 1 mm), varsayılan 24 (3 mm sağa)
    ETIKET_Y_OFFSET  yukarı/aşağı kaydırma (nokta), varsayılan 16 (2 mm aşağı)
    ETIKET_YOGUNLUK  koyuluk 1-15, varsayılan 8
"""
import io, os, re

ETIKET_W_MM, ETIKET_H_MM = 58, 40      # 203 dpi = 8 nokta/mm
NOKTA_MM = 8

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


# ----------------------------------------------------------------- TSPL şablonu (58 x 40 yatay)
def _qr_bilgi(url):
    """URL için QR sürümü ve modül sayısı (yerleşimi önceden bilmek için)."""
    import qrcode
    q = qrcode.QRCode(error_correction=0, border=0)       # 0 = M
    q.add_data(url); q.make(fit=True)
    return q.version, 17 + 4 * q.version


def _baslik(baslik=None):
    """Etiket başlığı: dükkân adı (verilmezse ETIKET_BASLIK, o da yoksa SERVIS DEFTERI), ASCII, büyük harf, en fazla 18 karakter."""
    return _ascii(baslik or os.environ.get('ETIKET_BASLIK', '') or 'SERVIS DEFTERI', 18).upper().strip() or 'SERVIS'


def tspl_komutlari(plaka, url, baslik=None):
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
    kelimeler = _baslik(baslik).split(' ', 1)                       # ilk kelime 1. satır, kalanı 2. satır (satır başına en fazla 9 karakter)
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
