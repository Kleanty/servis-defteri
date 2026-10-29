# Yonetici olarak calisir (kur.ps1 ve 3-OTOMATIK-BASLAT-KUR.bat cagirir). Iki Windows gorevi olusturur:
#   ServisDefteri        : bilgisayar acilinca (kimse oturum acmasa bile) uygulamayi baslatir, cokerse yeniden dener, sure siniri YOK
#   ServisDefteri-Yedek  : her gece 02:00'de yedek alir (bilgisayar kapaliysa acilinca alir)
#   ServisDefteri-YedekKontrol : 15 dakikada bir USB / Google Drive yedeginin gerekip gerekmedigine bakar
param([string]$Kok)
$ErrorActionPreference = 'Stop'
try {
$py  = Join-Path $Kok 'venv\Scripts\pythonw.exe'
$pyc = Join-Path $Kok 'venv\Scripts\python.exe'
if (-not (Test-Path $py)) { Write-Host 'Once kurulum (SERVIS-DEFTERI-KUR.bat) calistirilmali.'; exit 1 }
$sistem = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

$ayar = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
$eylem = New-ScheduledTaskAction -Execute $py -Argument ('"' + (Join-Path $Kok 'scripts\calistir.py') + '"') -WorkingDirectory $Kok
Register-ScheduledTask -TaskName 'ServisDefteri' -Action $eylem -Trigger (New-ScheduledTaskTrigger -AtStartup) -Principal $sistem -Settings $ayar -Force | Out-Null

$ayar2 = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$eylem2 = New-ScheduledTaskAction -Execute $pyc -Argument ('"' + (Join-Path $Kok 'scripts\yedek.py') + '"') -WorkingDirectory $Kok
Register-ScheduledTask -TaskName 'ServisDefteri-Yedek' -Action $eylem2 -Trigger (New-ScheduledTaskTrigger -Daily -At '02:00') -Principal $sistem -Settings $ayar2 -Force | Out-Null

# 15 dakikada bir: USB bellek (adi servisyedek) takilmissa / Google Drive'a gitmemis yedek varsa yedegi yapar (is yoksa hemen cikar)
$tet = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)
$ayar3 = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
$eylem3 = New-ScheduledTaskAction -Execute $pyc -Argument ('"' + (Join-Path $Kok 'scripts\yedek.py') + '" --duzenli') -WorkingDirectory $Kok
Register-ScheduledTask -TaskName 'ServisDefteri-YedekKontrol' -Action $eylem3 -Trigger $tet -Principal $sistem -Settings $ayar3 -Force | Out-Null

try { Stop-ScheduledTask -TaskName 'ServisDefteri' -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Seconds 1
Start-ScheduledTask -TaskName 'ServisDefteri'
Write-Host 'Tamam: uygulama artik bilgisayar acilinca kendiliginden baslar. Gece 02:00 yedek alinir; USB bellek takilinca da yedeklenir.'
} catch {
  Write-Host ''
  Write-Host ('HATA (otomatik baslatma gorevi): ' + $_.Exception.Message) -ForegroundColor Red
  try { Write-Host ('Konum: ' + ($_.InvocationInfo.PositionMessage -replace '\s+',' ')) -ForegroundColor Red } catch {}
  Write-Host 'Olasi neden: yonetici olarak calistirilmadi ya da sirket bilgisayarinda grup ilkesi gorev olusturmayi engelliyor.' -ForegroundColor Yellow
  exit 1
}
