# -*- coding: utf-8 -*-
"""Servis Defteri API'sine TEK bir kayit gonderir (sunucunun disindaki herhangi bir bilgisayardan, deneme/entegrasyon kontrolu icin).
Calistirma:  python disaridan_gonder.py        (sorulari yanitla; API anahtari yazarken gorunmez)
Ek paket gerekmez (Python 3.7+). Anahtar dosyaya YAZILMAZ; istersen SERVIS_API_ANAHTARI ortam degiskeniyle ver.
UYARI: Bu GERCEK bir istektir. Plakanin sunucuda acik is emri varsa o is emri guncellenir (yapilan islem degisir)."""
import getpass, json, os, sys, time, urllib.request, urllib.error

ADRES = os.environ.get('SERVIS_API_ADRES', '')   # bos ise calisirken sorulur (orn. https://servis.alanadiniz.com/api/v1/is-emirleri)

ACIKLAMA = {
    200: 'BASARILI: kayit sunucudaki acik is emrine islendi (ya da ayni kayit_no daha once islenmisti).',
    202: 'KAYDEDILDI ama OTOMATIK ESLESMEDI: Servis Defteri > ust menu "Eslesmeyen" listesinde bekliyor. Nedeni asagida yazar. Bu da API\'nin dogru calistigini gosterir.',
    400: 'HTTPS gerekli: adres https:// ile baslamali.',
    401: 'API anahtari yanlis ya da eksik. Anahtari sunucudaki .env dosyasindan (ENTEGRASYON_API_ANAHTARI) kontrol et.',
    403: 'Cevabi uygulama degil Cloudflare/guvenlik duvari verdi. Cloudflare panelinde Security > Events bolumune bak.',
    404: 'API bu sunucuda kapali ya da adres yanlis (yeni app.py yuklu mu, anahtar .env icinde var mi?).',
    409: 'CAKISMA: bu kayit_no daha once FARKLI icerikle gonderilmis. Yeni bir kayit_no kullan.',
    422: 'Gonderilen bilgi gecersiz (plaka biçimi, durum vb.). Mesaji oku, duzelt, tekrar dene.',
    429: 'Cok fazla hatali anahtar denemesi; 5 dakika bekle.',
    500: 'Sunucu hatasi; biraz sonra ayni istegi tekrar dene.',
}

def sor(metin, varsayilan=''):
    c = input(metin).strip()
    return c or varsayilan

def main():
    print('=== Servis Defteri API - tek kayit gonder ===')
    global ADRES
    if not ADRES:
        a = sor('Sunucu adresi (orn. https://servis.alanadiniz.com): ').rstrip('/')
        if not a.lower().startswith('https://'): print('Adres https:// ile baslamali.'); return 1
        ADRES = a + '/api/v1/is-emirleri'
    print('Adres:', ADRES, '\n')
    plaka = sor('Plaka (orn. 35 ABC 123): ')
    if not plaka: print('Plaka zorunlu.'); return 1
    km = sor('Km (bos birakilabilir): ')
    islem = sor('Yapilan islem (birden fazlaysa virgulle ayir; bos birakilabilir): ')
    durum_no = sor('Durum: 1=Tamamlandi  2=Devam Ediyor  3=Beklemede  (bos = degistirme): ')
    kayit_no = sor('Kayit no (bos = otomatik TEST-... uretilir): ', 'TEST-%s' % time.strftime('%Y%m%d-%H%M%S'))

    govde = {'kayit_no': kayit_no, 'plaka': plaka}
    if km:
        if not km.isdigit(): print('Km sadece rakam olmali.'); return 1
        govde['km'] = int(km)
    if islem: govde['yapilan_islem'] = [x.strip() for x in islem.split(',') if x.strip()]
    durum = {'1': 'Tamamlandı', '2': 'Devam Ediyor', '3': 'Beklemede'}.get(durum_no)
    if durum: govde['durum'] = durum
    anahtar = os.environ.get('SERVIS_API_ANAHTARI') or getpass.getpass('API anahtari (yazarken gorunmez): ').strip()
    if not anahtar: print('Anahtar bos.'); return 1

    print('\nGonderilecek:', json.dumps(govde, ensure_ascii=False))
    if sor('Gonderilsin mi? (E/H): ', 'H').lower() != 'e': print('Iptal edildi, hicbir sey gonderilmedi.'); return 0

    istek = urllib.request.Request(ADRES, data=json.dumps(govde).encode('utf-8'), method='POST', headers={
        'Authorization': 'Bearer ' + anahtar, 'Content-Type': 'application/json',
        'User-Agent': 'DisaridanDeneme/1.0', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(istek, timeout=25) as r: kod, ham = r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e: kod, ham = e.code, e.read().decode('utf-8', 'replace')
    except (urllib.error.URLError, OSError) as e:
        print('\nULASILAMADI:', e); print('Internet var mi? Sunucu ve (varsa) Cloudflare tuneli acik mi?'); return 1
    try: j = json.loads(ham)
    except ValueError: j = None
    print('\nHTTP', kod)
    print(json.dumps(j, ensure_ascii=False, indent=2) if j is not None else (ham[:300] or '(bos govde)'))
    print('\n' + ACIKLAMA.get(kod, 'Beklenmeyen kod.'))
    if j and j.get('neden'): print('Neden:', j['neden'])
    if j and j.get('hata'): print('Mesaj:', j['hata'])
    return 0 if kod in (200, 202) else 1

if __name__ == '__main__':
    try: sys.exit(main())
    except KeyboardInterrupt: print('\nIptal.'); sys.exit(1)
