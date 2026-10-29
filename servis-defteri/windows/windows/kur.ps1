# SERVIS-DEFTERI-KUR.bat tarafindan YONETICI olarak cagrilir. Tek seferde kurar:
#  1) dosyalari C:\ServisDefteri'ne kopyalar (USB'den calistirildiysa)  2) Python 3.12 yoksa kurar
#  3) paketleri kurar  4) bilgisayar acilinca otomatik baslatmayi ayarlar  5) yaziciyi arar, deneme etiketi basar
#  6) masaustune kisayol koyar  7) ilk sifreyi gosterir
$ErrorActionPreference = 'Stop'
# Turkce harfler konsolda bozulmasin: hem PowerShell hem Python ciktisi UTF-8
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$env:PYTHONUTF8 = '1'
$Hedef  = 'C:\ServisDefteri'
$Kaynak = Split-Path -Parent $PSScriptRoot
$ProgressPreference = 'SilentlyContinue'   # PS 5.1'de Invoke-WebRequest ilerleme cubugu indirmeyi cok yavaslatir
$script:SonAdim = 'Baslangic'
$script:SonCikti = @()
# Hata raporu yardimcisi (kurulum hatasinda kurulum-hata.txt uretir). Dosya yoksa/bozuksa asagidaki yedek tanimlar gecerli kalir, kurulum yine calisir.
$yardimci = Join-Path $PSScriptRoot 'hata-raporu.ps1'
function Native-Calistir([string]$Exe, [string[]]$Arg) { $eski = $ErrorActionPreference; $ErrorActionPreference = 'Continue'; try { $c = & $Exe @Arg 2>&1 | ForEach-Object { "$_" }; $k = $LASTEXITCODE } finally { $ErrorActionPreference = $eski }; $script:SonCikti = @($c); return $k }
function Hata-Raporu { param($Hata, [string]$Adim, [string]$LogYol, [string]$RaporKlasor, [string]$Baslik, [string]$Kaynak) }
if (Test-Path $yardimci) { try { . $yardimci } catch { Write-Host 'Uyari: hata-raporu.ps1 yuklenemedi (kurulum yine de calisir).' -ForegroundColor Yellow } }
function Adim($m) { $script:SonAdim = $m; Write-Host ''; Write-Host ('>> ' + $m) -ForegroundColor Cyan }
function Tamam($m) { Write-Host ('   OK  ' + $m) -ForegroundColor Green }
function SifreDuz($g) { $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($g); try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) } }
function Uyari($m) { Write-Host ('   !!  ' + $m) -ForegroundColor Yellow }

try {
  New-Item -ItemType Directory -Force -Path (Join-Path $Hedef 'data') | Out-Null
  try { Start-Transcript -Path (Join-Path $Hedef 'data\kurulum.log') -Append | Out-Null } catch {}
  Write-Host '=============================================' -ForegroundColor Cyan
  Write-Host '   SERVIS DEFTERI Kurulumu' -ForegroundColor Cyan
  Write-Host '=============================================' -ForegroundColor Cyan

  # ---- 1) Dosyalari yerlestir
  Adim '1/7 Dosyalar C:\ServisDefteri klasorune yerlestiriliyor'
  # Guncelleme: calisan eski surum dursun, yeni dosyalar yerlessin, sonra yeniden baslasin (veriler yerinde kalir)
  try { Stop-ScheduledTask -TaskName 'ServisDefteri' -ErrorAction SilentlyContinue } catch {}
  Start-Sleep -Seconds 2
  if ($Kaynak.TrimEnd('\') -ine $Hedef) {
    New-Item -ItemType Directory -Force -Path $Hedef | Out-Null
    # data (kayitlar), venv ve mevcut .env ASLA ezilmez: guncelleme yaparken verilerin silinmez
    robocopy $Kaynak $Hedef /E /XD data venv __pycache__ .git /XF .env /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw 'Dosyalar kopyalanamadi (robocopy hatasi).' }
    $global:LASTEXITCODE = 0
    if (-not (Test-Path (Join-Path $Hedef '.env')) -and (Test-Path (Join-Path $Kaynak '.env'))) { Copy-Item (Join-Path $Kaynak '.env') (Join-Path $Hedef '.env') }
    Tamam 'Dosyalar kopyalandi.'
  } else { Tamam 'Zaten C:\ServisDefteri icindesin.' }
  if (-not (Test-Path (Join-Path $Hedef '.env'))) { Copy-Item (Join-Path $Hedef '.env.example') (Join-Path $Hedef '.env'); Uyari '.env bulunamadi, ornek ayar dosyasi olusturuldu.' }
  New-Item -ItemType Directory -Force -Path (Join-Path $Hedef 'data') | Out-Null
  # data klasoru (kayitlar, sifre ozeti, gizli anahtar): yalnizca SYSTEM ve Yoneticiler okuyabilsin (dil bagimsiz SID'lerle)
  $null = & icacls (Join-Path $Hedef 'data') /reset /T /C 2>&1
  $null = & icacls (Join-Path $Hedef 'data') /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' 2>&1
  if ($LASTEXITCODE -eq 0) { Tamam 'data klasoru yalnizca Yonetici/SYSTEM erisimine kisitlandi.' } else { Uyari 'data klasorunun izinleri kisitlanamadi (icacls hata verdi). Bilgisayarda baska Windows kullanicilari varsa C:\ServisDefteri\data klasorunu elle kisitla.' }

  # ---- 2) Python 3.12 (3.10-3.12 kabul; daha yeni surumlerde paket uyumsuzlugu olabilir)
  Adim '2/7 Python kontrol ediliyor'
  function Python-Bul {
    $adaylar = @()
    try { $p = & py -3.12 -c 'import sys;print(sys.executable)' 2>$null; if ($LASTEXITCODE -eq 0 -and $p) { $adaylar += $p.Trim() } } catch {}
    $adaylar += @("$env:ProgramFiles\Python312\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                  "$env:ProgramFiles\Python311\python.exe", "$env:ProgramFiles\Python310\python.exe")
    foreach ($a in $adaylar) {
      if ($a -and (Test-Path $a)) {
        try { $v = & $a --version 2>&1; if ("$v" -match 'Python 3\.(10|11|12)\.') { return $a } } catch {}
      }
    }
    try { $v = & python --version 2>&1; if ("$v" -match 'Python 3\.(10|11|12)\.') { return (Get-Command python).Source } } catch {}
    return $null
  }
  $py = Python-Bul
  $pyKurduk = $false
  if (-not $py) {
    $pyKurduk = $true
    Uyari 'Python bulunamadi, kuruluyor (internet gerekir, birkac dakika surer)...'
    try { & winget install -e --id Python.Python.3.12 --scope machine --silent --accept-package-agreements --accept-source-agreements | Out-Host } catch { Uyari 'winget kullanilamadi.' }
    $py = Python-Bul
    if (-not $py) {
      Uyari 'python.org uzerinden indiriliyor...'
      $exe = Join-Path $env:TEMP 'python-3.12.8-amd64.exe'
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile $exe
      $imza = Get-AuthenticodeSignature -FilePath $exe
      if ($imza.Status -ne 'Valid' -or "$($imza.SignerCertificate.Subject)" -notmatch 'Python Software Foundation') { Remove-Item $exe -Force -ErrorAction SilentlyContinue; throw 'Indirilen Python kurulum dosyasinin dijital imzasi dogrulanamadi (indirme bozuk ya da degistirilmis olabilir). Python 3.12 u python.org adresinden elle kur.' }
      Start-Process -FilePath $exe -ArgumentList '/quiet','InstallAllUsers=1','PrependPath=1','Include_launcher=1' -Wait
      $py = Python-Bul
    }
    if (-not $py) { throw 'Python kurulamadi. https://www.python.org/downloads/ adresinden Python 3.12 kur ("Add python.exe to PATH" isaretli), sonra SERVIS-DEFTERI-KUR.bat dosyasini tekrar calistir.' }
  }
  Tamam ("Python: $py")
  # Python'u BU kurulum yuklediyse iz birak: KALDIR.bat yalnizca o durumda (ve sorarak) Python'u da kaldirir
  if ($pyKurduk) { Set-Content -Path (Join-Path $Hedef 'data\python_kuruldu.txt') -Encoding ASCII -Value ("Python bu kurulum tarafindan yuklendi: " + (Get-Date -Format s)) }

  # ---- 3) Sanal ortam + paketler
  Adim '3/7 Gerekli paketler kuruluyor (internet gerekir, birkac dakika surebilir)'
  Set-Location $Hedef
  $vpy = Join-Path $Hedef 'venv\Scripts\python.exe'
  if (-not (Test-Path $vpy)) { & $py -m venv venv; if ($LASTEXITCODE -ne 0) { throw 'Sanal ortam olusturulamadi.' } }
  $kod = Native-Calistir $vpy @('-m','pip','install','--disable-pip-version-check','--quiet','--upgrade','pip')
  if ($kod -ne 0) { Uyari 'pip guncellenemedi (onemli degil, eski surumle devam ediliyor).' }
  $kod = Native-Calistir $vpy @('-m','pip','install','--disable-pip-version-check','--quiet','-r','requirements.txt')
  if ($kod -ne 0) {
    Uyari ('Ilk deneme basarisiz (pip cikis kodu ' + $kod + '), tekrar deneniyor...')
    $script:SonCikti | Select-Object -Last 15 | ForEach-Object { Write-Host ('      ' + $_) -ForegroundColor DarkYellow }
    Start-Sleep -Seconds 3
    $kod = Native-Calistir $vpy @('-m','pip','install','--disable-pip-version-check','-r','requirements.txt')
    $script:SonCikti | ForEach-Object { Write-Host ('      ' + $_) }
    if ($kod -ne 0) { throw ('Paketler kurulamadi (pip cikis kodu ' + $kod + '). Internet baglantisini kontrol edip SERVIS-DEFTERI-KUR.bat dosyasini tekrar calistir.') }
  }
  $kod = Native-Calistir $vpy @('-c','import flask, waitress, qrcode, PIL; print(1)')
  if ($kod -ne 0) { throw 'Paket dogrulamasi basarisiz (flask/waitress/qrcode/PIL yuklenemedi).' }
  $kod = Native-Calistir $vpy @('-c','import win32print; print(1)')
  if ($kod -ne 0) { Uyari 'pywin32 (yazici modulu) yuklenemedi: etiket yazdirma calismayabilir (kurulum devam ediyor). Microsoft Visual C++ Redistributable (x64) kurulu olmayabilir.' }
  Tamam 'Paketler kuruldu ve dogrulandi.'

  # ---- Yedek var mi? (yalnizca veritabani YOKSA: format/sifirdan kurulumda eski kayitlari geri getirmeyi sorar; guncellemede dokunmaz)
  if (-not (Test-Path (Join-Path $Hedef 'data\servis.db'))) {
    Adim 'Eski yedek araniyor (bu bilgisayar, SERVISYEDEK USB bellek, Google Drive)'
    $ErrorActionPreference = 'Continue'
    $yb = (& $vpy (Join-Path $Hedef 'scripts\kurulum_yedek.py') bul 2>$null | Select-Object -Last 1)
    $ybKod = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($ybKod -eq 0 -and $yb -match '\|') {
      $pp = "$yb".Split('|')
      Write-Host ('   Bulundu: ' + $pp[0] + ' - ' + $pp[1] + '  (' + $pp[2] + ' musteri, ' + $pp[3] + ' is emri)') -ForegroundColor Yellow
      $cv = Read-Host '   Bu yedekten devam edilsin mi? Eski kayitlar geri gelir. [E = evet / H = hayir, bos yeni kurulum]'
      if ($cv -match '^[eE]') {
        $ErrorActionPreference = 'Continue'
        & $vpy (Join-Path $Hedef 'scripts\kurulum_yedek.py') yukle | Out-Host
        $yk = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        if ($yk -eq 0) { Tamam 'Yedek yuklendi: eski musteri ve is emirleri geri geldi.'; $yedekYuklendi = $true } else { Uyari 'Yedek yuklenemedi, bos veritabaniyla devam ediliyor. Sonra windows\YEDEKTEN-GERI-YUKLE.bat ile tekrar deneyebilirsin.' }
      } else { Write-Host '   Yedek kullanilmadi, bos veritabaniyla kurulacak (yedekler silinmez).' }
    } else { Write-Host '   Yedek bulunamadi (yeni kurulum). Google Drive yedegin varsa: kurulumdan sonra windows\DRIVE-YEDEK-KUR.bat, ardindan windows\YEDEKTEN-GERI-YUKLE.bat.' }
  }

  # ---- Dis sistem (muhasebe vb.) API anahtari (yoksa uretilir; mevcut anahtar ve .env'deki diger ayarlar KORUNUR)
  $envYol = Join-Path $Hedef '.env'
  $envMetin = if (Test-Path $envYol) { [IO.File]::ReadAllText($envYol) } else { '' }
  if ($envMetin -notmatch '(?m)^\s*ENTEGRASYON_API_ANAHTARI\s*=\s*\S') {
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create(); $bayt = New-Object byte[] 30; $rng.GetBytes($bayt)
    $apiAnahtar = ([Convert]::ToBase64String($bayt)).Replace('+','A').Replace('/','B').Replace('=','')
    $yeniSatir = "`r`n# Dis sistem API entegrasyonu (docs\ENTEGRASYON-API.md). Bu anahtari yalnizca entegrasyonu kuracak firmaya ver.`r`nENTEGRASYON_API_ANAHTARI=$apiAnahtar`r`n"
    [IO.File]::AppendAllText($envYol, $yeniSatir, (New-Object Text.UTF8Encoding($false)))
    Set-Content -Path (Join-Path $Hedef 'data\ENTEGRASYON-ANAHTARI.txt') -Encoding ASCII -Value @("API anahtari (gizli tut, yalnizca entegrasyonu kuracak firmaya ver):", $apiAnahtar, "Adres: (sitenin alan adi)/api/v1/is-emirleri", "Belge: C:\ServisDefteri\docs\Servis-Defteri-Entegrasyon-API.pdf")
    $apiYeni = $true
  }

  # ---- Panel sifresi (yalnizca ilk kurulumda sorulur; guncellemede mevcut sifre korunur)
  $hashDosya = Join-Path $Hedef 'data\.password_hash'
  if (-not (Test-Path $hashDosya)) {
    Adim 'Panel giris sifresi belirle'
    Write-Host '   En az 10 karakter. Dogru girene kadar tekrar sorulur. Bos birakip Enter''a basarsan rastgele bir sifre uretilir ve kurulum sonunda ekranda gosterilir.'
    while ($true) {
      $sec = Read-Host '   Sifre' -AsSecureString
      $duz = SifreDuz $sec
      if (-not $duz) { Uyari 'Bos birakildi: rastgele sifre uretilecek (sonra windows\SIFRE-DEGISTIR.bat ile degistirebilirsin).'; break }
      if ($duz.Length -lt 10) { Uyari 'Sifre en az 10 karakter olmali. Tekrar dene.'; continue }
      $sec2 = Read-Host '   Sifre (tekrar)' -AsSecureString
      $duz2 = SifreDuz $sec2
      if ($duz -ne $duz2) { Uyari 'Sifreler uyusmadi. Bastan tekrar dene.'; continue }
      $env:SERVIS_SIFRE = $duz
      & $vpy (Join-Path $Hedef 'scripts\sifre_ayarla.py') | Out-Host
      $sifreKod = $LASTEXITCODE
      Remove-Item Env:\SERVIS_SIFRE -ErrorAction SilentlyContinue
      if ($sifreKod -eq 0) { $sifreBelirlendi = $true; break }
      Uyari 'Sifre kaydedilemedi. Tekrar dene (bos birakirsan rastgele sifre uretilir).'
    }
  }

  # ---- 4) Otomatik baslatma
  Adim '4/7 Bilgisayar acilinca otomatik baslatma ayarlaniyor'
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Hedef 'windows\otomatik-baslat.ps1') -Kok $Hedef
  if ($LASTEXITCODE -ne 0) { throw 'Otomatik baslatma gorevi olusturulamadi.' }
  Tamam 'Sistem bilgisayar her acildiginda kendiliginden baslayacak, gece 02:00 yedek alinacak.'

  # ---- 5) Uygulama ayakta mi
  Adim '5/7 Uygulamanin acilmasi bekleniyor'
  $calisiyor = $false
  for ($i = 0; $i -lt 45; $i++) {
    try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5000/saglik' -TimeoutSec 3; if ($r.StatusCode -eq 200) { $calisiyor = $true; break } } catch {}
    Start-Sleep -Seconds 1
  }
  if ($calisiyor) {
    Tamam 'Uygulama calisiyor: http://localhost:5000'
    $tablo = & $vpy -c "import sqlite3; c=sqlite3.connect('data/servis.db'); print(c.execute('select count(*) from sqlite_master').fetchone()[0])" 2>&1
    if ($LASTEXITCODE -eq 0 -and [int]$tablo -gt 0) { Tamam ('Veritabani baglantisi dogrulandi (' + $tablo + ' tablo/indeks).') } else { Uyari 'Veritabani dogrulanamadi: data\servis.db' }
  } else { Uyari 'Uygulama 45 saniyede acilmadi. data\sunucu.log dosyasina bak veya bilgisayari yeniden baslat.' }

  # ---- 6) Etiket yazicisi
  Adim '6/7 Etiket yazicisi araniyor'
  $env:PYTHONUTF8 = '1'
  $ErrorActionPreference = 'Continue'   # yazici betikleri stderr'e yazsa bile kurulum durmasin
  $liste = (& $vpy (Join-Path $Hedef 'scripts\yazicilari_listele.py') 2>&1 | ForEach-Object { "$_" }) -join "`n"
  Write-Host $liste
  if ($liste -match 'gidecek') {
    Tamam 'Etiket yazicisi bulundu. Deneme etiketi basiliyor...'
    $deneme = (& $vpy (Join-Path $Hedef 'scripts\etiket_deneme.py') 2>&1 | ForEach-Object { "$_" }) -join "`n"
    Write-Host $deneme
    if ($LASTEXITCODE -ne 0) { Uyari 'Deneme etiketi basilamadi (kurulum bundan etkilenmez). Yaziciyi ac, USB kablosunu tak, sonra windows\ETIKET-DENEME.bat dosyasini calistir.'; $global:LASTEXITCODE = 0 }
  } else {
    Uyari 'Etiket yazicisi bulunamadi. XP-470B USB ile takili, acik ve surucusu kurulu mu? Sonra windows\ETIKET-DENEME.bat dosyasini calistir. Adi farkliysa .env icine ETIKET_YAZICI_ADI=... yaz.'
  }

  $ErrorActionPreference = 'Stop'
  # ---- 7) Masaustu kisayolu + ilk sifre
  Adim '7/7 Masaustu kisayolu olusturuluyor'
  try {
    $masa = [Environment]::GetFolderPath('CommonDesktopDirectory')
    $ikon = Join-Path $Hedef 'static\favicon.ico'
    Set-Content -Path (Join-Path $masa 'Servis Defteri.url') -Encoding ASCII -Value @('[InternetShortcut]','URL=http://localhost:5000/login',"IconFile=$ikon",'IconIndex=0')
    $ws = New-Object -ComObject WScript.Shell
    $lnk = $ws.CreateShortcut((Join-Path $masa 'Servis Defteri - Yeniden Baslat.lnk'))
    $lnk.TargetPath = Join-Path $Hedef 'windows\YENIDEN-BASLAT.bat'; $lnk.WorkingDirectory = $Hedef; $lnk.Description = 'Servis Defteri sistemini yeniden baslatir'; $lnk.Save()
    Tamam 'Masaustune "Servis Defteri" ve "Servis Defteri - Yeniden Baslat" kisayollari konuldu.'
  } catch { Uyari 'Kisayol olusturulamadi (onemli degil): tarayicida http://localhost:5000/login adresini ac.' }

  Write-Host ''
  Write-Host '=============================================' -ForegroundColor Green
  Write-Host '   KURULUM TAMAMLANDI' -ForegroundColor Green
  Write-Host '=============================================' -ForegroundColor Green
  Write-Host ' Panel : http://localhost:5000/login   (masaustundeki "Servis Defteri" kisayolu)'
  Write-Host ' Site  : http://localhost:5000'
  if ($yedekYuklendi) { Write-Host ' Eski yedek yuklendi: musteri ve is emri kayitlarin geri geldi (sifre yedekle gelmez, yukarida belirledigin sifreyi kullan).' -ForegroundColor Green }
  if ($apiYeni) { Write-Host ' API anahtari olusturuldu: C:\ServisDefteri\data\ENTEGRASYON-ANAHTARI.txt (entegrasyon kullanilmayacaksa onemli degil; anahtari yalnizca guvenli bir kanaldan ver).' -ForegroundColor Yellow }
  Write-Host ' Domain baglamak icin (alanadiniz.com): C:\ServisDefteri\DOMAIN-BAGLAMA.txt dosyasini ac.'
  try { Stop-Transcript | Out-Null } catch {}      # asagida gosterilen ilk sifre kurulum kaydina (log) yazilmasin
  $sf = Join-Path $Hedef 'data\ILK_SIFRE.txt'
  if ((Test-Path $sf) -and -not $sifreBelirlendi) {
    Write-Host ''
    Write-Host ' ILK GIRIS SIFRESI (girince hemen degistir: windows\SIFRE-DEGISTIR.bat):' -ForegroundColor Yellow
    Get-Content $sf | ForEach-Object { Write-Host ('   ' + $_) -ForegroundColor Yellow }
  }
  Write-Host ''
  Write-Host ' Bilgisayari kapatip acinca sistem kendiliginden baslar; baska bir sey yapmana gerek yok.'
  if ($sifreBelirlendi) { Write-Host ' Giris sifresi: kurulumda belirledigin sifre.' -ForegroundColor Yellow }
  Write-Host ' Kurulum kaydi: C:\ServisDefteri\data\kurulum.log'
  Write-Host ' Sistemi yeniden baslatmak gerekirse: masaustundeki "Servis Defteri - Yeniden Baslat" kisayolu.'
  Write-Host ' Not: bilgisayarin uykuya gecmemesi icin Ayarlar > Sistem > Guc > Uyku: "Hicbir zaman" sec.'
  try { Stop-Transcript | Out-Null } catch {}
  exit 0
}
catch {
  $hataKaydi = $_
  Write-Host ''
  Write-Host ('HATA: ' + $hataKaydi.Exception.Message) -ForegroundColor Red
  Write-Host ('Hatanin oldugu adim: ' + $script:SonAdim) -ForegroundColor Red
  try { Stop-Transcript | Out-Null } catch {}
  $rk = Join-Path $Hedef 'data'
  $null = Hata-Raporu -Hata $hataKaydi -Adim $script:SonAdim -LogYol (Join-Path $Hedef 'data\kurulum.log') -RaporKlasor $rk -Baslik 'Servis Defteri (Windows) kurulum hatasi' -Kaynak $Kaynak
  exit 1
}
