#!/usr/bin/env python3
"""Kurulum denemesi: yazıcıdan örnek bir etiket çıkarır (gerçek araç kaydı oluşturmaz)."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ortam import KOK, env_yukle, utf8_cikti
utf8_cikti(); env_yukle(); sys.path.insert(0, KOK)
import etiket_yazici as EY

taban = (os.environ.get('PUBLIC_BASE_URL') or 'https://servis.example.com').rstrip('/')
ok, mesaj = EY.etiket_bas('34ABC123', taban + '/arac/DENEME-ETIKETI-1234567890')
print(('✔ ' if ok else '✘ ') + mesaj)
if ok: print('Etiket çıkmadıysa: yazıcıyı, kâğıdı ve kapağı kontrol et; sonra YAZICILARI-LISTELE.bat çalıştır.')
sys.exit(0 if ok else 1)
