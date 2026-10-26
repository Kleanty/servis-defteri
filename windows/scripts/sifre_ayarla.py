#!/usr/bin/env python3
"""Kurulum betiği içindir: şifreyi SERVIS_SIFRE ortam değişkeninden okuyup data/.password_hash dosyasına
PBKDF2 hash olarak yazar (şifre dosyada/kodda düz metin tutulmaz). Rastgele ilk şifre dosyasını siler."""
import os, sys, hashlib, secrets
klasor = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
p = os.environ.get('SERVIS_SIFRE', '')
if len(p) < 10: sys.exit('Şifre en az 10 karakter olmalı.')
salt = secrets.token_bytes(16); h = hashlib.pbkdf2_hmac('sha256', p.encode(), salt, 600000).hex()
os.makedirs(klasor, exist_ok=True)
with open(os.path.join(klasor, '.password_hash'), 'w') as f: f.write(f'pbkdf2_sha256$600000${salt.hex()}${h}')
ilk = os.path.join(klasor, 'ILK_SIFRE.txt')
if os.path.exists(ilk): os.remove(ilk)
print('Şifre ayarlandı.')
