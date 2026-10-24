#!/usr/bin/env python3
"""Windows'taki yazıcıları listeler ve uygulamanın etiket için hangisini seçeceğini gösterir."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortam import KOK, env_yukle, utf8_cikti
utf8_cikti(); env_yukle(); sys.path.insert(0, KOK)
import etiket_yazici as EY

w = EY._win_modul()
if w is None:
    sys.exit('Bu araç Windows içindir (pywin32 gerekir).')
liste = EY._win_yazicilar(w)
secilen = EY._win_hedef()
print('Bu bilgisayardaki yazıcılar:')
for p in liste: print('  %s %s' % ('>>' if p == secilen else '  ', p))
if secilen: print('\nEtiketler şu yazıcıya gidecek:', secilen)
else: print('\nEtiket yazıcısı BULUNAMADI. Yazıcı adında "XP-470", "Xprinter", "Etiket" veya "Label" geçmiyor.\n'
            'Çözüm: .env dosyasına ETIKET_YAZICI_ADI=<yukarıdaki adın bir parçası> yaz (örn. ETIKET_YAZICI_ADI=Zebra).')
