# Kurulum betiklerinin hata yakalaması (statik denetim): rapor dosyası, adım izleme, Windows/Linux kurulum dosyalarının tutarlılığı.
import os, re, subprocess, sys
K = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = fail = 0
def k(ad, c):
    global ok, fail
    if c: ok += 1
    else: fail += 1; print('BAŞARISIZ:', ad)
def oku(*y):
    with open(os.path.join(K, *y), encoding='utf-8-sig') as f: return f.read()
def var(*y): return os.path.exists(os.path.join(K, *y))
if var('scripts', 'kurulum.sh'):
    s = oku('scripts', 'kurulum.sh')
    k('kurulum.sh sözdizimi geçerli', subprocess.run(['bash', '-n', os.path.join(K, 'scripts', 'kurulum.sh')]).returncode == 0)
    k('kurulum.sh: ERR+EXIT tuzağı, rapor dosyası, adım izleme, internet denetimi', all(x in s for x in ('trap ', 'EXIT', 'kurulum-hata.txt', 'adim "', 'pypi.org', 'set -Eeuo pipefail')))
    k('kurulum.sh: pip çıktısı kayda yazılır, başarıda eski rapor silinir', 'kurulum-pip.log' in s and 'rm -f "$RAPOR"' in s)
    k('kurulum.sh: yaygın nedenler için ipucu (venv, internet, derleme, disk, izin)', all(x in s for x in ('python3-venv', 'İnternet/bağlantı', 'build-essential', 'Diskte yer yok', 'İzin sorunu')))
if var('windows', 'kur.ps1'):
    s = oku('windows', 'kur.ps1'); h = oku('windows', 'hata-raporu.ps1'); b = oku('SERVIS-DEFTERI-KUR.bat')
    k('kur.ps1: hata raporu çağrılır, adım izlenir, pip çıkış kodu raporlanır', all(x in s for x in ('Hata-Raporu', 'SonAdim', 'Native-Calistir', 'pip cikis kodu')))
    k('hata-raporu.ps1: adım, konum, ipucu, bilgisayar bilgisi, internet, masaüstü kopyası', all(x in h for x in ('Hata adimi', 'PositionMessage', 'OLASI NEDEN', 'BILGISAYAR BILGISI', 'pypi.org', 'SERVIS-DEFTERI-KURULUM-HATASI.txt')))
    k('SERVIS-DEFTERI-KUR.bat: zip içinden çalıştırma uyarısı + hata sonrası yönlendirme', 'AppData\\Local\\Temp' in b and 'KURULUM TAMAMLANAMADI' in b and 'SERVIS-DEFTERI-KURULUM-HATASI.txt' in b)
    k('1-KUR.bat: pip çıktısı kayda yazılır, adım bilgisi ve rapor', all(x in oku('windows', '1-KUR.bat') for x in ('1-kur.log', 'kurulum-hata.txt', 'set "ADIM=')))
    k('otomatik-baslat.ps1: hata yakalama', 'catch' in oku('windows', 'otomatik-baslat.ps1'))
    k('Windows kurulum dosyaları ASCII (Türkçe karakter konsolda bozulmasın)', all(not re.search(r'[^\x00-\x7f]', oku('windows', d)) for d in ('kur.ps1', 'hata-raporu.ps1', 'otomatik-baslat.ps1', '1-KUR.bat')) )
if var('yazdirma_ajani', 'ajan-kur.ps1'):
    s = oku('yazdirma_ajani', 'ajan-kur.ps1')
    k('ajan-kur.ps1: kayıt (transcript), hata raporu, adım izleme', all(x in s for x in ('Start-Transcript', 'Hata-Raporu', 'SonAdim', 'Native-Calistir')))
    k('ajan: hata-raporu.ps1 var ve AJAN-KUR.bat hata sonrası yönlendirir', var('yazdirma_ajani', 'hata-raporu.ps1') and 'KURULUM TAMAMLANAMADI' in oku('yazdirma_ajani', 'AJAN-KUR.bat'))
    k('ajan: ps1/bat ASCII', all(not re.search(r'[^\x00-\x7f]', oku('yazdirma_ajani', d)) for d in ('ajan-kur.ps1', 'hata-raporu.ps1', 'AJAN-KUR.bat')))
if var('windows', 'hata-raporu.ps1'):
    h = oku('windows', 'hata-raporu.ps1')
    k('hata raporu anahtar/şifre/proxy kimliğini gizler', '_Gizle' in h and 'sifre|password' in h and '****' in h)
    k('kur.ps1: ilk şifre gösterilmeden önce kayıt (transcript) kapatılır, ilerleme çubuğu kapalı', oku('windows', 'kur.ps1').index('Stop-Transcript | Out-Null } catch {}      # asagida') < oku('windows', 'kur.ps1').index('ILK GIRIS SIFRESI') and 'ProgressPreference' in oku('windows', 'kur.ps1'))
if var('yazdirma_ajani', 'ajan-kur.ps1'):
    s = oku('yazdirma_ajani', 'ajan-kur.ps1')
    k('ajan-kur.ps1: anahtar ekranda görünmez (SecureString), aday dosya + ACL önce, başarısız denemede eski ayar korunur', '-AsSecureString' in s and 'ajan.env.yeni' in s and s.index('Acl-Kisitla $aday') < s.index('--baglanti | Out-Host; $k = $LASTEXITCODE; $ErrorActionPreference = \'Stop\'\n  Remove-Item Env:') )
    k('ajan: python.org yedeği ve AJAN_AYAR desteği', 'python-3.12.8-amd64.exe' in s and 'AJAN_AYAR' in oku('yazdirma_ajani', 'yazdirma_ajani.py'))
print(f'{ok} geçti, {fail} başarısız'); sys.exit(1 if fail else 0)
