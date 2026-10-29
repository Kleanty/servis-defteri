@echo off
fltmc >nul 2>&1
if errorlevel 1 (
  echo Bu dosyayi YONETICI olarak calistir: dosyaya sag tikla - "Yonetici olarak calistir".
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Stop-ScheduledTask -TaskName 'ServisAjan' -ErrorAction SilentlyContinue } catch {}; try { Unregister-ScheduledTask -TaskName 'ServisAjan' -Confirm:$false -ErrorAction SilentlyContinue } catch {}; Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*yazdirma_ajani.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Ajan durduruldu ve otomatik baslatma kaldirildi.
echo C:\ServisAjan klasorunu istersen elle silebilirsin (ayar ve kayit dosyalari orada).
pause
