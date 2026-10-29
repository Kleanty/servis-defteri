#!/usr/bin/env python3
"""Yönetici şifresini değiştirir. Uygulama klasöründe çalıştır:
    venv/bin/python scripts/sifre_degistir.py
Şifre ekranda görünmez. Hash data/.password_hash dosyasına yazılır (kodda şifre tutulmaz).
Sonra servisi yeniden başlat:  sudo systemctl restart servis-defteri.service
"""
import os, sys, getpass, hashlib, secrets
klasor = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')     # <proje>/data (scripts/ değil)
yol = os.path.join(klasor, '.password_hash')
print('Boş bırakıp Enter\'a basarsan işlem iptal olur (eski şifre geçerli kalır).')
while True:
    p1 = getpass.getpass('Yeni şifre: ')
    if not p1: sys.exit('İptal edildi, şifre değişmedi.')
    if len(p1) < 10: print('  Şifre en az 10 karakter olmalı (harf+rakam+işaret karışık olsun). Tekrar dene.'); continue
    if p1 != getpass.getpass('Yeni şifre (tekrar): '): print('  Şifreler uyuşmuyor. Baştan tekrar dene.'); continue
    break
salt = secrets.token_bytes(16); h = hashlib.pbkdf2_hmac('sha256', p1.encode(), salt, 600000).hex()
os.makedirs(klasor, exist_ok=True)
fd = os.open(yol, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600); os.write(fd, f'pbkdf2_sha256$600000${salt.hex()}${h}'.encode()); os.close(fd)
ilk = os.path.join(klasor, 'ILK_SIFRE.txt')
if os.path.exists(ilk): os.remove(ilk); print('İlk kurulum şifre dosyası silindi.')
print('Tamam. Şimdi uygulamayı yeniden başlat:  ' + ('windows\\YENIDEN-BASLAT.bat (yönetici olarak)' if os.name == 'nt' else 'sudo systemctl restart servis-defteri.service'))
print('(Not: Şifre değişince açık olan tüm oturumlar kapanır.)')
