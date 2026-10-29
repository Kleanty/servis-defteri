# Kurulum betikleri tarafindan "nokta ile yuklenir" (. .\hata-raporu.ps1). Kurulum hatasinda TEK bir rapor dosyasi uretir:
# hangi adimda, hangi satirda, hangi hata; olasi neden ve cozum; bilgisayar bilgisi (Windows, Python, disk, internet); kurulum kaydinin sonu.
# Bu dosya asla hata firlatmaz (rapor uretilemese bile kurulumun asil hata mesaji gorunur).
function Native-Calistir([string]$Exe, [string[]]$Arg) {
  # Dis programi (pip, python...) calistirir, ciktisini $script:SonCikti'da tutar, cikis kodunu dondurur. stderr satirlari hata sayilmaz.
  $eski = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
  try { $cikti = & $Exe @Arg 2>&1 | ForEach-Object { "$_" }; $kod = $LASTEXITCODE } catch { $cikti = @("$_"); $kod = 99 } finally { $ErrorActionPreference = $eski }
  $script:SonCikti = @($cikti)
  return $kod
}
function _Gizle([string]$Satir) {
  # Rapora anahtar/sifre/proxy kimligi sizmasin (rapor masaustune kopyalanir ve gonderilir)
  if ($Satir -match '(?i)sifre|password|parola|passwd') { return '(satir gizlendi: sifre iceriyor olabilir)' }
  $t = [regex]::Replace($Satir, '\b(ya|sk)_([a-z0-9]{4})_[A-Za-z0-9_-]{12,}', '$1_$2_****')
  $t = [regex]::Replace($t, '://[^/@\s:]+:[^/@\s]+@', '://****:****@')
  $t = [regex]::Replace($t, '(?i)(ANAHTAR|API[_-]?KEY|TOKEN)\s*[=:]\s*\S+', '$1=****')
  return $t
}
function _Rapor-Ipuclari([string]$Metin) {
  $m = "$Metin"
  $o = New-Object System.Collections.Generic.List[string]
  if ($m -match 'pip|PyPI|pypi|files\.pythonhosted|Could not find a version|No matching distribution|Max retries|ConnectionError|timed out|Temporary failure|getaddrinfo|SSL|certificate|ProxyError|Invoke-WebRequest|WebException|The remote name could not be resolved|baglanti') {
    $o.Add('Internet/baglanti sorunu olabilir: bilgisayarin internete bagli oldugunu, tarayicida https://pypi.org adresinin acildigini kontrol et. Sirket/okul agi veya proxy varsa kurulum engellenebilir; telefonun sicak noktasiyla (hotspot) tekrar dene. Antivirus/guvenlik duvari "python.exe" ve "pip"i engelliyor olabilir.')
  }
  if ($m -match 'Access is denied|UnauthorizedAccess|PermissionError|izin|Erisim engellendi|being used by another process|baska bir islem|WinError 5|WinError 32') {
    $o.Add('Izin/kilit sorunu: kurulum dosyasina sag tikla - "Yonetici olarak calistir". Antivirus klasoru (C:\ServisDefteri) kilitliyor olabilir; gecici olarak kapatip tekrar dene. Uygulama calisiyorsa once windows\DURDUR.bat calistir.')
  }
  if ($m -match 'No space left|not enough space|yetersiz disk|disk dolu|WinError 112|There is not enough space') {
    $o.Add('Diskte yer yok: C: surucusunde en az 1 GB bos yer olmali. Gereksiz dosyalari silip tekrar calistir.')
  }
  if ($m -match 'Python kurulamadi|Python bulunamadi|No Python|winget|Sanal ortam') {
    $o.Add('Python sorunu: https://www.python.org/downloads/ adresinden Python 3.12 kur ("Add python.exe to PATH" kutusunu ISARETLE), bilgisayari yeniden baslat, kurulumu tekrar calistir. Microsoft Store''daki sahte "python" kisayolu sorun cikarabilir: Ayarlar > Uygulamalar > Uygulama yurutme takma adlari bolumunden python.exe ve python3.exe takma adlarini kapat.')
  }
  if ($m -match 'robocopy|kopyalanamadi') {
    $o.Add('Dosya kopyalama sorunu: kurulum klasorunu zip icinden degil, "Tumunu ayikla" ile cikardigin klasorden calistir; yolda Turkce karakter/cok uzun yol olmasin (ornek: C:\Kurulum).')
  }
  if ($m -match 'paket dogrulamasi|import|ModuleNotFound|DLL load failed|pywin32|win32print') {
    $o.Add('Paket yuklendi ama calismiyor: "Microsoft Visual C++ Redistributable (x64)" kurulu olmayabilir (https://aka.ms/vs/17/release/vc_redist.x64.exe). Kurup tekrar dene. Windows 32 bit (x86) desteklenmez.')
  }
  if ($m -match 'Gorev|ScheduledTask|Register-ScheduledTask') {
    $o.Add('Zamanlanmis gorev olusturulamadi: kurulumu YONETICI olarak calistirdigindan emin ol. Grup ilkesi (sirket bilgisayari) gorev olusturmayi engelliyor olabilir.')
  }
  if ($m -match 'imza|SHA256|dijital') {
    $o.Add('Indirilen dosyanin dogrulamasi basarisiz: indirme bozulmus ya da aradaki ag/antivirus dosyayi degistirmis olabilir. Baska bir aga baglanip tekrar dene.')
  }
  if ($o.Count -eq 0) { $o.Add('Otomatik bir neden bulunamadi. Bu raporun TAMAMINI gonder; hata mesaji, adim ve kurulum kaydinin sonu cozumu bulmamizi saglar.') }
  return $o
}
function Hata-Raporu {
  param($Hata, [string]$Adim = '', [string]$LogYol = '', [string]$RaporKlasor = '', [string]$Baslik = 'Servis Defteri kurulum hatasi', [string]$Kaynak = '')
  try {
    $s = New-Object System.Collections.Generic.List[string]
    $s.Add('=====================================================')
    $s.Add(' ' + $Baslik)
    $s.Add('=====================================================')
    $s.Add('Zaman        : ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
    $s.Add('Hata adimi   : ' + $(if ($Adim) { $Adim } else { '(bilinmiyor)' }))
    $msg = ''; $tip = ''; $konum = ''; $yigin = ''
    if ($Hata) {
      try { $msg = "$($Hata.Exception.Message)" } catch { $msg = "$Hata" }
      try { $tip = "$($Hata.Exception.GetType().FullName)" } catch {}
      try { $konum = "$($Hata.InvocationInfo.PositionMessage)".Trim() } catch {}
      try { $yigin = "$($Hata.ScriptStackTrace)".Trim() } catch {}
    }
    $s.Add('Hata mesaji  : ' + (_Gizle $msg))
    if ($tip) { $s.Add('Hata turu     : ' + $tip) }
    if ($konum) { $s.Add(''); $s.Add('Betikte konum  :'); $konum -split "`r?`n" | ForEach-Object { $s.Add('   ' + $_) } }
    if ($yigin) { $s.Add(''); $s.Add('Cagri yigini   :'); $yigin -split "`r?`n" | ForEach-Object { $s.Add('   ' + $_) } }
    $son = @(); if ($script:SonCikti) { $son = @($script:SonCikti | Select-Object -Last 25) }
    if ($son.Count -gt 0) { $s.Add(''); $s.Add('Son calistirilan programin ciktisi (pip/python):'); $son | ForEach-Object { $s.Add('   ' + (_Gizle $_)) } }
    $s.Add(''); $s.Add('--- OLASI NEDEN VE COZUM -------------------------------')
    $ipucu = _Rapor-Ipuclari ($msg + ' ' + $Adim + ' ' + ($son -join ' '))
    $ipucu | ForEach-Object { $s.Add(' * ' + $_) }
    $s.Add(''); $s.Add('--- BILGISAYAR BILGISI ---------------------------------')
    try { $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop; $s.Add('Windows      : ' + $os.Caption + ' ' + $os.Version + ' (' + $os.OSArchitecture + ')'); $s.Add('Bos RAM      : ' + [math]::Round($os.FreePhysicalMemory / 1024) + ' MB') } catch { $s.Add('Windows      : ' + [Environment]::OSVersion.VersionString) }
    $s.Add('PowerShell   : ' + $PSVersionTable.PSVersion.ToString())
    try { $yon = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator); $s.Add('Yonetici     : ' + $yon) } catch {}
    $s.Add('Kullanici    : ' + $env:USERNAME + '   Bilgisayar: ' + $env:COMPUTERNAME)
    try { $d = Get-PSDrive -Name C -ErrorAction Stop; $s.Add('C: bos yer   : ' + [math]::Round($d.Free / 1GB, 1) + ' GB') } catch {}
    if ($Kaynak) { $s.Add('Kurulum yeri : ' + $Kaynak) }
    try { $pl = (& py -0p 2>&1 | ForEach-Object { "$_" }) -join ' | '; if ($pl) { $s.Add('Python (py)  : ' + $pl) } } catch { $s.Add('Python (py)  : py baslatici yok') }
    try { $pv = (& python --version 2>&1 | ForEach-Object { "$_" }) -join ' '; $s.Add('python       : ' + $pv) } catch { $s.Add('python       : PATH''te yok') }
    try { $px = [Net.WebRequest]::DefaultWebProxy; $pa = $px.GetProxy([Uri]'https://pypi.org'); $s.Add('Proxy        : ' + $(if ($pa.AbsoluteUri -eq 'https://pypi.org/') { 'yok (dogrudan)' } else { $pa.AbsoluteUri })) } catch {}
    foreach ($u in 'https://pypi.org', 'https://files.pythonhosted.org', 'https://www.python.org') {
      try { $r = Invoke-WebRequest -UseBasicParsing -Uri $u -Method Head -TimeoutSec 8 -ErrorAction Stop; $s.Add('Internet     : ' + $u + ' -> OK (' + $r.StatusCode + ')') }
      catch {
        $yanit = $null; try { $yanit = $_.Exception.Response } catch {}
        if ($yanit) { $s.Add('Internet     : ' + $u + ' -> ulasildi (sunucu yanit verdi: HTTP ' + [int]$yanit.StatusCode + ')') }
        else { $s.Add('Internet     : ' + $u + ' -> ULASILAMADI (' + (("$($_.Exception.Message)") -replace '\s+', ' ') + ')') }
      }
    }
    if ($LogYol -and (Test-Path $LogYol)) {
      $s.Add(''); $s.Add('--- KURULUM KAYDININ SONU (' + $LogYol + ') ---')
      try { Get-Content $LogYol -Tail 60 -ErrorAction Stop | ForEach-Object { $s.Add((_Gizle $_)) } } catch { $s.Add('(kayit okunamadi)') }
    }
    $s.Add(''); $s.Add('=====================================================')
    $klasor = $RaporKlasor; if (-not $klasor -or -not (Test-Path $klasor)) { $klasor = $env:TEMP }
    $dosya = Join-Path $klasor 'kurulum-hata.txt'
    [IO.File]::WriteAllLines($dosya, $s, (New-Object Text.UTF8Encoding($true)))
    $kopya = $null
    try { $masa = [Environment]::GetFolderPath('CommonDesktopDirectory'); if (-not $masa -or -not (Test-Path $masa)) { $masa = [Environment]::GetFolderPath('Desktop') }; if ($masa) { $kopya = Join-Path $masa 'SERVIS-DEFTERI-KURULUM-HATASI.txt'; Copy-Item $dosya $kopya -Force } } catch { $kopya = $null }
    Write-Host ''
    Write-Host 'OLASI NEDEN / COZUM:' -ForegroundColor Yellow
    $ipucu | ForEach-Object { Write-Host (' * ' + $_) -ForegroundColor Yellow }
    Write-Host ''
    Write-Host ('Hata raporu hazir: ' + $(if ($kopya) { $kopya } else { $dosya })) -ForegroundColor Red
    Write-Host 'Cozum bulunamazsa bu dosyayi (tamamini) gonder; hatanin nerede oldugu icinde yazar.' -ForegroundColor Red
    try { Start-Process notepad.exe -ArgumentList ('"' + $(if ($kopya) { $kopya } else { $dosya }) + '"') } catch {}
    return $dosya
  } catch {
    Write-Host ('(Hata raporu olusturulamadi: ' + $_.Exception.Message + ')') -ForegroundColor DarkYellow
  }
}
