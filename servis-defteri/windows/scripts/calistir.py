#!/usr/bin/env python3
"""Uygulamayı .env ayarlarıyla başlatır (Windows'ta windows\\2-BASLAT.bat ve otomatik başlatma bunu çalıştırır).
Çökerse 5 saniye sonra kendini yeniden başlatır; her açılışta bir yedek alır.
.env:  PORT (varsayılan 5000)   DINLE_ADRES (varsayılan 127.0.0.1; yerel ağdan erişim için 0.0.0.0)"""
import os, sys, time, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortam import KOK, env_yukle, utf8_cikti


def cikti_ayarla():
    os.makedirs(os.path.join(KOK, 'data'), exist_ok=True)
    if sys.stdout is None or sys.stderr is None:       # pythonw.exe (pencere yok): çıktıyı dosyaya al
        yol = os.path.join(KOK, 'data', 'sunucu.log')
        if os.path.exists(yol) and os.path.getsize(yol) > 1_000_000: os.remove(yol)
        sys.stdout = sys.stderr = open(yol, 'a', encoding='utf-8', buffering=1)
    else:
        utf8_cikti()


def main():
    os.chdir(KOK); sys.path.insert(0, KOK)
    cikti_ayarla(); env_yukle()
    host = os.environ.get('DINLE_ADRES', '127.0.0.1').strip() or '127.0.0.1'
    try: port = int(os.environ.get('PORT', '5000') or 5000)
    except ValueError: port = 5000
    from waitress import serve
    import app as A
    try:
        import threading, yedek
        y = yedek.al(harici=False); print('Açılış yedeği:', y or 'veritabanı henüz yok', flush=True)
        threading.Thread(target=yedek.duzenli, daemon=True).start()      # USB/Drive kopyası açılışı yavaşlatmasın: arka planda
    except Exception as e:                  # noqa: BLE001 - yedek hatası açılışı engellemesin
        print('Açılış yedeği alınamadı:', e, flush=True)
    print('Servis Defteri %s:%s adresinde çalışıyor (durdurmak: Ctrl+C)' % (host, port), flush=True)
    while True:
        try:
            serve(A.app, host=host, port=port, threads=4)
            return
        except KeyboardInterrupt:
            return
        except Exception:                   # noqa: BLE001 - port meşgul vb.: bekleyip yeniden dene
            traceback.print_exc(); print('5 saniye sonra yeniden denenecek…', flush=True); time.sleep(5)


if __name__ == '__main__':
    main()
