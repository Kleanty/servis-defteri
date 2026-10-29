# KALDIR.bat tarafindan YONETICI olarak cagrilir. SERVIS-DEFTERI-KUR.bat'in yaptiklarinin tersini yapar:
#  1) otomatik baslatma + otomatik yedek gorevlerini ve calisan uygulamayi durdurup siler
#  2) masaustu kisayollarini siler   3) kayitlarin (data) ne olacagini SORAR   4) C:\ServisDefteri klasorunu siler
#  5) Python'u yalnizca kurulum yuklediyse ve sen "e" dersen kaldirir.  Cloudflare, yazici surucusu, dis yedek klasoru: DOKUNULMAZ.
# Otomatik kullanim (soru sormaz):  -Evet [-VeriSil | -VeriSakla | -ProgramiSakla] [-PythonSil]
param([switch]$Evet, [switch]$VeriSil, [switch]$VeriSakla, [switch]$ProgramiSakla, [switch]$PythonSil)
$ErrorActionPreference = 'Continue'
$Hedef = 'C:\ServisDefteri'
$Log = Join-Path $env:TEMP 'servis-defteri-kaldir.log'
function Adim($m) { Write-Host ''; Write-Host ('>> ' + $m) -ForegroundColor Cyan }
function Tamam($m) { Write-Host ('   OK  ' + $m) -ForegroundColor Green }
function Uyari($m) { Write-Host ('   !!  ' + $m) -ForegroundColor Yellow }
function Dur($m) { try { Stop-Transcript | Out-Null } catch {}; if (-not $Evet) { Read-Host $m | Out-Null } }

try { Start-Transcript -Path $Log -Append | Out-Null } catch {}
Set-Location $env:TEMP
Write-Host '=============================================' -ForegroundColor Cyan
Write-Host '   SERVIS DEFTERI KALDIRMA' -ForegroundColor Cyan
Write-Host '=============================================' -ForegroundColor Cyan
Write-Host ' Bu islem su kadarini yapar:'
Write-Host '   - "ServisDefteri" ve "ServisDefteri-Yedek" Windows gorevlerini siler, calisan uygulamayi durdurur'
Write-Host '   - masaustundeki "Servis Defteri" kisayollarini siler'
Write-Host ('   - ' + $Hedef + ' klasorunu siler (kayitlarin ne olacagini birazdan sorarim)')
Write-Host ' Dokunmaz: Cloudflare tuneli, yazici surucusu, .env icindeki dis yedek klasoru.'
if (-not $Evet) {
  $c = Read-Host ' Devam etmek icin E yaz (vazgecmek icin sadece Enter)'
  if ($c -notmatch '^[eE]') { Write-Host ' Vazgecildi, hicbir sey degismedi.'; Dur 'Kapatmak icin Enter'; exit 0 }
}

# Silmeden ONCE okunacak bilgiler
$dataKlasor = Join-Path $Hedef 'data'
$pyBizKurduk = Test-Path (Join-Path $dataKlasor 'python_kuruldu.txt')
$disYedek = ''
$envDosya = Join-Path $Hedef '.env'
if (Test-Path $envDosya) {
  try { $m = Select-String -Path $envDosya -Pattern '^\s*YEDEK_KLASORU\s*=\s*(.+?)\s*$' | Select-Object -First 1; if ($m) { $disYedek = $m.Matches[0].Groups[1].Value.Trim('"', "'") } } catch {}
}

# ---- 1) Gorevler ve calisan uygulama
Adim '1/5 Otomatik baslatma ve yedek gorevleri kaldiriliyor'
foreach ($ad in 'ServisDefteri', 'ServisDefteri-Yedek', 'ServisDefteri-YedekKontrol') {
  $g = Get-ScheduledTask -TaskName $ad -ErrorAction SilentlyContinue
  if ($g) {
    try { Stop-ScheduledTask -TaskName $ad -ErrorAction SilentlyContinue } catch {}
    try { Unregister-ScheduledTask -TaskName $ad -Confirm:$false -ErrorAction Stop; Tamam ($ad + ' gorevi silindi.') } catch { Uyari ($ad + ' gorevi silinemedi: ' + $_.Exception.Message) }
  } else { Tamam ($ad + ' gorevi zaten yok.') }
}
function Surecleri-Kapat {
  $liste = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($Hedef + '\', [StringComparison]::OrdinalIgnoreCase)) -or ($_.CommandLine -and $_.CommandLine.IndexOf($Hedef + '\', [StringComparison]::OrdinalIgnoreCase) -ge 0 -and $_.Name -match '^pythonw?\.exe$') }
  foreach ($p in $liste) { try { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }
  return @($liste).Count
}
$n = Surecleri-Kapat
Start-Sleep -Seconds 2
if ($n -gt 0) { Tamam ("Calisan uygulama durduruldu (" + $n + " surec).") } else { Tamam 'Calisan uygulama yok.' }

# ---- 2) Kisayollar
Adim '2/5 Masaustu kisayollari siliniyor'
$silinenKisayol = 0
foreach ($masa in @([Environment]::GetFolderPath('CommonDesktopDirectory'), [Environment]::GetFolderPath('Desktop'))) {
  foreach ($ad in 'Servis Defteri.url', 'Servis Defteri - Yeniden Baslat.lnk') {
    $y = Join-Path $masa $ad
    if ($masa -and (Test-Path $y)) { try { Remove-Item $y -Force -ErrorAction Stop; $silinenKisayol++ } catch { Uyari ($y + ' silinemedi.') } }
  }
}
Tamam ($silinenKisayol.ToString() + ' kisayol silindi.')

# ---- 3) Kayitlar (data) ne olsun
$secim = 1
if (-not (Test-Path $Hedef)) {
  Adim '3/5 Program klasoru'
  Tamam ($Hedef + ' zaten yok.')
  $secim = 0
} else {
  Adim '3/5 Kayitlarin (musteri, arac, is emri, yedekler) durumu'
  if ($VeriSil) { $secim = 2 } elseif ($ProgramiSakla) { $secim = 3 } elseif ($VeriSakla) { $secim = 1 }
  elseif (-not $Evet) {
    $db = Join-Path $dataKlasor 'servis.db'
    if (Test-Path $db) { Write-Host ('   Veritabani bulundu: ' + [math]::Round((Get-Item $db).Length / 1KB) + ' KB, son degisiklik ' + (Get-Item $db).LastWriteTime) }
    else { Write-Host '   Veritabani yok (uygulama hic calismamis olabilir).' }
    Write-Host '   [1] KAYITLARI SAKLA (onerilen): data klasoru C:\ServisDefteriYedek-<tarih> altina kopyalanir, sonra program silinir'
    Write-Host '   [2] HEPSINI SIL: kayitlar ve yedekler dahil her sey silinir, GERI DONUSU YOKTUR (deneme bilgisayari icin)'
    Write-Host '   [3] SILME: sadece durdur + gorev/kisayol kaldir; C:\ServisDefteri oldugu gibi kalir'
    $c = Read-Host '   Seciminiz [1/2/3] (Enter = 1)'
    if ($c -eq '2') {
      $onay = Read-Host '   Emin misin? Silmek icin SIL yaz'
      if ($onay -ceq 'SIL') { $secim = 2 } else { Uyari 'Onaylanmadi, kayitlar SAKLANACAK (secenek 1).'; $secim = 1 }
    } elseif ($c -eq '3') { $secim = 3 }
  }
  if ($secim -eq 1 -and -not (Test-Path $dataKlasor)) { Tamam 'Saklanacak kayit yok.'; $secim = 2 }
}

$klasorSilinsin = ($secim -eq 1 -or $secim -eq 2)
if ($secim -eq 1) {
  $yedekKlasor = 'C:\ServisDefteriYedek-' + (Get-Date -Format 'yyyyMMdd-HHmm')
  New-Item -ItemType Directory -Force -Path $yedekKlasor | Out-Null
  robocopy $dataKlasor (Join-Path $yedekKlasor 'data') /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
  $rc = $LASTEXITCODE; $global:LASTEXITCODE = 0
  if (Test-Path $envDosya) { try { Copy-Item $envDosya (Join-Path $yedekKlasor '.env') -Force } catch {} }
  $kaynakDb = Join-Path $dataKlasor 'servis.db'; $kopyaDb = Join-Path $yedekKlasor 'data\servis.db'
  $dogru = ($rc -lt 8) -and ((-not (Test-Path $kaynakDb)) -or ((Test-Path $kopyaDb) -and ((Get-Item $kaynakDb).Length -eq (Get-Item $kopyaDb).Length)))
  if ($dogru) { Tamam ('Kayitlar kopyalandi: ' + $yedekKlasor) }
  else { Uyari 'Kayitlar tam kopyalanamadi! Guvenlik icin klasor SILINMEYECEK.'; $klasorSilinsin = $false }
} elseif ($secim -eq 2) {
  Uyari 'Kayitlar ve yedekler silinecek.'
} elseif ($secim -eq 3) {
  Tamam ($Hedef + ' oldugu gibi birakildi.')
}

# ---- 4) Klasoru sil
Adim '4/5 Program klasoru siliniyor'
if ($klasorSilinsin -and (Test-Path $Hedef)) {
  Set-Location $env:TEMP
  Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'rd', '/s', '/q', $Hedef -Wait -WindowStyle Hidden
  if (Test-Path $Hedef) { [void](Surecleri-Kapat); Start-Sleep -Seconds 3; Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'rd', '/s', '/q', $Hedef -Wait -WindowStyle Hidden }
  if (Test-Path $Hedef) { Uyari ($Hedef + ' tamamen silinemedi (bir program dosyayi kullaniyor olabilir). Bilgisayari yeniden baslatip klasoru elle sil.') }
  else { Tamam ($Hedef + ' silindi.') }
} elseif (-not $klasorSilinsin) { Tamam 'Klasor silinmedi (secimin geregi).' }

# ---- 5) Python
Adim '5/5 Python'
Remove-Item (Join-Path $env:TEMP 'python-3.12.8-amd64.exe') -Force -ErrorAction SilentlyContinue
if ($pyBizKurduk) {
  $pyKaldir = $PythonSil.IsPresent
  if (-not $PythonSil -and -not $Evet) {
    $c = Read-Host '   Python 3.12 bu kurulumla yuklenmisti. Onu da kaldirayim mi? (baska programlar kullaniyor olabilir) [e/H]'
    $pyKaldir = ($c -match '^[eE]')
  }
  if ($pyKaldir) {
    $anahtarlar = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*')
    $kayit = Get-ItemProperty $anahtarlar -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like 'Python 3.12*' -and "$($_.Publisher)" -like 'Python Software Foundation*' -and "$($_.UninstallString)" -match '\.exe' -and $_.DisplayName -notmatch 'Launcher|Documentation|Standard Library|Test Suite|Tcl|pip|Development|Core|Executables|Add to Path' } | Select-Object -First 1
    if ($kayit) {
      Write-Host ('   Kaldiriliyor: ' + $kayit.DisplayName)
      Start-Process -FilePath 'cmd.exe' -ArgumentList ('/c "' + $kayit.UninstallString + ' /quiet"') -Wait -WindowStyle Hidden
      Tamam 'Python kaldirma komutu calistirildi.'
    } else {
      $wg = Get-Command winget -ErrorAction SilentlyContinue
      if ($wg) { & winget uninstall -e --id Python.Python.3.12 --silent | Out-Host } else { Uyari 'Python otomatik kaldirilamadi. Ayarlar > Uygulamalar bolumunden "Python 3.12" i kaldir.' }
    }
  } else { Tamam 'Python birakildi.' }
} else {
  Tamam 'Python bu kurulum tarafindan yuklenmedi (ya da iz yok); dokunulmadi.'
}

# ---- Kontrol listesi
Write-Host ''
Write-Host '=============================================' -ForegroundColor Green
Write-Host '   KONTROL' -ForegroundColor Green
Write-Host '=============================================' -ForegroundColor Green
$g1 = [bool](Get-ScheduledTask -TaskName 'ServisDefteri' -ErrorAction SilentlyContinue)
$g2 = [bool](Get-ScheduledTask -TaskName 'ServisDefteri-Yedek' -ErrorAction SilentlyContinue) -or [bool](Get-ScheduledTask -TaskName 'ServisDefteri-YedekKontrol' -ErrorAction SilentlyContinue)
if ($g1 -or $g2) { Uyari 'Windows gorevlerinden biri hala duruyor.' } else { Tamam 'Windows gorevleri kaldirildi.' }
if (Test-Path (Join-Path ([Environment]::GetFolderPath('CommonDesktopDirectory')) 'Servis Defteri.url')) { Uyari 'Masaustu kisayolu duruyor.' } else { Tamam 'Masaustu kisayollari kaldirildi.' }
if ($klasorSilinsin) { if (Test-Path $Hedef) { Uyari ($Hedef + ' duruyor.') } else { Tamam ($Hedef + ' silindi.') } }
try { $dinleyen = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue; if ($dinleyen) { Uyari 'Port 5000 hala bir program tarafindan kullaniliyor (baska bir kopya calisiyor olabilir).' } else { Tamam 'Port 5000 bos.' } } catch {}
if ($secim -eq 1 -and $klasorSilinsin) { Write-Host (' Kayitlariniz burada: ' + $yedekKlasor) -ForegroundColor Yellow }
if ($disYedek) { Write-Host (' Dis yedek klasoru SILINMEDI: ' + $disYedek) -ForegroundColor Yellow }
if (Get-Service -Name 'cloudflared' -ErrorAction SilentlyContinue) {
  Write-Host ' Bu bilgisayarda Cloudflare tunel servisi var; ayri bir programdir, DOKUNULMADI.' -ForegroundColor Yellow
  Write-Host '   Kaldirmak istersen (yonetici komut satirinda):  cloudflared service uninstall   + Cloudflare panelinden tuneli sil.'
}
Write-Host ' Yazici surucusu (XP-470B) ve pencerelerin kendisi degistirilmedi.'
Write-Host (' Kaldirma kaydi: ' + $Log)
Dur ' Kapatmak icin Enter'
exit 0
