#!/usr/bin/env python3
"""Yönetici şifresini değiştirir. Uygulama klasöründe çalıştır:
    venv/bin/python sifre_degistir.py
Şifre ekranda görünmez. Hash data/.password_hash dosyasına yazılır (kodda şifre tutulmaz).
Sonra servisi yeniden başlat:  sudo systemctl restart servis-defteri.service
"""
import os, sys, getpass, hashlib, secrets
klasor = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
yol = os.path.join(klasor, '.password_hash')
p1 = getpass.getpass('Yeni şifre: ')
if len(p1) < 10: sys.exit('Şifre en az 10 karakter olmalı (harf+rakam+işaret karışık olsun).')
if p1 != getpass.getpass('Yeni şifre (tekrar): '): sys.exit('Şifreler uyuşmuyor.')
salt = secrets.token_bytes(16); h = hashlib.pbkdf2_hmac('sha256', p1.encode(), salt, 600000).hex()
os.makedirs(klasor, exist_ok=True)
fd = os.open(yol, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600); os.write(fd, f'pbkdf2_sha256$600000${salt.hex()}${h}'.encode()); os.close(fd)
ilk = os.path.join(klasor, 'ILK_SIFRE.txt')
if os.path.exists(ilk): os.remove(ilk); print('İlk kurulum şifre dosyası silindi.')
print('Tamam. Şimdi servisi yeniden başlat:  sudo systemctl restart servis-defteri.service')
print('(Not: Şifre değişince açık olan tüm oturumlar kapanır.)')
