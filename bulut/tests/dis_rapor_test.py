# Dış kod incelemesi (2026-10-29) düzeltmeleri: form gövdesi maskeleme, umask, USB tarama sınıfı, örnek iletişim bilgisi, .gitignore.
import os,re,sys,shutil,tempfile,types
os.environ['FORCE_HTTPS_COOKIE']='0'
d=tempfile.mkdtemp(); shutil.copytree(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),d+'/a',ignore=shutil.ignore_patterns('data','__pycache__')); os.chdir(d+'/a'); sys.path.insert(0,'.')
sys.path.insert(0,'yazdirma_ajani')
import app as A
import importlib.util as _u
_sp=_u.spec_from_file_location('ey_ajan','yazdirma_ajani/etiket_yazici.py'); EY=_u.module_from_spec(_sp); _sp.loader.exec_module(EY)
ok=0;fail=0
def k(ad,c):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print('BAŞARISIZ:',ad)
M=A._ent_maskele
# 1) JSON ve FORM gövdesi: telefon/adres/e-posta maskelenir, plaka/km kalır
j=M('{"plaka":"34ABC123","telefon":"05551112233","eposta":"a@b.com","adres":"Sok 1","km":1000}')
k('JSON maskelenir',all(x not in j for x in ('05551112233','a@b.com','Sok 1')) and '34ABC123' in j)
f=M('plaka=34ABC123&eposta=ali%40ornek.com&adres=Atat%C3%BCrk+Cad.+5&tel=0555+111+22+33&km=1000')
k('form: e-posta gizlenir',('ornek.com' not in f) and ('ali' not in f))
k('form: adres gizlenir','Cad' not in f and 'rk' not in f.split('adres=')[1].split('&')[0].replace('***',''))
k('form: telefon gizlenir','111' not in f)
k('form: plaka ve km korunur','plaka=34ABC123' in f and 'km=1000' in f)
k('form: E-Mail/Phone büyük harf de gizlenir','ornek' not in M('EMAIL=x%40ornek.com&Phone=05551112233'))
k('ayrıştırılamayan gövdede e-posta gizlenir','ali@ornek.com' not in M('bozuk veri ali@ornek.com gönder'))
k('boş gövde hata vermez',M('')=='' and M(None)=='')
# 2) Dosya izinleri: umask 077
k('umask 077 uygulanır',os.umask(0o077)==0o077)
# 3) USB otomatik tarama: yalnız yazıcı sınıfı (7); 255 (üreticiye özel) tek başına yetmez
class Ep: 
    bEndpointAddress=0x01
def aygit(sinif):
    intf=[Ep()]; intf=type('I',(list,),{'bInterfaceClass':sinif})(intf); cfg=[intf]
    class D(list):
        bDeviceClass=0; idVendor=0x1234; idProduct=0x5678
    return D([cfg])
def sahte(aygitlar):
    m=types.SimpleNamespace()
    m.core=types.SimpleNamespace(find=lambda find_all=False,**kw: (aygitlar if find_all else None))
    m.util=types.SimpleNamespace(endpoint_direction=lambda a: 0, ENDPOINT_OUT=0)
    return m
for ad,sinif,beklenen in (('sınıf 7 yazıcı bulunur',7,(0x1234,0x5678)),('sınıf 255 cihaz yazıcı sanılmaz',255,None)):
    EY._usb_modul=lambda a=aygit(sinif): sahte([a])
    os.environ.pop('ETIKET_USB_ID',None); os.environ.pop('ETIKET_AYGIT',None)
    eski=EY.aygit_bul; EY.aygit_bul=lambda: '/yok/lp0'
    try: k(ad,EY._usb_bul()==beklenen)
    finally: EY.aygit_bul=eski
# 4) Örnek telefon/adres canlı kurulumda görünmez
env=open('.env.example',encoding='utf-8').read()
k('.env.example örnek telefon/adres içermez','0555 000' not in env and 'Örnek Mah' not in env)
# 5) .gitignore paketle birlikte gelir ve sırları dışlar
gi=open('.gitignore',encoding='utf-8').read()
k('.gitignore var ve data/.env/venv dışlar',all(x in gi for x in ('data/','.env','venv/','__pycache__/')))
# 6) udev: üreticiye özel sınıf için genel izin yok
r=open('deploy/99-etiket.rules',encoding='utf-8').read() if os.path.exists('deploy/99-etiket.rules') else ''
k('udev: ff sınıfına genel izin yok','*:ff????:*"' not in r)
# 7) gidiş zamanı: API'nin gönderdiği öncelikli
src=open('app.py',encoding='utf-8').read()
k("gidiş: gelen değer eskisinden önce","(v.get('gidis') or gidis or t)" in src)
print(f'{ok} kontrol geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
