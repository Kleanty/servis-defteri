# DRIVE-YEDEK-KUR.bat tarafindan YONETICI olarak cagrilir. Yedekleri Google Drive'a gondermek icin rclone'u kurar ve Google hesabina BIR KEZ izin aldirir.
# Yedekler Drive'da "ServisDefteriYedek" klasorune gider. Izin yalnizca bu programin actigi dosyalarla sinirlidir (drive.file): Drive'daki diger dosyalara erisemez.
$ErrorActionPreference = 'Continue'
$Kok = 'C:\ServisDefteri'
$Klasor = Join-Path $Kok 'data\rclone'
$Exe = Join-Path $Klasor 'rclone.exe'
$Conf = Join-Path $Klasor 'rclone.conf'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
function Adim($m) { Write-Host ''; Write-Host ('>> ' + $m) -ForegroundColor Cyan }
function Tamam($m) { Write-Host ('   OK  ' + $m) -ForegroundColor Green }
function Hata($m) { Write-Host ('   XX  ' + $m) -ForegroundColor Red }
function Dur { Read-Host 'Kapatmak icin Enter' | Out-Null }
# rclone'u calistirir; cikis kodunu dondurur. Program hic calismazsa (erisim engellendi vb.) 99 doner (eski surumde bu hata fark edilmiyordu).
function Rc {
  $global:LASTEXITCODE = 99
  try { $null = & $Exe @args 2>&1 } catch { return 99 }
  return $LASTEXITCODE
}
function Izin-Sifirla($yol) {
  # Onceki denemeden kalan bozuk izinleri onarir: sahipligi yoneticiye al, izinleri ust klasorden devralacak sekilde sifirla
  $null = & takeown /f $yol /r /d y 2>&1
  $null = & icacls $yol /reset /T /C 2>&1
}

Write-Host '=============================================' -ForegroundColor Cyan
Write-Host '   SERVIS DEFTERI - Google Drive yedegi kurulumu' -ForegroundColor Cyan
Write-Host '=============================================' -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $Kok 'scripts\yedek.py'))) { Hata 'Once SERVIS-DEFTERI-KUR.bat ile kurulum yapilmali (C:\ServisDefteri yok).'; Dur; exit 1 }
New-Item -ItemType Directory -Force -Path $Klasor | Out-Null
Izin-Sifirla $Klasor

# ---- 1) rclone
Adim '1/4 rclone (Google Drive aktarim programi) hazirlaniyor'
if (-not (Test-Path $Exe)) {
  $bulundu = $null
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host '   winget ile kuruluyor (birkac dakika surebilir)...'
    try { $null = & winget install --id Rclone.Rclone -e --silent --accept-package-agreements --accept-source-agreements 2>&1 } catch {}
    $yollar = @(Get-ChildItem (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages') -Recurse -Filter rclone.exe -ErrorAction SilentlyContinue) +
              @(Get-ChildItem 'C:\Program Files\WinGet\Packages' -Recurse -Filter rclone.exe -ErrorAction SilentlyContinue) +
              @(Get-ChildItem 'C:\Windows\System32\config\systemprofile\AppData\Local\Microsoft\WinGet\Packages' -Recurse -Filter rclone.exe -ErrorAction SilentlyContinue)
    if ($yollar.Count -gt 0) { $bulundu = $yollar[0].FullName }
    if (-not $bulundu) { $k = Get-Command rclone.exe -ErrorAction SilentlyContinue; if ($k) { $bulundu = $k.Source } }
  }
  if (-not $bulundu) {
    Write-Host '   winget yok/calismadi: dogrudan indiriliyor...'
    $zip = Join-Path $env:TEMP 'rclone.zip'; $dizin = Join-Path $env:TEMP 'rclone-ac'
    try {
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      Invoke-WebRequest 'https://downloads.rclone.org/rclone-current-windows-amd64.zip' -OutFile $zip -UseBasicParsing
      $sum = (Invoke-WebRequest 'https://downloads.rclone.org/SHA256SUMS' -UseBasicParsing).Content
      if ($sum -is [byte[]]) { $sum = [Text.Encoding]::UTF8.GetString($sum) }   # sunucu dosyayi ikili olarak gonderirse metne cevir
      $hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
      if ($sum -notmatch $hash) { throw 'Indirilen dosyanin SHA256 degeri rclone sitesindeki listeyle uyusmuyor.' }
      if (Test-Path $dizin) { Remove-Item $dizin -Recurse -Force }
      Expand-Archive $zip -DestinationPath $dizin -Force
      $bulundu = (Get-ChildItem $dizin -Recurse -Filter rclone.exe | Select-Object -First 1).FullName
    } catch { Hata ('rclone indirilemedi: ' + $_.Exception.Message); Dur; exit 1 }
  }
  if (-not $bulundu) { Hata 'rclone bulunamadi.'; Dur; exit 1 }
  Copy-Item $bulundu $Exe -Force
}
if ((Rc version) -ne 0) {
  Hata 'rclone.exe calistirilamadi (Erisim engellendi). Buyuk olasilikla Windows Guvenligi/antivirus engelliyor:'
  Write-Host '   Windows Guvenligi > Virus ve tehdit korumasi > Koruma gecmisi: rclone icin "Cihazda izin ver" de,'
  Write-Host '   ardindan Ayarlari yonet > Dislamalar''a C:\ServisDefteri klasorunu ekleyip bu dosyayi yeniden calistir.'
  Dur; exit 1
}
Tamam ('rclone hazir: ' + (& $Exe version 2>&1 | Select-Object -First 1))

# ---- 2) Google izni
Adim '2/4 Google hesabi baglaniyor'
function ConfVar($desen) { try { return ((Test-Path $Conf) -and ((Get-Content $Conf -Raw -ErrorAction Stop) -match $desen)) } catch { return $false } }
$varMi = ConfVar '\[servisdrive\]'
if ($varMi) {
  $c = Read-Host '   Daha once baglanmis. Yeniden baglansin mi? (e/H)'
  if ($c -match '^[eE]') { $null = Rc config delete servisdrive --config $Conf; $varMi = $false }
}
if (-not $varMi) {
  Write-Host '   Birazdan tarayici acilacak. Yedegin gidecegi Google hesabiyla giris yap ve "Izin ver / Allow" de.'
  Write-Host '   (Tarayici acilmazsa bu pencerede yazan baglantiyi elle ac.)'
  $kimlik = Read-Host '   Kendi Google API istemci kimligin (client id) varsa yaz; yoksa Enter (rclone ortak kimligi kullanilir)'
  if ($kimlik.Trim()) {
    $sir = Read-Host '   Istemci sirri (client secret)'
    & $Exe config create servisdrive drive scope=drive.file client_id=$($kimlik.Trim()) client_secret=$($sir.Trim()) --config $Conf | Out-Null
  } else {
    & $Exe config create servisdrive drive scope=drive.file --config $Conf | Out-Null
  }
  if (-not (ConfVar 'token')) { Hata 'Google izni alinamadi. Tekrar dene.'; Dur; exit 1 }
}
# ---- 3) Deneme dosyasi
Adim '3/4 Deneme dosyasi Drive''a yuklenip siliniyor'
$deneme = Join-Path $env:TEMP 'servis-drive-deneme.txt'
Set-Content $deneme ('Servis Defteri Drive yedek denemesi ' + (Get-Date -Format s))
$kod = Rc copyto $deneme 'servisdrive:ServisDefteriYedek/deneme.txt' --config $Conf
if ($kod -ne 0) { Hata ('Yukleme basarisiz (kod ' + $kod + '). Internet baglantisini ve Google iznini kontrol edip yeniden dene.'); Dur; exit 1 }
$null = Rc deletefile 'servisdrive:ServisDefteriYedek/deneme.txt' --config $Conf
Remove-Item $deneme -Force -ErrorAction SilentlyContinue
Tamam 'Deneme dosyasi Drive''a yuklendi ve silindi: baglanti calisiyor.'

# ---- 4) Ilk yedek
Adim '4/4 Ilk yedek aliniyor ve Drive''a gonderiliyor'
$py = Join-Path $Kok 'venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
Remove-Item (Join-Path $Kok 'data\bulut_son.txt') -Force -ErrorAction SilentlyContinue   # eski kayit basari sanilmasin
& $py (Join-Path $Kok 'scripts\yedek.py')
if (Test-Path (Join-Path $Kok 'data\bulut_son.txt')) { Tamam 'Ilk yedek Drive''da (Drive > ServisDefteriYedek).' } else {
  Hata 'Yedek Drive''a gitmedi. Son kayitlar (C:\ServisDefteri\data\yedek.log):'
  try { Get-Content (Join-Path $Kok 'data\yedek.log') -Tail 8 -ErrorAction Stop | ForEach-Object { Write-Host ('     ' + $_) } } catch { Write-Host '     (kayit dosyasi yok: yedek hic denenmemis olabilir)' }
  Dur; exit 1
}
# Google erisim anahtari rclone.conf icinde: klasoru yalnizca SYSTEM ve Yoneticiler okuyabilsin (dil bagimsiz SID; yalniz klasore uygulanir, icindekiler devralir)
$null = & icacls $Klasor /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' 2>&1
if ($LASTEXITCODE -eq 0 -and (Rc version) -eq 0) { Tamam 'Anahtar klasoru korumaya alindi (yalnizca Yonetici/SYSTEM) ve rclone hala calisiyor.' }
else {
  Izin-Sifirla $Klasor
  Hata 'Klasor izinleri kisitlanamadi; izinler eski haline getirildi (yedek yine de calisir). Bilgisayari baskalari kullaniyorsa C:\ServisDefteri\data\rclone klasorunu elle kisitla.'
}
Write-Host ''
Write-Host 'Bitti. Bundan sonra her gece 02:00''de ve en gec 6 saatte bir yedekler Drive''a otomatik gider (internet yoksa sonra yeniden dener).' -ForegroundColor Green
Dur
