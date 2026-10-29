import os as _os; _os.environ['APP_PASSWORD_HASH']='pbkdf2_sha256$600000$0123456789abcdef0123456789abcdef$bc43d8da4a5cfd47df54d15115d65eafe20121e09ab04ca54ddf8dd8397d4335'   # test şifresi: TestSifre-12345!
# pyusb yedek yolu testi: gerçek yazıcı yok, usb.core.find sahte cihazla değiştirilir
import os,sys,tempfile
os.environ.pop('ETIKET_KURU',None); os.environ.pop('ETIKET_AYGIT',None)
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import errno, usb.core, usb.util
import etiket_yazici as EY
ok=fail=0
def k(ad,c):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print('BAŞARISIZ:',ad)
class EP:
    def __init__(s,addr,out=None,hata=None): s.bEndpointAddress=addr; s.bmAttributes=2; s.yazilan=bytearray(); s.hata=hata
    def write(s,b,timeout=0):
        if s.hata: raise s.hata
        s.yazilan+=bytes(b); return len(b)
class Intf(list):
    def __init__(s,sinif,eps,no=0): super().__init__(eps); s.bInterfaceClass=sinif; s.bInterfaceNumber=no
class Dev:
    def __init__(s,vid,pid,sinif,eps,dc=0,kd=False):
        s.idVendor=vid; s.idProduct=pid; s.bDeviceClass=dc; s._i=Intf(sinif,eps); s.kd=kd; s.det=False
    def __iter__(s): return iter([[s._i]])
    def set_configuration(s): pass
    def get_active_configuration(s): return [s._i]
    def is_kernel_driver_active(s,n): return s.kd
    def detach_kernel_driver(s,n): s.det=True
yazici=Dev(0x0483,0x5743,7,[EP(0x01)],kd=True); hub=Dev(0x1d6b,2,9,[],dc=9); disk=Dev(0x1234,1,8,[EP(0x02)])
def sahte(*cihazlar):
    def find(find_all=False,idVendor=None,idProduct=None):
        l=[d for d in cihazlar if (idVendor is None or d.idVendor==idVendor) and (idProduct is None or d.idProduct==idProduct)]
        return l if find_all else (l[0] if l else None)
    usb.core.find=find
    usb.util.claim_interface=lambda d,n: None; usb.util.dispose_resources=lambda d: None
sahte(hub,disk,yazici)
k('hub ve disk atlanır, yazıcı bulunur',EY._usb_bul()==(0x0483,0x5743))
d=EY.yazici_durumu(); k('durum hazır (doğrudan USB)',d['durum']=='hazir' and d['aygit']=='usb:0483:5743')
ok_,m=EY.gonder(b'TSPL-VERISI'); k('gönderim başarılı',ok_ and bytes(yazici._i[0].yazilan)==b'TSPL-VERISI')
k('çekirdek sürücüsü ayrıldı',yazici.det)
yazici._i[0].yazilan=bytearray(); ok_,m=EY.etiket_bas('35ABC123','https://x/arac/abc',2); k('etiket_bas USB üzerinden (2 adet)',ok_ and yazici._i[0].yazilan.count(b'PRINT 1,2')==1)
os.environ['ETIKET_USB_ID']='0483:5743'; k('ETIKET_USB_ID ile bulunur',EY._usb_bul()==(0x0483,0x5743)); os.environ['ETIKET_USB_ID']='dead:beef'; k('yanlış ID -> bulunamaz',EY._usb_bul() is None); os.environ.pop('ETIKET_USB_ID')
sahte(hub,disk); d=EY.yazici_durumu(); k('yazıcı yoksa durum "yok"',d['durum']=='yok'); ok_,m=EY.gonder(b'x'); k('yazıcı yoksa anlaşılır hata',not ok_ and 'bağlı değil' in m)
for hata,beklenen in ((usb.core.USBTimeoutError('t',errno.ETIMEDOUT),'yanıt vermiyor'),(usb.core.USBError('izin',None,errno.EACCES),'izin'),(usb.core.USBError('yok',None,errno.ENODEV),'bağlı değil')):
    y=Dev(0x0483,0x5743,7,[EP(0x01,hata=hata)]); sahte(y); ok_,m=EY.gonder(b'x'); k(f'hata -> mesaj ({beklenen})',not ok_ and beklenen in m)
# bilinen yazıcı kimliği (XP-470B) öncelikli bulunur; ETIKET_AYGIT verilirse USB yolu devreye girmez
xp=Dev(0x2d37,0x82c5,7,[EP(0x01)],kd=True); sahte(hub,disk,yazici,xp); k('bilinen XP-470B kimliği önceliklidir',EY._usb_bul()==(0x2d37,0x82c5))
xp._i[0].yazilan=bytearray(); ok_,m=EY.gonder(b'RAW'); k('XP-470B doğrudan USB ile yazılır',ok_ and bytes(xp._i[0].yazilan)==b'RAW' and xp.det)
# USB izin hatası + lp aygıtı varsa lp yoluna düşülür
import tempfile as _t; lpf=_t.mktemp(); open(lpf,'wb').close()
xe=Dev(0x2d37,0x82c5,7,[EP(0x01,hata=usb.core.USBError('izin',None,errno.EACCES))]); sahte(xe)
EY.aygit_bul=lambda: lpf; ok_,m=EY.gonder(b'LPYEDEK'); k('USB izni yok, lp var -> lp yoluna düşer',ok_ and open(lpf,'rb').read()==b'LPYEDEK'); os.remove(lpf)
os.environ['ETIKET_AYGIT']='/dev/yok_boyle_aygit'; sahte(yazici); k('ETIKET_AYGIT verilmişse USB yolu devreye girmez',EY._usb_bul() is None)
print(f'\n{ok} kontrol geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
