"""Ortak yardımcılar: klasör yolu ve .env okuma (Windows'ta systemd'nin EnvironmentFile işini yapar)."""
import os, sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def env_yukle(yol=None):
    """KOK/.env dosyasını okuyup ortam değişkeni yapar. Gerçek ortam değişkenleri önceliklidir.
    Biçim: ANAHTAR=değer (satır başı # yorumdur; değerin yanına yorum yazma)."""
    yol = yol or os.path.join(KOK, '.env')
    try:
        with open(yol, encoding='utf-8-sig') as f: satirlar = f.read().splitlines()
    except OSError:
        return 0
    n = 0
    for s in satirlar:
        s = s.strip()
        if not s or s.startswith('#') or '=' not in s: continue
        k, v = s.split('=', 1); k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'': v = v[1:-1]
        if k and k not in os.environ: os.environ[k] = v; n += 1
    return n


def utf8_cikti():
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding='utf-8', errors='replace')
        except Exception: pass              # noqa: BLE001 - pythonw'de stdout yoktur
