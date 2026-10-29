# AJAN-KUR.bat tarafindan YONETICI olarak cagrilir. Dukkan bilgisayarina "yazdirma ajani"ni kurar:
#  1) dosyalari C:\ServisAjan'a kopyalar  2) Python 3.10-3.12 yoksa kurar  3) paketleri kurar
#  4) sunucu adresi + ajan anahtari sorar ve dener  5) yaziciyi kontrol eder  6) bilgisayar acilinca otomatik baslatir
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$env:PYTHONUTF8 = '1'
$Hedef  = 'C:\ServisAjan'
$Kaynak = $PSScriptRoot
$ProgressPreference = 'SilentlyContinue'
$script:SonAdim = 'Baslangic'
$script:SonCikti = @()
$yardimci = Join-Path $PSScriptRoot 'hata-raporu.ps1'
function Native-Calistir([string]$Exe, [string[]]$Arg) { $eski = $ErrorActionPreference; $ErrorActionPreference = 'Continue'; try { $c = & $Exe @Arg 2>&1 | ForEach-Object { "$_" }; $k = $LASTEXITCODE } finally { $ErrorActionPreference = $eski }; $script:SonCikti = @($c); return $k }
function Hata-Raporu { param($Hata, [string]$Adim, [string]$LogYol, [string]$RaporKlasor, [string]$Baslik, [string]$Kaynak) }
if (Test-Path $yardimci) { try { . $yardimci } catch { Write-Host 'Uyari: hata-raporu.ps1 yuklenemedi (kurulum yine de calisir).' -ForegroundColor Yellow } }
function Adim($m) { $script:SonAdim = $m; Write-Host ''; Write-Host ('>> ' + $m) -ForegroundColor Cyan }
function Tamam($m) { Write-Host ('   OK  ' + $m) -ForegroundColor Green }
function Uyari($m) { Write-Host ('   !!  ' + $m) -ForegroundColor Yellow }

New-Item -ItemType Directory -Force -Path $Hedef | Out-Null
try { Start-Transcript -Path (Join-Path $Hedef 'kurulum.log') -Append | Out-Null } catch {}
try {
Write-Host '=============================================' -ForegroundColor Cyan
Write-Host '   SERVIS DEFTERI - Yazdirma Ajani Kurulumu' -ForegroundColor Cyan
Write-Host '=============================================' -ForegroundColor Cyan
Write-Host 'Bu bilgisayardaki etiket yazicisini bulut sunucusuna baglar. Ayarlar icin yoneticiden'
Write-Host 'sunucu adresini ve "ajan anahtari"ni almis olmalisin.'

Adim '1/6 Dosyalar C:\ServisAjan klasorune yerlestiriliyor'
try { Stop-ScheduledTask -TaskName 'ServisAjan' -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Seconds 2
New-Item -ItemType Directory -Force -Path $Hedef | Out-Null
if ($Kaynak.TrimEnd('\') -ine $Hedef) {
  robocopy $Kaynak $Hedef /E /XD venv __pycache__ /XF ajan.env ajan.log /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) { throw 'Dosyalar kopyalanamadi (robocopy hatasi).' }
  $global:LASTEXITCODE = 0
}
Tamam 'Dosyalar hazir.'

Adim '2/6 Python kontrol ediliyor'
function Python-Bul {
  $adaylar = @()
  foreach ($s in '3.12','3.11','3.10') { try { $p = & py "-$s" -c 'import sys;print(sys.executable)' 2>$null; if ($LASTEXITCODE -eq 0 -and $p) { $adaylar += $p.Trim() } } catch {} }
  $adaylar += @("$env:ProgramFiles\Python312\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe", "$env:ProgramFiles\Python311\python.exe", "$env:ProgramFiles\Python310\python.exe")
  foreach ($a in $adaylar) {
    if ($a -and (Test-Path $a)) { try { $v = & $a --version 2>&1; if ("$v" -match 'Python 3\.(10|11|12)\.') { return $a } } catch {} }
  }
  try { $v = & python --version 2>&1; if ("$v" -match 'Python 3\.(10|11|12)\.') { return (Get-Command python).Source } } catch {}
  return $null
}
$py = Python-Bul
if (-not $py) {
  Uyari 'Python bulunamadi, kuruluyor (internet gerekir, birkac dakika surer)...'
  try { & winget install -e --id Python.Python.3.12 --scope machine --silent --accept-package-agreements --accept-source-agreements | Out-Host } catch { Uyari 'winget kullanilamadi.' }
  $py = Python-Bul
  if (-not $py) {
    Uyari 'python.org uzerinden indiriliyor...'
    $exe = Join-Path $env:TEMP 'python-3.12.8-amd64.exe'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile $exe
    $imza = Get-AuthenticodeSignature -FilePath $exe
    if ($imza.Status -ne 'Valid' -or "$($imza.SignerCertificate.Subject)" -notmatch 'Python Software Foundation') { Remove-Item $exe -Force -ErrorAction SilentlyContinue; throw 'Indirilen Python kurulum dosyasinin dijital imzasi dogrulanamadi. Python 3.12 yi python.org adresinden elle kur.' }
    Start-Process -FilePath $exe -ArgumentList '/quiet','InstallAllUsers=1','PrependPath=1','Include_launcher=1' -Wait
    $py = Python-Bul
  }
  if (-not $py) { throw 'Python kurulamadi. https://www.python.org/downloads/ adresinden Python 3.12 kur ("Add python.exe to PATH" isaretli), sonra AJAN-KUR.bat dosyasini tekrar calistir.' }
}
Tamam ("Python: $py")

Adim '3/6 Gerekli paketler kuruluyor (internet gerekir)'
Set-Location $Hedef
$vpy = Join-Path $Hedef 'venv\Scripts\python.exe'
if (-not (Test-Path $vpy)) { & $py -m venv venv; if ($LASTEXITCODE -ne 0) { throw 'Sanal ortam olusturulamadi.' } }
$kod = Native-Calistir $vpy @('-m','pip','install','--disable-pip-version-check','--quiet','--upgrade','pip')
if ($kod -ne 0) { Uyari 'pip guncellenemedi (onemli degil).' }
$kod = Native-Calistir $vpy @('-m','pip','install','--disable-pip-version-check','-r','requirements.txt')
$script:SonCikti | Select-Object -Last 8 | ForEach-Object { Write-Host ('      ' + $_) -ForegroundColor DarkGray }
if ($kod -ne 0) { throw ('Paketler kurulamadi (pip cikis kodu ' + $kod + '). Internet baglantisini kontrol edip AJAN-KUR.bat dosyasini tekrar calistir.') }
$kod = Native-Calistir $vpy @('-c','import win32print, usb; print(1)')
if ($kod -ne 0) { throw 'Paket dogrulamasi basarisiz (pywin32 yuklenemedi; Visual C++ Redistributable x64 gerekebilir).' }
Tamam 'Paketler kuruldu.'

Adim '4/6 Sunucu baglantisi'
$ayarYol = Join-Path $Hedef 'ajan.env'
$basarili = $false
$mevcut = Test-Path $ayarYol
if ($mevcut) {
  $c = Read-Host '   Onceki ayar bulundu. Korunsun mu? [E = evet (onerilir) / H = hayir, yeniden gir]'
  if ($c -match '^[eE]') {
    $ErrorActionPreference = 'Continue'; & $vpy (Join-Path $Hedef 'yazdirma_ajani.py') --baglanti | Out-Host; $k = $LASTEXITCODE; $ErrorActionPreference = 'Stop'
    if ($k -eq 0) { $basarili = $true } else { Uyari 'Onceki ayarla baglanilamadi, yeniden girelim.' }
  }
}
function Acl-Kisitla([string]$Yol) { $null = & icacls $Yol /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' 2>&1 }
function SifreDuz($g) { $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($g); try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) } }
$aday = Join-Path $Hedef 'ajan.env.yeni'
$deneme = 0
while (-not $basarili -and $deneme -lt 3) {
  $deneme++
  $sunucu = (Read-Host '   Sunucu adresi (ornek: https://servis.ornek.com)').Trim().TrimEnd('/')
  # Anahtar ekranda gorunmez ve kurulum kaydina (transcript) yazilmaz: yapistir + Enter
  $anahtar = (SifreDuz (Read-Host '   Ajan anahtari (ya_ ile baslar; yazarken/yapistirirken ekranda gorunmez) - yapistir ve Enter' -AsSecureString)).Trim()
  $satirlar = @('# Servis Defteri yazdirma ajani ayarlari. Anahtari kimseyle paylasma.', "SUNUCU=$sunucu", "ANAHTAR=$anahtar", '# Yazici adi bulunamazsa asagidaki satirin basindaki # isaretini kaldirip yazici adinin bir parcasini yaz:', '#ETIKET_YAZICI_ADI=XP-470')
  [IO.File]::WriteAllLines($aday, $satirlar, (New-Object Text.UTF8Encoding($false)))
  Acl-Kisitla $aday                      # yazilir yazilmaz kisitla (deneme basarisiz olsa da dosya herkese acik kalmasin)
  $env:AJAN_AYAR = $aday
  $ErrorActionPreference = 'Continue'; & $vpy (Join-Path $Hedef 'yazdirma_ajani.py') --baglanti | Out-Host; $k = $LASTEXITCODE; $ErrorActionPreference = 'Stop'
  Remove-Item Env:\AJAN_AYAR -ErrorAction SilentlyContinue
  if ($k -eq 0) { Move-Item -Force $aday $ayarYol; $basarili = $true } else { Remove-Item $aday -Force -ErrorAction SilentlyContinue; Uyari 'Baglanti kurulamadi (onceki ayar varsa korundu). Adresi ve anahtari kontrol edip tekrar dene.' }
}
if (-not $basarili) { throw 'Sunucuya baglanilamadi. Adresi ve ajan anahtarini yoneticiden tekrar iste.' }
Acl-Kisitla $ayarYol                     # ayar dosyasi (anahtar icerir): yalnizca SYSTEM ve Yoneticiler okuyabilsin
Acl-Kisitla (Join-Path $Hedef 'kurulum.log')
Tamam 'Sunucu baglantisi tamam.'

Adim '5/6 Yazici kontrol ediliyor'
$ErrorActionPreference = 'Continue'; & $vpy (Join-Path $Hedef 'yazdirma_ajani.py') --durum | Out-Host; $yd = $LASTEXITCODE; $ErrorActionPreference = 'Stop'
if ($yd -ne 0) { Uyari 'Etiket yazicisi bulunamadi. Yazici surucusunu kur, USB kablosunu tak. Adi farkliysa C:\ServisAjan\ajan.env icindeki ETIKET_YAZICI_ADI satirini ac. Sonra AJAN-DENEME.bat ile dene.' }
else {
  $c = Read-Host '   Yazicidan deneme etiketi cikarilsin mi? [E/H]'
  if ($c -match '^[eE]') { $ErrorActionPreference = 'Continue'; & $vpy (Join-Path $Hedef 'yazdirma_ajani.py') --deneme | Out-Host; $ErrorActionPreference = 'Stop' }
}

Adim '6/6 Bilgisayar acilinca otomatik baslatma'
$pyw = Join-Path $Hedef 'venv\Scripts\pythonw.exe'
$sistem = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$ayar = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
$eylem = New-ScheduledTaskAction -Execute $pyw -Argument ('"' + (Join-Path $Hedef 'yazdirma_ajani.py') + '"') -WorkingDirectory $Hedef
Register-ScheduledTask -TaskName 'ServisAjan' -Action $eylem -Trigger (New-ScheduledTaskTrigger -AtStartup) -Principal $sistem -Settings $ayar -Force | Out-Null
Start-ScheduledTask -TaskName 'ServisAjan'
Tamam 'Ajan calisiyor ve bilgisayar her acildiginda kendiliginden baslayacak.'
Write-Host ''
Write-Host 'Bitti. Telefondan arac etiket ekraninda "Dukkan bilgisayarindan bas" dugmesini dene.' -ForegroundColor Green
Write-Host 'Sorun olursa AJAN-DENEME.bat dosyasini calistir.'
  try { Stop-Transcript | Out-Null } catch {}
  exit 0
}
catch {
  $hataKaydi = $_
  Write-Host ''
  Write-Host ('HATA: ' + $hataKaydi.Exception.Message) -ForegroundColor Red
  Write-Host ('Hatanin oldugu adim: ' + $script:SonAdim) -ForegroundColor Red
  try { Stop-Transcript | Out-Null } catch {}
  $null = Hata-Raporu -Hata $hataKaydi -Adim $script:SonAdim -LogYol (Join-Path $Hedef 'kurulum.log') -RaporKlasor $Hedef -Baslik 'Servis Defteri yazdirma ajani kurulum hatasi' -Kaynak $Kaynak
  exit 1
}
